#!/usr/bin/env python3
"""
Crta grafikone za benchmark vektorskih indeksa.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT_DIR / "rezultati" / "vektorski_benchmark" / "rezime.csv"
OUTPUT_DIR = ROOT_DIR / "rezultati" / "vektorski_benchmark" / "grafikoni"


def load_rows() -> list[dict]:
    with INPUT_CSV.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({
                **row,
                "avg_ms": float(row["avg_ms"]),
                "p50_ms": float(row["p50_ms"]),
                "p95_ms": float(row["p95_ms"]),
                "build_ms": float(row["build_ms"]),
                "index_size_bytes": float(row["index_size_bytes"] or 0),
                "insert_ms": float(row["insert_ms"]),
                "recall_at_k": float(row["recall_at_k"]),
                "overlap_at_k": float(row["overlap_at_k"]),
            })
        return rows


def latest_rows(rows: list[dict]) -> list[dict]:
    latest = {}
    for row in rows:
        key = (row["oznaka_upita"], row["metod"])
        latest[key] = row
    return list(latest.values())


def draw_query_latency(rows: list[dict], metric: str, output_name: str) -> None:
    methods = ["pg_exact", "pg_hnsw", "pg_ivfflat", "neo4j_hnsw"]
    labels = [row["oznaka_upita"] for row in rows if row["metod"] == "pg_exact"]
    labels = sorted(set(labels))
    x = list(range(len(labels)))
    width = 0.2

    plt.figure(figsize=(11, 6))
    for index, method in enumerate(methods):
        values = []
        for label in labels:
            row = next(item for item in rows if item["oznaka_upita"] == label and item["metod"] == method)
            values.append(row[metric])
        offsets = [item + (index - 1.5) * width for item in x]
        plt.bar(offsets, values, width=width, label=method)

    plt.title(f"Upitna latencija ({metric})")
    plt.xlabel("Upit")
    plt.ylabel("Vreme (ms)")
    plt.xticks(x, labels)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def draw_global_metric(rows: list[dict], metric: str, title: str, output_name: str) -> None:
    methods = ["pg_hnsw", "pg_ivfflat", "neo4j_hnsw"]
    seen = {}
    for row in rows:
        if row["metod"] in methods and row["metod"] not in seen:
            seen[row["metod"]] = row[metric]

    plt.figure(figsize=(8, 5))
    plt.bar(list(seen.keys()), list(seen.values()))
    plt.title(title)
    plt.ylabel(metric)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def draw_quality(rows: list[dict], metric: str, title: str, output_name: str) -> None:
    methods = ["pg_hnsw", "pg_ivfflat", "neo4j_hnsw"]
    labels = sorted({row["oznaka_upita"] for row in rows})
    x = list(range(len(labels)))
    width = 0.25

    plt.figure(figsize=(10, 6))
    for index, method in enumerate(methods):
        values = []
        for label in labels:
            row = next(item for item in rows if item["oznaka_upita"] == label and item["metod"] == method)
            values.append(row[metric])
        offsets = [item + (index - 1) * width for item in x]
        plt.bar(offsets, values, width=width, label=method)

    plt.title(title)
    plt.xlabel("Upit")
    plt.ylabel(metric)
    plt.xticks(x, labels)
    plt.ylim(0, 1.05)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = latest_rows(load_rows())

    draw_query_latency(rows, "p50_ms", "latencija_p50.png")
    draw_query_latency(rows, "p95_ms", "latencija_p95.png")
    draw_global_metric(rows, "build_ms", "Vreme kreiranja indeksa", "build_time.png")
    draw_global_metric(rows, "index_size_bytes", "Velicina indeksa", "index_size.png")
    draw_global_metric(rows, "insert_ms", "Vreme inserta novih transakcija", "insert_time.png")
    draw_quality(rows, "recall_at_k", "Recall@k po metodi", "recall.png")
    draw_quality(rows, "overlap_at_k", "Overlap top-k po metodi", "overlap.png")

    print(f"Grafikoni su sacuvani u: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
