#!/usr/bin/env python3
"""
Crta grafikone za benchmark vektorskih indeksa.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT_DIR / "rezultati" / "vektorski_benchmark" / "rezime.csv"
OUTPUT_DIR = ROOT_DIR / "rezultati" / "vektorski_benchmark" / "grafikoni"

METHODS = ["pg_exact", "pg_hnsw", "pg_ivfflat", "neo4j_hnsw"]
INDEX_METHODS = ["pg_hnsw", "pg_ivfflat", "neo4j_hnsw"]
METHOD_TITLES = {
    "pg_exact": "PostgreSQL exact",
    "pg_hnsw": "PostgreSQL HNSW",
    "pg_ivfflat": "PostgreSQL IVFFlat",
    "neo4j_hnsw": "Neo4j HNSW",
}


def load_rows() -> list[dict]:
    with INPUT_CSV.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({
                **row,
                "scale": int(row["scale"]),
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


def latest_rows_by_scale(rows: list[dict]) -> list[dict]:
    latest_per_scale = {}
    for row in rows:
        scale = row["scale"]
        latest_per_scale[scale] = max(latest_per_scale.get(scale, ""), row["vreme_pokretanja"])
    return [row for row in rows if row["vreme_pokretanja"] == latest_per_scale[row["scale"]]]


def best_rows(rows: list[dict], metric: str = "p50_ms") -> list[dict]:
    best = {}
    for row in rows:
        key = (row["scale"], row["oznaka_upita"], row["metod"])
        current = best.get(key)
        if current is None or row[metric] < current[metric]:
            best[key] = row
    return list(best.values())


def grouped(rows: list[dict], key_name: str) -> dict:
    result = defaultdict(list)
    for row in rows:
        result[row[key_name]].append(row)
    return result


def draw_query_latency(rows: list[dict], metric: str, output_name: str, scale: int) -> None:
    labels = sorted({row["oznaka_upita"] for row in rows})
    x = list(range(len(labels)))
    width = 0.2

    plt.figure(figsize=(12, 6))
    for index, method in enumerate(METHODS):
        method_rows = [row for row in rows if row["metod"] == method]
        if not method_rows:
            continue
        values = []
        for label in labels:
            row = next(item for item in method_rows if item["oznaka_upita"] == label)
            values.append(row[metric])
        offsets = [item + (index - 1.5) * width for item in x]
        plt.bar(offsets, values, width=width, label=METHOD_TITLES[method])

    plt.title(f"Latencija po upitu ({metric}, scale={scale})")
    plt.xlabel("Upit")
    plt.ylabel("Vreme (ms)")
    plt.xticks(x, labels)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def draw_index_size(rows: list[dict], scale: int) -> None:
    methods = ["pg_hnsw", "pg_ivfflat"]
    values = {}
    for method in methods:
        method_rows = [row for row in rows if row["metod"] == method]
        if not method_rows:
            continue
        values[method] = min(method_rows, key=lambda row: row["build_ms"])["index_size_bytes"]

    if not values:
        return

    plt.figure(figsize=(8, 5))
    plt.bar([METHOD_TITLES[key] for key in values], list(values.values()))
    plt.title(f"Veličina indeksa na disku (scale={scale})")
    plt.ylabel("Bajtovi")
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"index_size_scale_{scale}.png", dpi=300)
    plt.close()


def draw_global_metric(rows: list[dict], metric: str, title: str, output_name: str, scale: int) -> None:
    values = {}
    for method in INDEX_METHODS:
        method_rows = [row for row in rows if row["metod"] == method]
        if not method_rows:
            continue
        values[method] = min(method_rows, key=lambda row: row["p50_ms"])[metric]

    if not values:
        return

    plt.figure(figsize=(8, 5))
    plt.bar([METHOD_TITLES[key] for key in values], list(values.values()))
    plt.title(f"{title} (scale={scale})")
    plt.ylabel(metric)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def draw_quality(rows: list[dict], metric: str, title: str, output_name: str, scale: int) -> None:
    labels = sorted({row["oznaka_upita"] for row in rows})
    x = list(range(len(labels)))
    width = 0.25

    plt.figure(figsize=(11, 6))
    for index, method in enumerate(INDEX_METHODS):
        method_rows = [row for row in rows if row["metod"] == method]
        if not method_rows:
            continue
        best_per_query = {
            row["oznaka_upita"]: min(
                [item for item in method_rows if item["oznaka_upita"] == row["oznaka_upita"]],
                key=lambda item: item["p50_ms"],
            )
            for row in method_rows
        }
        values = [best_per_query[label][metric] for label in labels]
        offsets = [item + (index - 1) * width for item in x]
        plt.bar(offsets, values, width=width, label=METHOD_TITLES[method])

    plt.title(f"{title} (scale={scale})")
    plt.xlabel("Upit")
    plt.ylabel(metric)
    plt.xticks(x, labels)
    plt.ylim(0, 1.05)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=300)
    plt.close()


def draw_parameter_metric(rows: list[dict], method: str, metric: str, scale: int) -> None:
    method_rows = [row for row in rows if row["metod"] == method]
    if not method_rows:
        return

    ordered_params = list(dict.fromkeys(row["parametri"] for row in method_rows))
    labels = sorted({row["oznaka_upita"] for row in method_rows})

    plt.figure(figsize=(max(12, len(ordered_params) * 2), 6))
    for label in labels:
        values = []
        for param in ordered_params:
            matches = [
                row for row in method_rows
                if row["oznaka_upita"] == label and row["parametri"] == param
            ]
            if not matches:
                values.append(None)
            else:
                values.append(matches[0][metric])
        plt.plot(ordered_params, values, marker="o", label=label)

    plt.title(f"{METHOD_TITLES[method]}: {metric} po konfiguraciji (scale={scale})")
    plt.xlabel("Parametri")
    plt.ylabel(metric)
    plt.xticks(rotation=20, ha="right")
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend(title="Upit")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{method}_{metric}_scale_{scale}.png", dpi=300)
    plt.close()


def draw_build_insert_by_config(rows: list[dict], method: str, scale: int) -> None:
    method_rows = [row for row in rows if row["metod"] == method]
    if not method_rows:
        return

    unique_rows = {}
    for row in method_rows:
        unique_rows[row["parametri"]] = row
    ordered_params = list(unique_rows.keys())
    build_values = [unique_rows[param]["build_ms"] for param in ordered_params]
    insert_values = [unique_rows[param]["insert_ms"] for param in ordered_params]
    x = list(range(len(ordered_params)))
    width = 0.35

    plt.figure(figsize=(max(12, len(ordered_params) * 2), 6))
    plt.bar([item - width / 2 for item in x], build_values, width=width, label="build_ms")
    plt.bar([item + width / 2 for item in x], insert_values, width=width, label="insert_ms")
    plt.title(f"{METHOD_TITLES[method]}: build i insert po konfiguraciji (scale={scale})")
    plt.xlabel("Parametri")
    plt.ylabel("Vreme (ms)")
    plt.xticks(x, ordered_params, rotation=20, ha="right")
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{method}_build_insert_scale_{scale}.png", dpi=300)
    plt.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = latest_rows_by_scale(load_rows())

    for scale, scale_rows in grouped(rows, "scale").items():
        best_scale_rows = best_rows(scale_rows)
        draw_query_latency(best_scale_rows, "p50_ms", f"latencija_p50_scale_{scale}.png", scale)
        draw_query_latency(best_scale_rows, "p95_ms", f"latencija_p95_scale_{scale}.png", scale)
        draw_global_metric(scale_rows, "build_ms", "Vreme kreiranja indeksa", f"build_time_scale_{scale}.png", scale)
        draw_index_size(scale_rows, scale)
        draw_global_metric(scale_rows, "insert_ms", "Vreme inserta novih transakcija", f"insert_time_scale_{scale}.png", scale)
        draw_quality(scale_rows, "recall_at_k", "Recall@k po metodi", f"recall_scale_{scale}.png", scale)
        draw_quality(scale_rows, "overlap_at_k", "Overlap top-k po metodi", f"overlap_scale_{scale}.png", scale)

        for method in INDEX_METHODS:
            draw_parameter_metric(scale_rows, method, "p50_ms", scale)
            draw_parameter_metric(scale_rows, method, "p95_ms", scale)
            draw_parameter_metric(scale_rows, method, "recall_at_k", scale)
            draw_parameter_metric(scale_rows, method, "overlap_at_k", scale)
            draw_build_insert_by_config(scale_rows, method, scale)

    print(f"Grafikoni su sacuvani u: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
