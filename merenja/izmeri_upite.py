#!/usr/bin/env python3
"""
Skripta za merenje vremena izvrsavanja upita nad PostgreSQL i Neo4j bazom.

Pre pokretanja:
1. Pokrenuti kontejnere:
   docker compose up -d

2. Napuniti baze podacima, na primer:
   docker compose run --rm loader python run.py --scale 150

3. Pokrenuti ovu skriptu lokalno:
   python merenja/izmeri_upite.py --scale 150

Rezultat se cuva u:
rezultati/sirovi/rezultati_upita.csv
"""

import argparse
import csv
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

import psycopg2
from neo4j import GraphDatabase


ROOT_DIR = Path(__file__).resolve().parents[1]

POSTGRES_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "bankdb"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
}

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "bankdb123")

UPITI = [
    {
        "oznaka": "U1",
        "naziv": "Promet izmedju filijala",
        "postgresql": ROOT_DIR / "upiti" / "postgresql" / "u1_promet_izmedju_filijala.sql",
        "neo4j": ROOT_DIR / "upiti" / "neo4j" / "u1_promet_izmedju_filijala.cypher",
    },
    {
        "oznaka": "U2",
        "naziv": "Najaktivniji klijenti",
        "postgresql": ROOT_DIR / "upiti" / "postgresql" / "u2_najaktivniji_klijenti.sql",
        "neo4j": ROOT_DIR / "upiti" / "neo4j" / "u2_najaktivniji_klijenti.cypher",
    },
]


def procitaj_fajl(putanja: Path) -> str:
    if not putanja.exists():
        raise FileNotFoundError(f"Ne postoji fajl: {putanja}")

    return putanja.read_text(encoding="utf-8").strip()


def pripremi_cypher_upit(sadrzaj: str) -> str:
    """
    Neo4j Python driver ne zahteva ; na kraju upita.
    Ako postoji, uklanja se.
    """
    return sadrzaj.rstrip().rstrip(";")


def podeli_cypher_indekse(sadrzaj: str) -> list[str]:
    """
    Iz fajla indeksi.cypher izvlaci pojedinacne CREATE INDEX naredbe.

    Podrzava format u kome su naredbe napisane kroz vise linija,
    na primer:

    CREATE INDEX naziv_indeksa IF NOT EXISTS
    FOR (n:Labela)
    ON (n.atribut);
    """
    naredbe = []
    trenutna_naredba = []

    for linija in sadrzaj.splitlines():
        linija = linija.strip()

        if not linija or linija.startswith("//"):
            continue

        if linija.upper().startswith("CREATE ") and trenutna_naredba:
            naredbe.append(" ".join(trenutna_naredba).rstrip(";"))
            trenutna_naredba = []

        trenutna_naredba.append(linija)

        if linija.endswith(";"):
            naredbe.append(" ".join(trenutna_naredba).rstrip(";"))
            trenutna_naredba = []

    if trenutna_naredba:
        naredbe.append(" ".join(trenutna_naredba).rstrip(";"))

    return naredbe


def kreiraj_postgresql_indekse() -> None:
    putanja = ROOT_DIR / "upiti" / "postgresql" / "indeksi.sql"
    sql = procitaj_fajl(putanja)

    with psycopg2.connect(**POSTGRES_CONFIG) as konekcija:
        konekcija.autocommit = True

        with konekcija.cursor() as kursor:
            kursor.execute(sql)

    print("PostgreSQL indeksi su kreirani.")


def kreiraj_neo4j_indekse() -> None:
    putanja = ROOT_DIR / "upiti" / "neo4j" / "indeksi.cypher"
    sadrzaj = procitaj_fajl(putanja)
    naredbe = podeli_cypher_indekse(sadrzaj)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    try:
        with driver.session() as sesija:
            for naredba in naredbe:
                sesija.run(naredba).consume()

            sesija.run("CALL db.awaitIndexes(300)").consume()
    finally:
        driver.close()

    print("Neo4j indeksi su kreirani.")


def izmeri_postgresql_upit(konekcija, sql: str) -> tuple[float, int]:
    """
    Meri samo vreme izvrsavanja SQL upita.
    Konekcija se ne otvara ovde, vec se prosledjuje spolja,
    kako se vreme konekcije ne bi racunalo u rezultat.
    """
    pocetak = time.perf_counter()

    with konekcija.cursor() as kursor:
        kursor.execute(sql)
        redovi = kursor.fetchall()

    trajanje_ms = (time.perf_counter() - pocetak) * 1000
    return trajanje_ms, len(redovi)


def izmeri_neo4j_upit(sesija, cypher: str) -> tuple[float, int]:
    """
    Meri samo vreme izvrsavanja Cypher upita.
    Neo4j sesija se ne otvara ovde, vec se prosledjuje spolja,
    kako se vreme otvaranja driver-a/sesije ne bi racunalo u rezultat.
    """
    pocetak = time.perf_counter()

    rezultat = sesija.run(cypher)
    redovi = list(rezultat)

    trajanje_ms = (time.perf_counter() - pocetak) * 1000
    return trajanje_ms, len(redovi)


