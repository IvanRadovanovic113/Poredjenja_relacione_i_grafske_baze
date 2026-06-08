#!/usr/bin/env python3
"""
Loads generated JSON data into Neo4j.

Usage:
    python neo4j/load.py --scale 15000
"""
import argparse
import json
import os
import sys
import time

from neo4j import GraphDatabase

NEO4J_URI  = os.environ.get('NEO4J_URI',  'bolt://localhost:7687')
NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
NEO4J_PASS = os.environ.get('NEO4J_PASS', 'bankdb123')

CONSTRAINTS_PATH = os.path.join(os.path.dirname(__file__), 'constraints.cypher')
BATCH_SIZE = 500


def load_json(scale, name):
    path = os.path.join('data', str(scale), f'{name}.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def batched(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def run_batched(session, query, rows):
    for batch in batched(rows, BATCH_SIZE):
        session.run(query, rows=batch)


def load_all(scale):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    with driver.session() as session:
        print("  Clearing database...")
        session.run("MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS")

        print("  Creating constraints/indexes...")
        with open(CONSTRAINTS_PATH, encoding='utf-8') as f:
            for stmt in f.read().split(';'):
                stmt = stmt.strip()
                if stmt:
                    session.run(stmt)

        start = time.perf_counter()

        # --- Nodes ---
        filijale = load_json(scale, 'filijale')
        run_batched(session,
            "UNWIND $rows AS r CREATE (:Filijala {id_fil: r.id_fil, naziv_fil: r.naziv_fil, adresa_fil: r.adresa_fil, grad_fil: r.grad_fil})",
            filijale)
        print(f"  :Filijala      {len(filijale):>7} nodes")

        bankomati = load_json(scale, 'bankomati')
        run_batched(session,
            "UNWIND $rows AS r CREATE (:Bankomat {id_bank: r.id_bank, lokacija_bank: r.lokacija_bank, grad_bank: r.grad_bank})",
            bankomati)
        print(f"  :Bankomat      {len(bankomati):>7} nodes")

        klijenti = load_json(scale, 'klijenti')
        run_batched(session,
            """UNWIND $rows AS r
               CREATE (:Klijent {
                   id_kli: r.id_kli, ime_kli: r.ime_kli, prezime_kli: r.prezime_kli,
                   email_kli: r.email_kli, datum_reg_kli: r.datum_reg_kli,
                   jmbg_kli: r.jmbg_kli, telefon_kli: r.telefon_kli,
                   adresa_kli: r.adresa_kli, grad_kli: r.grad_kli,
                   datum_rodj_kli: r.datum_rodj_kli, tip_kli: r.tip_kli
               })""",
            klijenti)
        print(f"  :Klijent       {len(klijenti):>7} nodes")

        racuni = load_json(scale, 'racuni')
        run_batched(session,
            """UNWIND $rows AS r
               CREATE (:Racun {
                   id_rac: r.id_rac, broj_rac: r.broj_rac, tip_rac: r.tip_rac,
                   saldo_rac: r.saldo_rac, valuta_rac: r.valuta_rac,
                   datum_otavaranja_rac: r.datum_otavaranja_rac, limit_rac: r.limit_rac
               })""",
            racuni)
        print(f"  :Racun         {len(racuni):>7} nodes")

        kartice = load_json(scale, 'kartice')
        run_batched(session,
            """UNWIND $rows AS r
               CREATE (:Kartica {
                   id_kar: r.id_kar, broj_kar: r.broj_kar, tip_kar: r.tip_kar,
                   datum_isteka_kar: r.datum_isteka_kar,
                   datum_izdavanja_kar: r.datum_izdavanja_kar, CCV_kar: r.CCV_kar
               })""",
            kartice)
        print(f"  :Kartica       {len(kartice):>7} nodes")

        transakcije = load_json(scale, 'transakcije')

        # --- Relationships ---
        # Klijent -[:POSEDUJE]-> Racun
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (k:Klijent {id_kli: r.id_kli}), (ra:Racun {id_rac: r.id_rac})
               CREATE (k)-[:POSEDUJE]->(ra)""",
            [{'id_kli': r['id_kli'], 'id_rac': r['id_rac']} for r in racuni])
        print(f"  [:POSEDUJE]    {len(racuni):>7} rels")

        # Racun -[:OTVOREN_U]-> Filijala (only where id_fil is not null)
        otvoren_u = [{'id_rac': r['id_rac'], 'id_fil': r['id_fil']}
                     for r in racuni if r['id_fil'] is not None]
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (ra:Racun {id_rac: r.id_rac}), (f:Filijala {id_fil: r.id_fil})
               CREATE (ra)-[:OTVOREN_U]->(f)""",
            otvoren_u)
        print(f"  [:OTVOREN_U]   {len(otvoren_u):>7} rels")

        # Racun -[:IMA]-> Kartica
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (ra:Racun {id_rac: r.id_rac}), (k:Kartica {id_kar: r.id_kar})
               CREATE (ra)-[:IMA]->(k)""",
            [{'id_rac': r['id_rac'], 'id_kar': r['id_kar']} for r in kartice])
        print(f"  [:IMA]         {len(kartice):>7} rels")

        # Racun -[:TRANSAKCIJA]-> Racun  (transakcija je ivica, ne cvor)
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (platilac:Racun {id_rac: r.id_rac_platilac}),
                     (primalac:Racun {id_rac: r.id_rac_primalac})
               CREATE (platilac)-[:TRANSAKCIJA {
                   id_trans: r.id_trans,
                   iznos_trans: r.iznos_trans,
                   datum_vreme_trans: r.datum_vreme_trans,
                   opis_trans: r.opis_trans,
                   status_trans: r.status_trans,
                   semanticka_grupa_trans: r.semanticka_grupa_trans,
                   embedding_trans: r.embedding_trans
               }]->(primalac)""",
            transakcije)
        print(f"  [:TRANSAKCIJA] {len(transakcije):>7} rels")

        ima_punomoc = load_json(scale, 'ima_punomoc')
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (k:Klijent {id_kli: r.id_kli}), (ra:Racun {id_rac: r.id_rac})
               CREATE (k)-[:IMA_PUNOMOC {datum_dodele: r.datum_dodele, nivo_pristupa: r.nivo_pristupa}]->(ra)""",
            ima_punomoc)
        print(f"  [:IMA_PUNOMOC] {len(ima_punomoc):>7} rels")

        gotovinska = load_json(scale, 'gotovinska_trans')
        run_batched(session,
            """UNWIND $rows AS r
               MATCH (ra:Racun {id_rac: r.id_rac}), (b:Bankomat {id_bank: r.id_bank})
               CREATE (ra)-[:GOTOVINSKA_TRANS {tip_got_trans: r.tip_got_trans}]->(b)""",
            gotovinska)
        print(f"  [:GOT_TRANS]   {len(gotovinska):>7} rels")

        elapsed = time.perf_counter() - start

    driver.close()
    return elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', type=int, default=15000)
    args = parser.parse_args()

    print(f"Loading Neo4j (scale={args.scale})...")
    try:
        elapsed = load_all(args.scale)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Run generate.py first.")
        sys.exit(1)
    print(f"Neo4j load time: {elapsed:.2f}s")


if __name__ == '__main__':
    main()
