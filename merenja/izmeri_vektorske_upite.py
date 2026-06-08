#!/usr/bin/env python3
"""
Benchmark vektorskih indeksa u PostgreSQL i Neo4j bazama.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
from neo4j import GraphDatabase

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from semantic_vectors import EMBEDDING_DIM, embed_text, embed_texts, generate_semantic_payload

POSTGRES_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5433")),
    "dbname": os.environ.get("POSTGRES_DB", "bankdb"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
}

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "bankdb123")

RESULTS_DIR = ROOT_DIR / "rezultati" / "vektorski_benchmark"
SUMMARY_CSV = RESULTS_DIR / "rezime.csv"
DETAILS_CSV = RESULTS_DIR / "detalji.csv"

PG_HNSW_INDEX = "idx_transakcija_embedding_hnsw"
PG_IVF_INDEX = "idx_transakcija_embedding_ivfflat"
NEO4J_INDEX = "transakcija_embedding_idx"

QUERY_SPECS = [
    {
        "oznaka": "V1",
        "naziv": "Čista semantička pretraga",
        "tekst_upita": "plaćanje kirije",
        "tip_rezultata": "transakcija",
        "kandidat_mnozilac": 1,
    },
    {
        "oznaka": "V2",
        "naziv": "Semantika i atributski filteri",
        "tekst_upita": "mesečna uplata za zakup stana ili poslovnog prostora",
        "tip_rezultata": "transakcija",
        "kandidat_mnozilac": 4,
    },
    {
        "oznaka": "V3",
        "naziv": "Semantika i graf ciklus",
        "tekst_upita": "neuobičajen prenos novca između povezanih računa",
        "tip_rezultata": "racun",
        "kandidat_mnozilac": 8,
    },
]

PG_HNSW_AUTO_CONFIGS = [
    {"m": 16, "ef_construction": 64, "ef_search": 80},
    {"m": 24, "ef_construction": 96, "ef_search": 120},
    {"m": 32, "ef_construction": 128, "ef_search": 160},
]

PG_IVF_AUTO_CONFIGS = [
    {"lists": 100, "probes": 10},
    {"lists": 200, "probes": 20},
    {"lists": 400, "probes": 40},
]

NEO4J_AUTO_CONFIGS = [
    {"m": 16, "ef_construction": 100, "quantization": "true"},
    {"m": 24, "ef_construction": 160, "quantization": "true"},
    {"m": 32, "ef_construction": 200, "quantization": "false"},
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"


def overlap_at_k(reference_ids: list[int], candidate_ids: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    ref = set(reference_ids[:k])
    cand = set(candidate_ids[:k])
    return round(len(ref & cand) / k, 4)


def recall_at_k(reference_ids: list[int], candidate_ids: list[int], k: int) -> float:
    ref = set(reference_ids[:k])
    if not ref:
        return 0.0
    cand = set(candidate_ids[:k])
    return round(len(ref & cand) / len(ref), 4)


def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def drop_pg_indexes(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"DROP INDEX IF EXISTS {PG_HNSW_INDEX}")
        cur.execute(f"DROP INDEX IF EXISTS {PG_IVF_INDEX}")
    conn.commit()


def create_pg_hnsw_index(conn, m: int, ef_construction: int) -> tuple[float, int]:
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE INDEX {PG_HNSW_INDEX}
            ON Transakcija
            USING hnsw (embedding_trans vector_cosine_ops)
            WITH (m = %s, ef_construction = %s)
            """,
            (m, ef_construction),
        )
    conn.commit()
    elapsed_ms = (time.perf_counter() - start) * 1000

    with conn.cursor() as cur:
        cur.execute("SELECT pg_relation_size(%s)", (PG_HNSW_INDEX,))
        size_bytes = cur.fetchone()[0]

    return elapsed_ms, size_bytes


