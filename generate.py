#!/usr/bin/env python3
"""
Generates identical fake banking data for PostgreSQL and Neo4j.
All entities and relationships are saved as JSON files under data/<scale>/.

Usage:
    python generate.py --scale 150
    python generate.py --scale 15000
    python generate.py --scale 100000
"""
import argparse
import json
import os
import random
from faker import Faker
from semantic_vectors import embed_texts, generate_semantic_payload, SEMANTIC_GROUPS

fake = Faker('hr_HR')


def seed_all(seed=42):
    Faker.seed(seed)
    random.seed(seed)


def get_counts(n_trans):
    """Scale all entity counts proportionally to the number of transactions."""
    ratio = n_trans / 15000
    return {
        'filijale':    max(5,  int(20  * ratio)),
        'bankomati':   max(5,  int(30  * ratio)),
        'klijenti':    max(20, int(500 * ratio)),
        'racuni':      max(30, int(800 * ratio)),
        'kartice':     max(25, int(650 * ratio)),
        'transakcije': n_trans,
    }


def gen_filijale(n):
    def jedna_filijala(i):
        grad = fake.city()
        return {
            'id_fil':     i + 1,
            'naziv_fil':  f"Filijala {grad}",
            'adresa_fil': fake.street_address(),
            'grad_fil':   grad,
        }
    return [jedna_filijala(i) for i in range(n)]


def gen_bankomati(n):
    return [
        {
            'id_bank':      i + 1,
            'lokacija_bank': fake.street_address(),
            'grad_bank':    fake.city(),
        }
        for i in range(n)
    ]


def gen_klijenti(n):
    result = []
    seen_jmbg = set()
    for i in range(n):
        birth = fake.date_of_birth(minimum_age=18, maximum_age=80)
        while True:
            jmbg = (
                birth.strftime('%d%m')
                + birth.strftime('%Y')[1:]
                + str(random.randint(70, 79))
                + str(random.randint(100, 999))
                + str(random.randint(0, 9))
            )
            if jmbg not in seen_jmbg:
                seen_jmbg.add(jmbg)
                break
        result.append({
            'id_kli':        i + 1,
            'ime_kli':       fake.first_name(),
            'prezime_kli':   fake.last_name(),
            'email_kli':     fake.email(),
            'datum_reg_kli': fake.date_between(start_date='-10y', end_date='today').isoformat(),
            'jmbg_kli':      jmbg,
            'telefon_kli':   fake.phone_number(),
            'adresa_kli':    fake.street_address(),
            'grad_kli':      fake.city(),
            'datum_rodj_kli': birth.isoformat(),
            'tip_kli':       random.choice(['fizicko lice', 'pravno lice']),
        })
    return result


def gen_racuni(n, n_klijenti, n_filijale):
    tip_choices = ['devizni', 'dinarski', 'stedni']
    result = []
    for i in range(n):
        tip = random.choice(tip_choices)
        valuta = 'RSD' if tip == 'dinarski' else random.choice(['RSD', 'EUR', 'USD'])
        result.append({
            'id_rac':              i + 1,
            'broj_rac':            fake.iban(),
            'tip_rac':             tip,
            'saldo_rac':           round(random.uniform(0, 100000), 2),
            'valuta_rac':          valuta,
            'datum_otavaranja_rac': fake.date_between(start_date='-15y', end_date='today').isoformat(),
            'limit_rac':           round(random.uniform(0, 50000), 2),
            'id_kli':              random.randint(1, n_klijenti),
            'id_fil':              random.randint(1, n_filijale) if random.random() < 0.8 else None,
        })
    return result


def gen_kartice(n, n_racuni):
    tip_choices = ['debitna', 'kreditna', 'prepaid']
    result = []
    for i in range(n):
        issued = fake.date_between(start_date='-5y', end_date='today')
        try:
            expiry = issued.replace(year=issued.year + 5)
        except ValueError:
            # 29. februar — pomeri na 28.
            expiry = issued.replace(year=issued.year + 5, day=28)
        result.append({
            'id_kar':              i + 1,
            'broj_kar':            fake.credit_card_number(),
            'tip_kar':             random.choice(tip_choices),
            'datum_isteka_kar':    expiry.isoformat(),
            'datum_izdavanja_kar': issued.isoformat(),
            'CCV_kar':             str(random.randint(100, 999)),
            'id_rac':              random.randint(1, n_racuni),
        })
    return result


