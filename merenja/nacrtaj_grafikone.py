#!/usr/bin/env python3
"""
Skripta za crtanje grafikona na osnovu rezultata merenja.

Ulaz:
rezultati/sirovi/rezultati_upita.csv

Izlaz:
rezultati/grafikoni/u1_medijana.png
rezultati/grafikoni/u2_medijana.png
rezultati/grafikoni/u1_prosek.png
rezultati/grafikoni/u2_prosek.png
rezultati/grafikoni/odnos_brzine_medijana.png
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parents[1]

ULAZNI_FAJL = ROOT_DIR / "rezultati" / "sirovi" / "rezultati_upita.csv"
IZLAZNI_FOLDER = ROOT_DIR / "rezultati" / "grafikoni"


def ucitaj_rezultate() -> list[dict]:
    if not ULAZNI_FAJL.exists():
        raise FileNotFoundError(f"Ne postoji fajl sa rezultatima: {ULAZNI_FAJL}")

    rezultati = []

    with ULAZNI_FAJL.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for red in reader:
            rezultati.append({
                "vreme_pokretanja": red["vreme_pokretanja"],
                "scale": int(red["scale"]),
                "baza": red["baza"],
                "oznaka_upita": red["oznaka_upita"],
                "naziv_upita": red["naziv_upita"],
                "broj_redova": int(red["broj_redova"]),
                "broj_ponavljanja": int(red["broj_ponavljanja"]),
                "min_ms": float(red["min_ms"]),
                "max_ms": float(red["max_ms"]),
                "prosek_ms": float(red["prosek_ms"]),
                "medijana_ms": float(red["medijana_ms"]),
            })

    return rezultati


def uzmi_poslednja_merenja(rezultati: list[dict]) -> list[dict]:
    """
    Ako CSV sadrzi vise merenja za isti scale, bazu i upit,
    uzima se poslednje merenje.

    Ovo je korisno ako je skripta vise puta pokretana tokom testiranja.
    """
    poslednja = {}

    for red in rezultati:
        kljuc = (
            red["scale"],
            red["baza"],
            red["oznaka_upita"],
        )
        poslednja[kljuc] = red

    return list(poslednja.values())


def filtriraj_po_upitu(rezultati: list[dict], oznaka_upita: str) -> list[dict]:
    return [
        red for red in rezultati
        if red["oznaka_upita"] == oznaka_upita
    ]


def vrednost(rezultati: list[dict], scale: int, baza: str, kolona: str) -> float:
    for red in rezultati:
        if red["scale"] == scale and red["baza"] == baza:
            return red[kolona]

    raise ValueError(f"Nema rezultata za scale={scale}, baza={baza}, kolona={kolona}")


def nacrtaj_grafikon_za_upit(
    rezultati: list[dict],
    oznaka_upita: str,
    naziv_upita: str,
    kolona: str,
    naziv_kolone: str,
    izlazni_fajl: Path,
) -> None:
    rezultati_upita = filtriraj_po_upitu(rezultati, oznaka_upita)
    scale_vrednosti = sorted({red["scale"] for red in rezultati_upita})

    postgresql_vrednosti = [
        vrednost(rezultati_upita, scale, "PostgreSQL", kolona)
        for scale in scale_vrednosti
    ]

    neo4j_vrednosti = [
        vrednost(rezultati_upita, scale, "Neo4j", kolona)
        for scale in scale_vrednosti
    ]

    x = list(range(len(scale_vrednosti)))
    sirina = 0.35

    plt.figure(figsize=(10, 6))

    plt.bar(
        [i - sirina / 2 for i in x],
        postgresql_vrednosti,
        width=sirina,
        label="PostgreSQL",
    )

    plt.bar(
        [i + sirina / 2 for i in x],
        neo4j_vrednosti,
        width=sirina,
        label="Neo4j",
    )

    plt.title(f"{oznaka_upita} - {naziv_upita}")
    plt.xlabel("Velicina skupa podataka")
    plt.ylabel(f"{naziv_kolone} izvrsavanja (ms)")
    plt.xticks(x, [str(scale) for scale in scale_vrednosti])
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    plt.savefig(izlazni_fajl, dpi=300)
    plt.close()


def nacrtaj_odnos_brzine(rezultati: list[dict], izlazni_fajl: Path) -> None:
    """
    Crta koliko je puta Neo4j sporiji od PostgreSQL-a,
    na osnovu medijane vremena izvrsavanja.
    """
    oznake_upita = sorted({red["oznaka_upita"] for red in rezultati})
    scale_vrednosti = sorted({red["scale"] for red in rezultati})

    labele = []
    odnosi = []

    for oznaka_upita in oznake_upita:
        rezultati_upita = filtriraj_po_upitu(rezultati, oznaka_upita)

        for scale in scale_vrednosti:
            pg = vrednost(rezultati_upita, scale, "PostgreSQL", "medijana_ms")
            neo = vrednost(rezultati_upita, scale, "Neo4j", "medijana_ms")

            labele.append(f"{oznaka_upita}\n{scale}")
            odnosi.append(neo / pg)

    x = list(range(len(labele)))

    plt.figure(figsize=(11, 6))
    plt.bar(x, odnosi)

    plt.title("Koliko je puta Neo4j sporiji od PostgreSQL-a")
    plt.xlabel("Upit i velicina skupa podataka")
    plt.ylabel("Odnos medijana vremena izvrsavanja")
    plt.xticks(x, labele)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    plt.savefig(izlazni_fajl, dpi=300)
    plt.close()


def main() -> None:
    IZLAZNI_FOLDER.mkdir(parents=True, exist_ok=True)

    rezultati = ucitaj_rezultate()
    rezultati = uzmi_poslednja_merenja(rezultati)

    nacrtaj_grafikon_za_upit(
        rezultati=rezultati,
        oznaka_upita="U1",
        naziv_upita="Promet izmedju filijala",
        kolona="medijana_ms",
        naziv_kolone="Medijana vremena",
        izlazni_fajl=IZLAZNI_FOLDER / "u1_medijana.png",
    )

    nacrtaj_grafikon_za_upit(
        rezultati=rezultati,
        oznaka_upita="U2",
        naziv_upita="Najaktivniji klijenti",
        kolona="medijana_ms",
        naziv_kolone="Medijana vremena",
        izlazni_fajl=IZLAZNI_FOLDER / "u2_medijana.png",
    )

    nacrtaj_grafikon_za_upit(
        rezultati=rezultati,
        oznaka_upita="U1",
        naziv_upita="Promet izmedju filijala",
        kolona="prosek_ms",
        naziv_kolone="Prosecno vreme",
        izlazni_fajl=IZLAZNI_FOLDER / "u1_prosek.png",
    )

    nacrtaj_grafikon_za_upit(
        rezultati=rezultati,
        oznaka_upita="U2",
        naziv_upita="Najaktivniji klijenti",
        kolona="prosek_ms",
        naziv_kolone="Prosecno vreme",
        izlazni_fajl=IZLAZNI_FOLDER / "u2_prosek.png",
    )

    nacrtaj_odnos_brzine(
        rezultati=rezultati,
        izlazni_fajl=IZLAZNI_FOLDER / "odnos_brzine_medijana.png",
    )

    print("Grafikoni su uspesno generisani:")
    print(f"- {IZLAZNI_FOLDER / 'u1_medijana.png'}")
    print(f"- {IZLAZNI_FOLDER / 'u2_medijana.png'}")
    print(f"- {IZLAZNI_FOLDER / 'u1_prosek.png'}")
    print(f"- {IZLAZNI_FOLDER / 'u2_prosek.png'}")
    print(f"- {IZLAZNI_FOLDER / 'odnos_brzine_medijana.png'}")


if __name__ == "__main__":
    main()