def izmeri_vise_puta(
    baza: str,
    konekcija_ili_sesija,
    oznaka_upita: str,
    naziv_upita: str,
    upit: str,
    broj_ponavljanja: int,
    broj_zagrevanja: int,
) -> dict:
    vremena = []
    broj_redova = 0

    ukupno = broj_zagrevanja + broj_ponavljanja

    for i in range(ukupno):
        if baza == "PostgreSQL":
            trajanje_ms, broj_redova = izmeri_postgresql_upit(konekcija_ili_sesija, upit)
        elif baza == "Neo4j":
            trajanje_ms, broj_redova = izmeri_neo4j_upit(konekcija_ili_sesija, upit)
        else:
            raise ValueError(f"Nepoznata baza: {baza}")

        if i >= broj_zagrevanja:
            vremena.append(trajanje_ms)

    return {
        "baza": baza,
        "oznaka_upita": oznaka_upita,
        "naziv_upita": naziv_upita,
        "broj_redova": broj_redova,
        "broj_ponavljanja": broj_ponavljanja,
        "min_ms": round(min(vremena), 3),
        "max_ms": round(max(vremena), 3),
        "prosek_ms": round(statistics.mean(vremena), 3),
        "medijana_ms": round(statistics.median(vremena), 3),
    }


def sacuvaj_rezultate(scale: int, rezultati: list[dict]) -> Path:
    izlazni_folder = ROOT_DIR / "rezultati" / "sirovi"
    izlazni_folder.mkdir(parents=True, exist_ok=True)

    izlazni_fajl = izlazni_folder / "rezultati_upita.csv"
    fajl_postoji = izlazni_fajl.exists()

    kolone = [
        "vreme_pokretanja",
        "scale",
        "baza",
        "oznaka_upita",
        "naziv_upita",
        "broj_redova",
        "broj_ponavljanja",
        "min_ms",
        "max_ms",
        "prosek_ms",
        "medijana_ms",
    ]

    sada = datetime.now().isoformat(timespec="seconds")

    with izlazni_fajl.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=kolone)

        if not fajl_postoji:
            writer.writeheader()

        for rezultat in rezultati:
            writer.writerow({
                "vreme_pokretanja": sada,
                "scale": scale,
                **rezultat,
            })

    return izlazni_fajl


def prikazi_rezultate(rezultati: list[dict]) -> None:
    print("\nRezultati merenja:")
    print("-" * 100)
    print(f"{'Baza':<12} {'Upit':<4} {'Naziv':<32} {'Redova':>8} {'Prosek ms':>12} {'Medijana ms':>12}")
    print("-" * 100)

    for r in rezultati:
        print(
            f"{r['baza']:<12} "
            f"{r['oznaka_upita']:<4} "
            f"{r['naziv_upita']:<32} "
            f"{r['broj_redova']:>8} "
            f"{r['prosek_ms']:>12.3f} "
            f"{r['medijana_ms']:>12.3f}"
        )

    print("-" * 100)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        type=int,
        required=True,
        help="Velicina skupa podataka koja je prethodno ucitana, npr. 150, 15000 ili 100000.",
    )

    parser.add_argument(
        "--ponavljanja",
        type=int,
        default=10,
        help="Broj merenih ponavljanja po upitu. Podrazumevano: 10.",
    )

    parser.add_argument(
        "--zagrevanje",
        type=int,
        default=1,
        help="Broj pocetnih pokretanja koja se ne upisuju u rezultat. Podrazumevano: 1.",
    )

    parser.add_argument(
        "--bez-indeksa",
        action="store_true",
        help="Ako se navede ova opcija, skripta nece automatski kreirati indekse.",
    )

    args = parser.parse_args()

    if args.ponavljanja <= 0:
        raise ValueError("Broj ponavljanja mora biti veci od nule.")

    if args.zagrevanje < 0:
        raise ValueError("Broj pokretanja za zagrevanje ne moze biti negativan.")

    if not args.bez_indeksa:
        print("Kreiranje indeksa...")
        kreiraj_postgresql_indekse()
        kreiraj_neo4j_indekse()

    rezultati = []

    with psycopg2.connect(**POSTGRES_CONFIG) as pg_konekcija:
        pg_konekcija.autocommit = True

        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

        try:
            with neo4j_driver.session() as neo4j_sesija:
                for upit in UPITI:
                    print(f"\nMerenje {upit['oznaka']}: {upit['naziv']}")

                    sql = procitaj_fajl(upit["postgresql"])
                    cypher = pripremi_cypher_upit(procitaj_fajl(upit["neo4j"]))

                    rezultat_pg = izmeri_vise_puta(
                        baza="PostgreSQL",
                        konekcija_ili_sesija=pg_konekcija,
                        oznaka_upita=upit["oznaka"],
                        naziv_upita=upit["naziv"],
                        upit=sql,
                        broj_ponavljanja=args.ponavljanja,
                        broj_zagrevanja=args.zagrevanje,
                    )
                    rezultati.append(rezultat_pg)

                    rezultat_neo4j = izmeri_vise_puta(
                        baza="Neo4j",
                        konekcija_ili_sesija=neo4j_sesija,
                        oznaka_upita=upit["oznaka"],
                        naziv_upita=upit["naziv"],
                        upit=cypher,
                        broj_ponavljanja=args.ponavljanja,
                        broj_zagrevanja=args.zagrevanje,
                    )
                    rezultati.append(rezultat_neo4j)

        finally:
            neo4j_driver.close()

    prikazi_rezultate(rezultati)
    izlazni_fajl = sacuvaj_rezultate(args.scale, rezultati)

    print(f"\nRezultati su sacuvani u: {izlazni_fajl}")


if __name__ == "__main__":
    main()