def gen_transakcije(n, n_racuni):
    result = []

    # 10% racuna dobija 90% transakcija
    n_hub = max(1, n_racuni // 10)
    hub_racuni = random.sample(range(1, n_racuni + 1), n_hub)

    for i in range(n):
        payload = generate_semantic_payload(random)
        group_spec = SEMANTIC_GROUPS[payload['semanticka_grupa_trans']]

        # 90% sanse da platilac bude hub racun
        if random.random() < 0.9:
            platilac = random.choice(hub_racuni)
        else:
            platilac = random.randint(1, n_racuni)

        # 90% sanse da primalac bude hub racun
        if random.random() < 0.9:
            primalac = random.choice(hub_racuni)
        else:
            primalac = random.randint(1, n_racuni)

        while primalac == platilac:
            if random.random() < 0.9:
                primalac = random.choice(hub_racuni)
            else:
                primalac = random.randint(1, n_racuni)

        if random.random() < group_spec['recent_probability']:
            datum_vreme = fake.date_time_between(start_date='-365d', end_date='now').isoformat()
        else:
            datum_vreme = fake.date_time_between(start_date='-5y', end_date='-365d').isoformat()

        result.append({
            'id_trans':               i + 1,
            'iznos_trans':            payload['iznos_trans'],
            'datum_vreme_trans':      datum_vreme,
            'opis_trans':             payload['opis_trans'],
            'status_trans':           payload['status_trans'],
            'semanticka_grupa_trans': payload['semanticka_grupa_trans'],
            'id_rac_platilac':        platilac,
            'id_rac_primalac':        primalac,
        })

    embeddingi = embed_texts([red['opis_trans'] for red in result])
    for red, embedding in zip(result, embeddingi):
        red['embedding_trans'] = embedding

    return result


def obogati_transakcije_posebnim_obrascima(transakcije, ima_punomoc, n_racuni):
    if not transakcije:
        return transakcije

    racuni_sa_punomocjem = sorted({red['id_rac'] for red in ima_punomoc})
    if len(racuni_sa_punomocjem) < 3:
        racuni_sa_punomocjem = list(range(1, min(n_racuni, 6) + 1))

    if len(racuni_sa_punomocjem) < 3:
        return transakcije

    broj_ciklusa = max(2, min(len(transakcije) // 2000 + 2, 8))
    pocetak = max(0, len(transakcije) - broj_ciklusa * 5)

    for pomeraj in range(0, broj_ciklusa * 5, 5):
        baza = pocetak + pomeraj
        if baza + 4 >= len(transakcije):
            break

        a, b, c = random.sample(racuni_sa_punomocjem, 3)
        zapisi = [
            (baza + 0, a, b, "neobičan transfer", round(random.uniform(18000, 60000), 2)),
            (baza + 1, b, a, "neuobičajen prenos sredstava", round(random.uniform(18000, 60000), 2)),
            (baza + 2, a, b, "specijalan prenos bez standardne osnove", round(random.uniform(25000, 90000), 2)),
            (baza + 3, b, c, "transfer po hitnom dogovoru", round(random.uniform(25000, 90000), 2)),
            (baza + 4, c, a, "prenos po internom dogovoru", round(random.uniform(25000, 90000), 2)),
        ]

        for index, platilac, primalac, opis, iznos in zapisi:
            timestamp = fake.date_time_between(start_date='-300d', end_date='now').isoformat()
            transakcije[index].update({
                'iznos_trans': iznos,
                'datum_vreme_trans': timestamp,
                'opis_trans': opis,
                'status_trans': 'uspesna',
                'semanticka_grupa_trans': 'neobican_transfer',
                'id_rac_platilac': platilac,
                'id_rac_primalac': primalac,
            })

    embeddingi = embed_texts([red['opis_trans'] for red in transakcije[pocetak:]])
    for red, embedding in zip(transakcije[pocetak:], embeddingi):
        red['embedding_trans'] = embedding

    return transakcije


def gen_ima_punomoc(n_klijenti, n_racuni, racuni):
    n = max(5, n_klijenti // 5)
    seen = set()
    result = []
    attempts = 0
    vlasnik_racuna = {r['id_rac']: r['id_kli'] for r in racuni}
    while len(result) < n and attempts < n * 20:
        kli = random.randint(1, n_klijenti)
        rac = random.randint(1, n_racuni)
        attempts += 1
        # klijent ne moze imati punomoc na svom sopstvenom racunu
        if vlasnik_racuna.get(rac) == kli or (kli, rac) in seen:
            continue
        seen.add((kli, rac))
        result.append({
            'id_kli':        kli,
            'id_rac':        rac,
            'datum_dodele':  fake.date_between(start_date='-5y', end_date='today').isoformat(),
            'nivo_pristupa': random.choice(['citanje', 'citanje_pisanje', 'puno']),
        })
    return result


def gen_gotovinska_trans(n_racuni, n_bankomati, n_trans):
    n = max(10, n_trans // 5)
    result = []
    for _ in range(n):
        result.append({
            'id_rac':        random.randint(1, n_racuni),
            'id_bank':       random.randint(1, n_bankomati),
            'tip_got_trans': random.choice(['uplata', 'isplata']),
        })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', type=int, default=15000,
                        help='Number of transactions (e.g. 150, 15000, 100000)')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    seed_all(args.seed)
    counts = get_counts(args.scale)

    out_dir = os.path.join('data', str(args.scale))
    os.makedirs(out_dir, exist_ok=True)

    print(f"Generating data for scale={args.scale}...")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    filijale        = gen_filijale(counts['filijale'])
    bankomati       = gen_bankomati(counts['bankomati'])
    klijenti        = gen_klijenti(counts['klijenti'])
    racuni          = gen_racuni(counts['racuni'], counts['klijenti'], counts['filijale'])
    kartice         = gen_kartice(counts['kartice'], counts['racuni'])
    ima_punomoc     = gen_ima_punomoc(counts['klijenti'], counts['racuni'], racuni)
    transakcije     = gen_transakcije(counts['transakcije'], counts['racuni'])
    transakcije     = obogati_transakcije_posebnim_obrascima(
        transakcije, ima_punomoc, counts['racuni']
    )
    gotovinska_trans = gen_gotovinska_trans(counts['racuni'], counts['bankomati'], counts['transakcije'])

    datasets = {
        'filijale':         filijale,
        'bankomati':        bankomati,
        'klijenti':         klijenti,
        'racuni':           racuni,
        'kartice':          kartice,
        'transakcije':      transakcije,
        'ima_punomoc':      ima_punomoc,
        'gotovinska_trans': gotovinska_trans,
    }

    for name, records in datasets.items():
        path = os.path.join(out_dir, f'{name}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"  Saved {len(records):>7} records → {path}")

    print("Done.")


if __name__ == '__main__':
    main()