def create_pg_ivfflat_index(conn, lists: int) -> tuple[float, int]:
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE INDEX {PG_IVF_INDEX}
            ON Transakcija
            USING ivfflat (embedding_trans vector_cosine_ops)
            WITH (lists = %s)
            """,
            (lists,),
        )
    conn.commit()
    elapsed_ms = (time.perf_counter() - start) * 1000

    with conn.cursor() as cur:
        cur.execute("SELECT pg_relation_size(%s)", (PG_IVF_INDEX,))
        size_bytes = cur.fetchone()[0]

    return elapsed_ms, size_bytes


def drop_neo4j_index(session) -> None:
    session.run(f"DROP INDEX {NEO4J_INDEX} IF EXISTS").consume()


def wait_for_neo4j_index(session, name: str) -> None:
    while True:
        records = session.run(
            "SHOW VECTOR INDEXES YIELD name, state WHERE name = $name RETURN state",
            name=name,
        ).data()
        if records and records[0]["state"] == "ONLINE":
            return
        time.sleep(0.2)


def create_neo4j_index(session, m: int, ef_construction: int, quantization: bool) -> float:
    start = time.perf_counter()
    session.run(
        f"""
        CREATE VECTOR INDEX {NEO4J_INDEX} IF NOT EXISTS
        FOR ()-[t:TRANSAKCIJA]-() ON (t.embedding_trans)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {EMBEDDING_DIM},
            `vector.similarity_function`: 'cosine',
            `vector.hnsw.m`: {m},
            `vector.hnsw.ef_construction`: {ef_construction},
            `vector.quantization.enabled`: {str(quantization).lower()}
        }}}}
        """
    ).consume()
    wait_for_neo4j_index(session, NEO4J_INDEX)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


def pg_query_sql(spec: dict, query_vector: str, k: int, candidate_limit: int) -> tuple[str, tuple]:
    if spec["oznaka"] == "V1":
        return (
            """
            SELECT
                id_trans AS entity_id,
                opis_trans AS label,
                1 - (embedding_trans <=> %s::vector) AS score
            FROM Transakcija
            ORDER BY embedding_trans <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, k),
        )

    if spec["oznaka"] == "V2":
        return (
            """
            SELECT
                id_trans AS entity_id,
                opis_trans AS label,
                1 - (embedding_trans <=> %s::vector) AS score
            FROM Transakcija
            WHERE iznos_trans >= 30000
              AND status_trans = 'uspesna'
              AND datum_vreme_trans >= NOW() - INTERVAL '12 months'
            ORDER BY embedding_trans <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, k),
        )

    if spec["oznaka"] == "V3":
        return (
            """
            WITH kandidati AS (
                SELECT
                    id_trans,
                    id_rac_platilac,
                    id_rac_primalac,
                    1 - (embedding_trans <=> %s::vector) AS score
                FROM Transakcija
                ORDER BY embedding_trans <=> %s::vector
                LIMIT %s
            ),
            racuni_sa_punomocjem AS (
                SELECT DISTINCT id_rac FROM Ima_Punomoc
            ),
            ciklusni_racuni AS (
                SELECT k.id_rac_platilac AS racun_id, k.score
                FROM kandidati k
                JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_platilac
                WHERE EXISTS (
                    SELECT 1
                    FROM Transakcija t2
                    WHERE t2.id_rac_platilac = k.id_rac_primalac
                      AND t2.id_rac_primalac = k.id_rac_platilac
                )
                UNION ALL
                SELECT k.id_rac_platilac AS racun_id, k.score
                FROM kandidati k
                JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_platilac
                WHERE EXISTS (
                    SELECT 1
                    FROM Transakcija t2
                    JOIN Transakcija t3
                      ON t2.id_rac_primalac = t3.id_rac_platilac
                    WHERE t2.id_rac_platilac = k.id_rac_primalac
                      AND t3.id_rac_primalac = k.id_rac_platilac
                )
                UNION ALL
                SELECT k.id_rac_primalac AS racun_id, k.score
                FROM kandidati k
                JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_primalac
                WHERE EXISTS (
                    SELECT 1
                    FROM Transakcija t2
                    WHERE t2.id_rac_platilac = k.id_rac_primalac
                      AND t2.id_rac_primalac = k.id_rac_platilac
                )
                UNION ALL
                SELECT k.id_rac_primalac AS racun_id, k.score
                FROM kandidati k
                JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_primalac
                WHERE EXISTS (
                    SELECT 1
                    FROM Transakcija t2
                    JOIN Transakcija t3
                      ON t2.id_rac_primalac = t3.id_rac_platilac
                    WHERE t2.id_rac_platilac = k.id_rac_primalac
                      AND t3.id_rac_primalac = k.id_rac_platilac
                )
            )
            SELECT
                racun_id AS entity_id,
                CAST(racun_id AS TEXT) AS label,
                MAX(score) AS score
            FROM ciklusni_racuni
            GROUP BY racun_id
            ORDER BY score DESC, entity_id ASC
            LIMIT %s
            """,
            (query_vector, query_vector, candidate_limit, k),
        )

    return (
        """
        WITH kandidati AS (
            SELECT
                id_trans,
                id_rac_platilac,
                id_rac_primalac,
                1 - (embedding_trans <=> %s::vector) AS score
            FROM Transakcija
            ORDER BY embedding_trans <=> %s::vector
            LIMIT %s
        ),
        racuni_sa_punomocjem AS (
            SELECT DISTINCT id_rac FROM Ima_Punomoc
        ),
        ciklusni_racuni AS (
            SELECT k.id_rac_platilac AS racun_id, k.score
            FROM kandidati k
            JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_platilac
            WHERE EXISTS (
                SELECT 1
                FROM Transakcija t2
                WHERE t2.id_rac_platilac = k.id_rac_primalac
                  AND t2.id_rac_primalac = k.id_rac_platilac
            )
            UNION ALL
            SELECT k.id_rac_platilac AS racun_id, k.score
            FROM kandidati k
            JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_platilac
            WHERE EXISTS (
                SELECT 1
                FROM Transakcija t2
                JOIN Transakcija t3
                  ON t2.id_rac_primalac = t3.id_rac_platilac
                WHERE t2.id_rac_platilac = k.id_rac_primalac
                  AND t3.id_rac_primalac = k.id_rac_platilac
            )
            UNION ALL
            SELECT k.id_rac_primalac AS racun_id, k.score
            FROM kandidati k
            JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_primalac
            WHERE EXISTS (
                SELECT 1
                FROM Transakcija t2
                WHERE t2.id_rac_platilac = k.id_rac_primalac
                  AND t2.id_rac_primalac = k.id_rac_platilac
            )
            UNION ALL
            SELECT k.id_rac_primalac AS racun_id, k.score
            FROM kandidati k
            JOIN racuni_sa_punomocjem p ON p.id_rac = k.id_rac_primalac
            WHERE EXISTS (
                SELECT 1
                FROM Transakcija t2
                JOIN Transakcija t3
                  ON t2.id_rac_primalac = t3.id_rac_platilac
                WHERE t2.id_rac_platilac = k.id_rac_primalac
                  AND t3.id_rac_primalac = k.id_rac_platilac
            )
        )
        SELECT
            racun_id AS entity_id,
            CAST(racun_id AS TEXT) AS label,
            MAX(score) AS score
        FROM ciklusni_racuni
        GROUP BY racun_id
        ORDER BY score DESC, entity_id ASC
        LIMIT %s
        """,
        (query_vector, query_vector, candidate_limit, k),
    )


def neo4j_query(spec: dict) -> str:
    if spec["oznaka"] == "V1":
        return """
        CALL db.index.vector.queryRelationships($index_name, $candidate_limit, $query_vector)
        YIELD relationship, score
        RETURN relationship.id_trans AS entity_id, relationship.opis_trans AS label, score
        ORDER BY score DESC, entity_id ASC
        LIMIT $k
        """

    if spec["oznaka"] == "V2":
        return """
        CALL db.index.vector.queryRelationships($index_name, $candidate_limit, $query_vector)
        YIELD relationship, score
        WHERE relationship.iznos_trans >= 30000
          AND relationship.status_trans = 'uspesna'
          AND datetime(relationship.datum_vreme_trans) >= datetime() - duration('P12M')
        RETURN relationship.id_trans AS entity_id, relationship.opis_trans AS label, score
        ORDER BY score DESC, entity_id ASC
        LIMIT $k
        """

    if spec["oznaka"] == "V3":
        return """
        CALL db.index.vector.queryRelationships($index_name, $candidate_limit, $query_vector)
        YIELD relationship, score
        MATCH (platilac:Racun)-[relationship:TRANSAKCIJA]->(primalac:Racun)
        WHERE (
            EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(platilac) }
            OR EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(primalac) }
        )
        AND (
            EXISTS { MATCH (primalac)-[:TRANSAKCIJA]->(platilac) }
            OR EXISTS { MATCH (primalac)-[:TRANSAKCIJA]->(:Racun)-[:TRANSAKCIJA]->(platilac) }
        )
        WITH score, platilac, primalac
        UNWIND [platilac, primalac] AS racun
        WITH racun, score
        WHERE EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(racun) }
        RETURN racun.id_rac AS entity_id, racun.broj_rac AS label, max(score) AS score
        ORDER BY score DESC, entity_id ASC
        LIMIT $k
        """

    return """
    CALL db.index.vector.queryRelationships($index_name, $candidate_limit, $query_vector)
    YIELD relationship, score
    MATCH (platilac:Racun)-[relationship:TRANSAKCIJA]->(primalac:Racun)
    WHERE (
        EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(platilac) }
        OR EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(primalac) }
    )
    AND (
        EXISTS { MATCH (primalac)-[:TRANSAKCIJA]->(platilac) }
        OR EXISTS { MATCH (primalac)-[:TRANSAKCIJA]->(:Racun)-[:TRANSAKCIJA]->(platilac) }
    )
    WITH score, platilac, primalac
    UNWIND [platilac, primalac] AS racun
    WITH racun, score
    WHERE EXISTS { MATCH (:Klijent)-[:IMA_PUNOMOC]->(racun) }
    RETURN racun.id_rac AS entity_id, racun.broj_rac AS label, max(score) AS score
    ORDER BY score DESC, entity_id ASC
    LIMIT $k
    """


def run_pg_query(conn, spec: dict, query_vector: list[float], k: int, candidate_limit: int, session_setup: list[str] | None = None) -> tuple[float, list[dict]]:
    sql, params = pg_query_sql(spec, vector_literal(query_vector), k, candidate_limit)
    start = time.perf_counter()
    with conn.cursor() as cur:
        if session_setup:
            for statement in session_setup:
                cur.execute(statement)
        cur.execute(sql, params)
        rows = cur.fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    results = [{"entity_id": row[0], "label": row[1], "score": float(row[2])} for row in rows]
    return elapsed_ms, results


def run_neo4j_query(session, spec: dict, query_vector: list[float], k: int, candidate_limit: int) -> tuple[float, list[dict]]:
    start = time.perf_counter()
    rows = session.run(
        neo4j_query(spec),
        index_name=NEO4J_INDEX,
        candidate_limit=candidate_limit,
        query_vector=query_vector,
        k=k,
    ).data()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, rows


def measure_many(fn, repetitions: int, warmup: int) -> tuple[list[float], list[dict]]:
    samples = []
    latest_rows = []
    for index in range(warmup + repetitions):
        elapsed_ms, rows = fn()
        if index >= warmup:
            samples.append(elapsed_ms)
            latest_rows = rows
    return samples, latest_rows


def summarize_samples(samples: list[float]) -> dict[str, float]:
    return {
        "avg_ms": round(statistics.mean(samples), 3),
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
    }


def sample_insert_rows(count: int, max_account_id: int) -> list[dict]:
    rng = random.Random(20260608)
    rows = []
    for offset in range(count):
        payload = generate_semantic_payload(rng)
        payer = 1 + (offset % max_account_id)
        receiver = 1 + ((offset + 17) % max_account_id)
        if payer == receiver:
            receiver = 1 + ((receiver + 1) % max_account_id)
        rows.append({
            "id_trans": 900000000 + offset,
            "iznos_trans": payload["iznos_trans"],
            "opis_trans": payload["opis_trans"],
            "status_trans": payload["status_trans"],
            "semanticka_grupa_trans": payload["semanticka_grupa_trans"],
            "id_rac_platilac": payer,
            "id_rac_primalac": receiver,
        })
    embeddingi = embed_texts([red["opis_trans"] for red in rows])
    for red, embedding in zip(rows, embeddingi):
        red["embedding_trans"] = embedding
    return rows


def parse_bool(value: str) -> bool:
    return value.lower() == "true"


def pg_hnsw_configs(args) -> list[dict]:
    if args.bez_auto_konfiguracija:
        return [{
            "m": args.pg_hnsw_m,
            "ef_construction": args.pg_hnsw_ef_construction,
            "ef_search": args.pg_hnsw_ef_search,
        }]
    return PG_HNSW_AUTO_CONFIGS


def pg_ivf_configs(args) -> list[dict]:
    if args.bez_auto_konfiguracija:
        return [{"lists": args.pg_ivf_lists, "probes": args.pg_ivf_probes}]
    return PG_IVF_AUTO_CONFIGS


def neo4j_configs(args) -> list[dict]:
    if args.bez_auto_konfiguracija:
        return [{
            "m": args.neo4j_hnsw_m,
            "ef_construction": args.neo4j_hnsw_ef_construction,
            "quantization": args.neo4j_quantization,
        }]
    return NEO4J_AUTO_CONFIGS


def append_detail_rows(
    detail_rows: list[dict],
    run_started: str,
    scale: int,
    spec: dict,
    method: str,
    rows: list[dict],
    parametri: str,
) -> None:
    detail_rows.extend([
        {
            "vreme_pokretanja": run_started,
            "scale": scale,
            "oznaka_upita": spec["oznaka"],
            "metod": method,
            "parametri": parametri,
            "rank": rank,
            "entity_id": row["entity_id"],
            "label": row["label"],
            "score": round(float(row["score"]), 6),
        }
        for rank, row in enumerate(rows, start=1)
    ])


def measure_pg_insert(conn, rows: list[dict]) -> float:
    start = time.perf_counter()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO Transakcija (
                    id_trans, iznos_trans, datum_vreme_trans, opis_trans, status_trans,
                    semanticka_grupa_trans, embedding_trans, id_rac_platilac, id_rac_primalac
                )
                VALUES (%s, %s, NOW(), %s, %s, %s, %s::vector, %s, %s)
                """,
                (
                    row["id_trans"],
                    row["iznos_trans"],
                    row["opis_trans"],
                    row["status_trans"],
                    row["semanticka_grupa_trans"],
                    vector_literal(row["embedding_trans"]),
                    row["id_rac_platilac"],
                    row["id_rac_primalac"],
                ),
            )
        cur.execute("DELETE FROM Transakcija WHERE id_trans >= 900000000")
    conn.commit()
    return round((time.perf_counter() - start) * 1000, 3)


