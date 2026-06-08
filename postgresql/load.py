#!/usr/bin/env python3
"""
Loads generated JSON data into PostgreSQL.

Usage:
    python postgresql/load.py --scale 15000
"""
import argparse
import json
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    'host':     os.environ.get('POSTGRES_HOST', 'localhost'),
    'port':     int(os.environ.get('POSTGRES_PORT', '5433')),
    'dbname':   os.environ.get('POSTGRES_DB', 'bankdb'),
    'user':     os.environ.get('POSTGRES_USER', 'postgres'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
}

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


def load_json(scale, name):
    path = os.path.join('data', str(scale), f'{name}.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def to_vector_literal(values):
    return '[' + ','.join(f'{value:.6f}' for value in values) + ']'


def load_all(scale):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("  Recreating schema...")
    cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        cur.execute(f.read())
    conn.commit()

    start = time.perf_counter()

    filijale = load_json(scale, 'filijale')
    execute_values(cur,
        "INSERT INTO Filijala (id_fil, naziv_fil, adresa_fil, grad_fil) VALUES %s",
        [(r['id_fil'], r['naziv_fil'], r['adresa_fil'], r['grad_fil']) for r in filijale])
    print(f"  Filijala:      {len(filijale):>7}")

    bankomati = load_json(scale, 'bankomati')
    execute_values(cur,
        "INSERT INTO Bankomat (id_bank, lokacija_bank, grad_bank) VALUES %s",
        [(r['id_bank'], r['lokacija_bank'], r['grad_bank']) for r in bankomati])
    print(f"  Bankomat:      {len(bankomati):>7}")

    klijenti = load_json(scale, 'klijenti')
    execute_values(cur,
        """INSERT INTO Klijent
           (id_kli, ime_kli, prezime_kli, email_kli, datum_reg_kli,
            jmbg_kli, telefon_kli, adresa_kli, grad_kli, datum_rodj_kli, tip_kli)
           VALUES %s""",
        [(r['id_kli'], r['ime_kli'], r['prezime_kli'], r['email_kli'],
          r['datum_reg_kli'], r['jmbg_kli'], r['telefon_kli'],
          r['adresa_kli'], r['grad_kli'], r['datum_rodj_kli'], r['tip_kli'])
         for r in klijenti])
    print(f"  Klijent:       {len(klijenti):>7}")

    racuni = load_json(scale, 'racuni')
    execute_values(cur,
        """INSERT INTO Racun
           (id_rac, broj_rac, tip_rac, saldo_rac, valuta_rac,
            datum_otavaranja_rac, limit_rac, id_kli, id_fil)
           VALUES %s""",
        [(r['id_rac'], r['broj_rac'], r['tip_rac'], r['saldo_rac'],
          r['valuta_rac'], r['datum_otavaranja_rac'], r['limit_rac'],
          r['id_kli'], r['id_fil'])
         for r in racuni])
    print(f"  Racun:         {len(racuni):>7}")

    kartice = load_json(scale, 'kartice')
    execute_values(cur,
        """INSERT INTO Kartica
           (id_kar, broj_kar, tip_kar, datum_isteka_kar, datum_izdavanja_kar, CCV_kar, id_rac)
           VALUES %s""",
        [(r['id_kar'], r['broj_kar'], r['tip_kar'],
          r['datum_isteka_kar'], r['datum_izdavanja_kar'], r['CCV_kar'], r['id_rac'])
         for r in kartice])
    print(f"  Kartica:       {len(kartice):>7}")

    transakcije = load_json(scale, 'transakcije')
    execute_values(cur,
        """INSERT INTO Transakcija
           (id_trans, iznos_trans, datum_vreme_trans, opis_trans,
            status_trans, semanticka_grupa_trans, embedding_trans,
            id_rac_platilac, id_rac_primalac)
           VALUES %s""",
        [(r['id_trans'], r['iznos_trans'], r['datum_vreme_trans'],
          r['opis_trans'], r['status_trans'],
          r['semanticka_grupa_trans'], to_vector_literal(r['embedding_trans']),
          r['id_rac_platilac'], r['id_rac_primalac'])
         for r in transakcije])
    print(f"  Transakcija:   {len(transakcije):>7}")

    ima_punomoc = load_json(scale, 'ima_punomoc')
    execute_values(cur,
        """INSERT INTO Ima_Punomoc
           (id_kli, id_rac, datum_dodele, nivo_pristupa)
           VALUES %s""",
        [(r['id_kli'], r['id_rac'],
          r['datum_dodele'], r['nivo_pristupa'])
         for r in ima_punomoc])
    print(f"  Ima_Punomoc:   {len(ima_punomoc):>7}")

    gotovinska = load_json(scale, 'gotovinska_trans')
    execute_values(cur,
        "INSERT INTO Gotovinska_Trans (id_rac, id_bank, tip_got_trans) VALUES %s",
        [(r['id_rac'], r['id_bank'], r['tip_got_trans']) for r in gotovinska])
    print(f"  Got_Trans:     {len(gotovinska):>7}")

    conn.commit()
    elapsed = time.perf_counter() - start

    cur.close()
    conn.close()
    return elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', type=int, default=15000)
    args = parser.parse_args()

    print(f"Loading PostgreSQL (scale={args.scale})...")
    try:
        elapsed = load_all(args.scale)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Run generate.py first.")
        sys.exit(1)
    print(f"PostgreSQL load time: {elapsed:.2f}s")


if __name__ == '__main__':
    main()
