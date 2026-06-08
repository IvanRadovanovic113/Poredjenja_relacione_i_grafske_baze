#!/usr/bin/env python3
"""
Helpers for generating semantically clustered Serbian transaction descriptions
and real embeddings via the djovak/embedic-base model.
"""
from __future__ import annotations

import os
import random
import re
from functools import lru_cache


EMBEDDING_DIM = 768
DEFAULT_EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL_NAME", "djovak/embedic-base")
DEFAULT_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "256"))

MESECI = [
    "januar", "februar", "mart", "april", "maj", "jun",
    "jul", "avgust", "septembar", "oktobar", "novembar", "decembar",
]

STANOVI = [
    "stan 12", "stan 14", "stan 18", "stan A3", "stan B7", "garsonjera",
    "lokal 2", "kancelarija 5", "poslovni prostor", "stan kod centra",
]

REZIJE = ["struja", "infostan", "komunalije", "voda", "grejanje", "internet"]
PRODAVCI = ["Maxi", "Idea", "Lidl", "Univerexport", "Aroma"]
PORODICA = ["mami", "tati", "bratu", "sestri", "ujaku", "tetki", "roditeljima"]
SKRACENICE = ["upl.", "trf.", "nalog", "prenos", "ispl."]


SEMANTIC_GROUPS = {
    "placanje_kirije": {
        "weight": 0.18,
        "templates": [
        "redovna mesečna uplata za zakup {objekat}",
        "uplata stanodavcu za korišćenje {objekat}",
        "plaćanje obaveze po ugovoru o najmu za {mesec}",
        "zakupnina za {objekat} za mesec {mesec}",
        "mesečni trošak stanovanja za {objekat}",
        "uplata za iznajmljeni {objekat} prema dogovorenom mesečnom iznosu",
        "plaćanje stanarine vlasniku za korišćenje {objekat}",
        "redovna uplata za najam {objekat} za mesec {mesec}",
        "mesečna obaveza za zakup prostora označenog kao {objekat}",
        "uplata zakupnine po osnovu korišćenja {objekat}",
        ],
        "amount_range": (22000, 78000),
        "status_weights": {"uspesna": 0.9, "na_cekanju": 0.08, "neuspesna": 0.02},
        "recent_probability": 0.8,
    },
    "pozajmica": {
        "weight": 0.1,
        "templates": [
            "pozajmica za {razlog}",
            "vraćanje pozajmice",
            "privatna pozajmica",
            "pomoć prijatelju",
            "vraćam dug za {razlog}",
        ],
        "amount_range": (3000, 60000),
        "status_weights": {"uspesna": 0.82, "na_cekanju": 0.11, "neuspesna": 0.07},
        "recent_probability": 0.55,
    },
    "neobican_transfer": {
        "weight": 0.08,
        "templates": [
        "neuobičajen prenos većeg iznosa između povezanih računa",
        "uplata koja odstupa od uobičajenog obrasca transakcija",
        "prenos sredstava bez jasne poslovne ili lične osnove",
        "hitna transakcija između računa sa prethodnim međusobnim uplatama",
        "sumnjiv transfer povezan sa kružnim tokom novca",
        "prenos novca izvršen po internom dogovoru bez standardnog opisa",
        "neuobičajena uplata između računa koji često razmenjuju sredstva",
        "transfer sredstava koji se ne uklapa u redovne aktivnosti klijenta",
        "specifičan prenos novca između računa sa mogućom međusobnom povezanošću",
        "uplata većeg iznosa koja zahteva dodatnu proveru porekla sredstava",
        ],
        "amount_range": (12000, 140000),
        "status_weights": {"uspesna": 0.84, "na_cekanju": 0.1, "neuspesna": 0.06},
        "recent_probability": 0.65,
    },
    "sumnjiva_uplata": {
        "weight": 0.06,
        "templates": [
            "sumnjiva uplata",
            "uplata bez jasnog osnova",
            "gotovinska uplata trećeg lica",
            "uplata bez dodatnog objašnjenja",
            "prenos nepoznatog porekla",
        ],
        "amount_range": (5000, 180000),
        "status_weights": {"uspesna": 0.7, "na_cekanju": 0.18, "neuspesna": 0.12},
        "recent_probability": 0.7,
    },
    "hitna_uplata": {
        "weight": 0.08,
        "templates": [
            "hitna uplata",
            "urgentna uplata dobavljaču",
            "uplata odmah po nalogu",
            "prioritetno plaćanje",
            "hitno plaćanje obaveze",
        ],
        "amount_range": (2500, 90000),
        "status_weights": {"uspesna": 0.78, "na_cekanju": 0.17, "neuspesna": 0.05},
        "recent_probability": 0.75,
    },
    "rezije": {
        "weight": 0.12,
        "templates": [
            "plaćanje računa za {rezija}",
            "uplata za {rezija}",
            "mesečni trošak za {rezija}",
            "račun za {rezija}",
            "{rezija} mesečna obaveza",
        ],
        "amount_range": (1200, 22000),
        "status_weights": {"uspesna": 0.94, "na_cekanju": 0.05, "neuspesna": 0.01},
        "recent_probability": 0.82,
    },
    "kupovina": {
        "weight": 0.14,
        "templates": [
            "kupovina u {prodavac}",
            "plaćanje karticom u {prodavac}",
            "račun za kupovinu",
            "dnevna nabavka u {prodavac}",
            "kupovina namirnica",
        ],
        "amount_range": (300, 16000),
        "status_weights": {"uspesna": 0.95, "na_cekanju": 0.03, "neuspesna": 0.02},
        "recent_probability": 0.88,
    },
    "zarada": {
        "weight": 0.08,
        "templates": [
            "isplata zarade",
            "uplata plate",
            "mesečna plata",
            "naknada za rad",
            "honorarna isplata",
        ],
        "amount_range": (45000, 220000),
        "status_weights": {"uspesna": 0.93, "na_cekanju": 0.05, "neuspesna": 0.02},
        "recent_probability": 0.74,
    },
    "porodicni_prenos": {
        "weight": 0.08,
        "templates": [
            "prenos novca {clan_porodice}",
            "pomoć {clan_porodice}",
            "porodični transfer",
            "uplata za porodične troškove",
            "slanje novca {clan_porodice}",
        ],
        "amount_range": (2000, 45000),
        "status_weights": {"uspesna": 0.9, "na_cekanju": 0.07, "neuspesna": 0.03},
        "recent_probability": 0.72,
    },
    "rata_kredita": {
        "weight": 0.05,
        "templates": [
            "rata kredita",
            "mesečna obaveza po kreditu",
            "otplata kredita",
            "uplata rate zajma",
            "plaćanje anuiteta",
        ],
        "amount_range": (8000, 65000),
        "status_weights": {"uspesna": 0.92, "na_cekanju": 0.06, "neuspesna": 0.02},
        "recent_probability": 0.78,
    },
    "bez_opisa": {
        "weight": 0.03,
        "templates": [
            "bez opisa",
            "prenos",
            "-",
            ".",
            "nalog",
            "interno",
        ],
        "amount_range": (1000, 55000),
        "status_weights": {"uspesna": 0.74, "na_cekanju": 0.14, "neuspesna": 0.12},
        "recent_probability": 0.58,
    },
}