def measure_neo4j_insert(session, rows: list[dict]) -> float:
    start = time.perf_counter()
    session.run(
        """
        UNWIND $rows AS row
        MATCH (platilac:Racun {id_rac: row.id_rac_platilac})
        MATCH (primalac:Racun {id_rac: row.id_rac_primalac})
        CREATE (platilac)-[t:TRANSAKCIJA {
            id_trans: row.id_trans,
            iznos_trans: row.iznos_trans,
            datum_vreme_trans: toString(datetime()),
            opis_trans: row.opis_trans,
            status_trans: row.status_trans,
            semanticka_grupa_trans: row.semanticka_grupa_trans,
            embedding_trans: row.embedding_trans,
            benchmark_insert: true
        }]->(primalac)
        """,
        rows=rows,
    ).consume()
    session.run("MATCH ()-[t:TRANSAKCIJA {benchmark_insert: true}]->() DELETE t").consume()
    return round((time.perf_counter() - start) * 1000, 3)


def save_summary(rows: list[dict]) -> None:
    columns = [
        "vreme_pokretanja", "scale", "oznaka_upita", "naziv_upita", "metod",
        "parametri", "avg_ms", "p50_ms", "p95_ms", "build_ms",
        "index_size_bytes", "insert_ms", "recall_at_k", "overlap_at_k",
    ]
    exists = SUMMARY_CSV.exists()
    with SUMMARY_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def save_details(rows: list[dict]) -> None:
    columns = [
        "vreme_pokretanja", "scale", "oznaka_upita", "metod", "parametri", "rank",
        "entity_id", "label", "score",
    ]
    exists = DETAILS_CSV.exists()
    with DETAILS_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, required=True)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--ponavljanja", type=int, default=10)
    parser.add_argument("--zagrevanje", type=int, default=2)
    parser.add_argument("--pg-hnsw-m", type=int, default=16)
    parser.add_argument("--pg-hnsw-ef-construction", type=int, default=64)
    parser.add_argument("--pg-hnsw-ef-search", type=int, default=80)
    parser.add_argument("--pg-ivf-lists", type=int, default=100)
    parser.add_argument("--pg-ivf-probes", type=int, default=10)
    parser.add_argument("--neo4j-hnsw-m", type=int, default=16)
    parser.add_argument("--neo4j-hnsw-ef-construction", type=int, default=100)
    parser.add_argument("--neo4j-quantization", choices=["true", "false"], default="true")
    parser.add_argument("--insert-count", type=int, default=50)
    parser.add_argument("--bez-auto-konfiguracija", action="store_true")
    args = parser.parse_args()

    ensure_results_dir()
    run_started = datetime.now().isoformat(timespec="seconds")
    summary_rows = []
    detail_rows = []
    query_vectors = {spec["oznaka"]: embed_text(spec["tekst_upita"]) for spec in QUERY_SPECS}

    with psycopg2.connect(**POSTGRES_CONFIG) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT max(id_rac) FROM Racun")
            max_account_id = cur.fetchone()[0] or 1

        drop_pg_indexes(pg_conn)
        exact_results = {}

        for spec in QUERY_SPECS:
            query_vector = query_vectors[spec["oznaka"]]
            candidate_limit = max(args.k * spec["kandidat_mnozilac"], args.k)

            samples, rows = measure_many(
                lambda spec=spec, query_vector=query_vector, candidate_limit=candidate_limit: run_pg_query(
                    pg_conn, spec, query_vector, args.k, candidate_limit
                ),
                args.ponavljanja,
                args.zagrevanje,
            )
            exact_results[spec["oznaka"]] = [row["entity_id"] for row in rows]
            summary_rows.append({
                "vreme_pokretanja": run_started,
                "scale": args.scale,
                "oznaka_upita": spec["oznaka"],
                "naziv_upita": spec["naziv"],
                "metod": "pg_exact",
                "parametri": "exact",
                **summarize_samples(samples),
                "build_ms": 0.0,
                "index_size_bytes": 0,
                "insert_ms": 0.0,
                "recall_at_k": 1.0,
                "overlap_at_k": 1.0,
            })
            append_detail_rows(detail_rows, run_started, args.scale, spec, "pg_exact", rows, "exact")

        insert_rows = sample_insert_rows(args.insert_count, max_account_id)
        for config in pg_hnsw_configs(args):
            drop_pg_indexes(pg_conn)
            build_ms, size_bytes = create_pg_hnsw_index(pg_conn, config["m"], config["ef_construction"])
            insert_ms = measure_pg_insert(pg_conn, insert_rows)
            parametri = (
                f"m={config['m']};ef_construction={config['ef_construction']};"
                f"ef_search={config['ef_search']}"
            )

            for spec in QUERY_SPECS:
                query_vector = query_vectors[spec["oznaka"]]
                candidate_limit = max(args.k * spec["kandidat_mnozilac"], args.k)
                samples, rows = measure_many(
                    lambda spec=spec, query_vector=query_vector, candidate_limit=candidate_limit, config=config: run_pg_query(
                        pg_conn,
                        spec,
                        query_vector,
                        args.k,
                        candidate_limit,
                        [f"SET hnsw.ef_search = {config['ef_search']}"],
                    ),
                    args.ponavljanja,
                    args.zagrevanje,
                )
                ids = [row["entity_id"] for row in rows]
                summary_rows.append({
                    "vreme_pokretanja": run_started,
                    "scale": args.scale,
                    "oznaka_upita": spec["oznaka"],
                    "naziv_upita": spec["naziv"],
                    "metod": "pg_hnsw",
                    "parametri": parametri,
                    **summarize_samples(samples),
                    "build_ms": round(build_ms, 3),
                    "index_size_bytes": size_bytes,
                    "insert_ms": insert_ms,
                    "recall_at_k": recall_at_k(exact_results[spec["oznaka"]], ids, args.k),
                    "overlap_at_k": overlap_at_k(exact_results[spec["oznaka"]], ids, args.k),
                })
                append_detail_rows(detail_rows, run_started, args.scale, spec, "pg_hnsw", rows, parametri)

        for config in pg_ivf_configs(args):
            drop_pg_indexes(pg_conn)
            build_ms, size_bytes = create_pg_ivfflat_index(pg_conn, config["lists"])
            insert_ms = measure_pg_insert(pg_conn, insert_rows)
            parametri = f"lists={config['lists']};probes={config['probes']}"

            for spec in QUERY_SPECS:
                query_vector = query_vectors[spec["oznaka"]]
                candidate_limit = max(args.k * spec["kandidat_mnozilac"], args.k)
                samples, rows = measure_many(
                    lambda spec=spec, query_vector=query_vector, candidate_limit=candidate_limit, config=config: run_pg_query(
                        pg_conn,
                        spec,
                        query_vector,
                        args.k,
                        candidate_limit,
                        [f"SET ivfflat.probes = {config['probes']}"],
                    ),
                    args.ponavljanja,
                    args.zagrevanje,
                )
                ids = [row["entity_id"] for row in rows]
                summary_rows.append({
                    "vreme_pokretanja": run_started,
                    "scale": args.scale,
                    "oznaka_upita": spec["oznaka"],
                    "naziv_upita": spec["naziv"],
                    "metod": "pg_ivfflat",
                    "parametri": parametri,
                    **summarize_samples(samples),
                    "build_ms": round(build_ms, 3),
                    "index_size_bytes": size_bytes,
                    "insert_ms": insert_ms,
                    "recall_at_k": recall_at_k(exact_results[spec["oznaka"]], ids, args.k),
                    "overlap_at_k": overlap_at_k(exact_results[spec["oznaka"]], ids, args.k),
                })
                append_detail_rows(detail_rows, run_started, args.scale, spec, "pg_ivfflat", rows, parametri)

        drop_pg_indexes(pg_conn)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    try:
        with driver.session() as session:
            drop_neo4j_index(session)
            insert_rows = sample_insert_rows(args.insert_count, max_account_id)

            for config in neo4j_configs(args):
                drop_neo4j_index(session)
                build_ms = create_neo4j_index(
                    session,
                    config["m"],
                    config["ef_construction"],
                    parse_bool(config["quantization"]),
                )
                insert_ms = measure_neo4j_insert(session, insert_rows)
                parametri = (
                    f"m={config['m']};ef_construction={config['ef_construction']};"
                    f"quantization={config['quantization']}"
                )

                for spec in QUERY_SPECS:
                    query_vector = query_vectors[spec["oznaka"]]
                    candidate_limit = max(args.k * spec["kandidat_mnozilac"], args.k)
                    samples, rows = measure_many(
                        lambda spec=spec, query_vector=query_vector, candidate_limit=candidate_limit: run_neo4j_query(
                            session, spec, query_vector, args.k, candidate_limit
                        ),
                        args.ponavljanja,
                        args.zagrevanje,
                    )
                    ids = [row["entity_id"] for row in rows]
                    summary_rows.append({
                        "vreme_pokretanja": run_started,
                        "scale": args.scale,
                        "oznaka_upita": spec["oznaka"],
                        "naziv_upita": spec["naziv"],
                        "metod": "neo4j_hnsw",
                        "parametri": parametri,
                        **summarize_samples(samples),
                        "build_ms": round(build_ms, 3),
                        "index_size_bytes": "",
                        "insert_ms": insert_ms,
                        "recall_at_k": recall_at_k(exact_results[spec["oznaka"]], ids, args.k),
                        "overlap_at_k": overlap_at_k(exact_results[spec["oznaka"]], ids, args.k),
                    })
                    append_detail_rows(detail_rows, run_started, args.scale, spec, "neo4j_hnsw", rows, parametri)

            drop_neo4j_index(session)
    finally:
        driver.close()

    save_summary(summary_rows)
    save_details(detail_rows)
    print(f"Sacuvan rezime: {SUMMARY_CSV}")
    print(f"Sacuvani detalji: {DETAILS_CSV}")


if __name__ == "__main__":
    main()