def clean_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^0-9a-zA-ZčćšžđČĆŠŽĐ\s\.\-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    labels = list(weights.keys())
    values = list(weights.values())
    return rng.choices(labels, weights=values, k=1)[0]


def choose_semantic_group(rng: random.Random) -> str:
    names = list(SEMANTIC_GROUPS.keys())
    weights = [SEMANTIC_GROUPS[name]["weight"] for name in names]
    return rng.choices(names, weights=weights, k=1)[0]


def render_transaction_description(group: str, rng: random.Random) -> str:
    template = rng.choice(SEMANTIC_GROUPS[group]["templates"])
    values = {
        "mesec": rng.choice(MESECI),
        "objekat": rng.choice(STANOVI),
        "rezija": rng.choice(REZIJE),
        "prodavac": rng.choice(PRODAVCI),
        "clan_porodice": rng.choice(PORODICA),
        "razlog": rng.choice(["selidbu", "put", "račune", "privatne troškove", "dogovor"]),
    }
    description = clean_text(template.format(**values))

    if group in {"placanje_kirije", "pozajmica", "hitna_uplata"} and rng.random() < 0.3:
        description = f"{description} {rng.choice(SKRACENICE)}"

    return description


def generate_semantic_payload(rng: random.Random) -> dict:
    group = choose_semantic_group(rng)
    spec = SEMANTIC_GROUPS[group]
    description = render_transaction_description(group, rng)
    amount = round(rng.uniform(*spec["amount_range"]), 2)
    status = _weighted_choice(rng, spec["status_weights"])

    return {
        "semanticka_grupa_trans": group,
        "opis_trans": description,
        "iznos_trans": amount,
        "status_trans": status,
    }


@lru_cache(maxsize=1)
def _load_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(DEFAULT_EMBEDDING_MODEL)


def embed_texts(texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[float]]:
    if not texts:
        return []

    model = _load_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [[round(float(value), 6) for value in vector] for vector in vectors]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
