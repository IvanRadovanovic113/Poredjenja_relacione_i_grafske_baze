# Bancarski model — PostgreSQL vs Neo4j

Projekat za istraživački rad koji puni isti skup podataka u PostgreSQL i Neo4j u različitim obimima, radi poređenja performansi.

Aktuelna verzija projekta dodatno uvodi kontrolisane semantičke opise transakcija i prave embeddinge preko modela `djovak/embedic-base`, kako bi se moglo porediti ponašanje vektorskih indeksa u relacionoj i graf bazi.

---

## Preduslovi

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Ništa drugo nije potrebno — Python i sve biblioteke se instaliraju unutar Docker kontejnera.

---

## Pokretanje

### 1. Pokretanje baza

```bash
docker compose up -d
```

Pokreće PostgreSQL i Neo4j u pozadini. Sačekaj ~15 sekundi da se obe baze potpuno inicijalizuju.

### 2. Punjenje podataka

Odaberi jedan od tri obima:

```bash
# Mali — 150 transakcija
docker compose run --rm loader python run.py --scale 150

# Srednji — 15 000 transakcija
docker compose run --rm loader python run.py --scale 15000

# Veliki — 100 000 transakcija
docker compose run --rm loader python run.py --scale 100000
```

> **Napomena:** Prva komanda automatski build-uje Docker image i instalira sve Python pakete (`faker`, `psycopg2`, `neo4j`). Svaki sledeći poziv je brži.

Ako promeniš kod i treba ti rebuild image-a:

```bash
docker compose run --rm --build loader python run.py --scale 15000
```

---

## Razmere podataka po obimu

| Entitet       | scale=150 | scale=15 000 | scale=100 000 |
|---------------|----------:|-------------:|--------------:|
| Filijala      |         5 |           20 |            66 |
| Bankomat      |         5 |           30 |           100 |
| Klijent       |        20 |          500 |         3 333 |
| Racun         |        30 |          800 |         5 333 |
| Kartica       |        25 |          650 |         4 333 |
| Transakcija   |       150 |       15 000 |       100 000 |

Svi podaci se generišu sa istim seed-om (`42`) — identičan dataset u oba obima.

---

## Pregled podataka

### Neo4j Browser

Otvori u pretraživaču:

```
http://localhost:7474
```

- **Username:** `neo4j`
- **Password:** `bankdb123`

Korisni upiti:

```cypher
-- Broj čvorova po tipu
MATCH (n) RETURN labels(n)[0] AS tip, count(n) AS broj ORDER BY broj DESC

-- Pregled 50 čvorova
MATCH (n) RETURN n LIMIT 50

-- Sve transakcije jednog klijenta
MATCH (k:Klijent)-[:POSEDUJE]->(r:Racun)-[:PLATILAC]->(t:Transakcija)
WHERE k.id_kli = 1
RETURN k, r, t LIMIT 25
```

### pgAdmin (browser)

```
http://localhost:5050
```

- **Email:** `admin@admin.com`
- **Password:** `admin`

Nakon prijave, dodaj server jednom:
1. Desni klik na **Servers** → **Register → Server**
2. Tab **General** → Name: `bankdb`
3. Tab **Connection**:
   - Host: `postgres`
   - Port: `5432`
   - Database: `bankdb`
   - Username: `postgres`
   - Password: `postgres`
4. **Save**

Korisni upiti:

```sql
-- Broj redova po tabeli
SELECT 'Filijala' AS tabela, COUNT(*) FROM Filijala UNION ALL
SELECT 'Bankomat',           COUNT(*) FROM Bankomat UNION ALL
SELECT 'Klijent',            COUNT(*) FROM Klijent  UNION ALL
SELECT 'Racun',              COUNT(*) FROM Racun    UNION ALL
SELECT 'Kartica',            COUNT(*) FROM Kartica  UNION ALL
SELECT 'Transakcija',        COUNT(*) FROM Transakcija;

-- Sve transakcije jednog klijenta
SELECT t.*
FROM Transakcija t
JOIN Racun r ON r.id_rac = t.id_rac_platilac
WHERE r.id_kli = 1;
```

---

## Napredne opcije

Punjenje samo jedne baze:

```bash
docker compose run --rm loader python run.py --scale 15000 --target pg
docker compose run --rm loader python run.py --scale 15000 --target neo4j
```

Preskočiti generisanje (reuse postojećih podataka):

```bash
docker compose run --rm loader python run.py --scale 15000 --skip-generate
```

---

## Vektorski benchmark

Opis transakcije se više ne generiše kao potpuno nasumična rečenica, već kroz semantičke klastere kao što su:

- `plaćanje_kirije`
- `pozajmica`
- `neobičan_transfer`
- `sumnjiva_uplata`
- `hitna_uplata`
- `rezije`

Za svaki opis se generiše pravi embedding dimenzije `768` pomoću modela `djovak/embedic-base`. Model se preuzima unutar Docker okruženja i čuva u lokalnom folderu `model_cache/`, tako da se pri sledećim pokretanjima ne skida ponovo.

Podrzana su tri glavna benchmark upita:

1. Nadji transakcije slicne `plaćanje kirije`
2. Nadji transakcije slicne `plaćanje kirije`, vece od `30.000 RSD`, u statusu `uspesna`, u poslednjih `12 meseci`
3. Nadji racune sa punomoci koji ucestvuju u transakcijama slicnim `neobičan transfer` i koji su deo ciklusa duzine `2-3`

### Pokretanje benchmarka

```bash
python merenja/izmeri_vektorske_upite.py
```

Primer sa promenjenim parametrima:

```bash
python merenja/izmeri_vektorske_upite.py \
  --k 20 \
  --pg-hnsw-m 32 \
  --pg-hnsw-ef-search 120 \
  --pg-ivf-lists 200 \
  --pg-ivf-probes 20 \
  --neo4j-hnsw-m 32 \
  --neo4j-hnsw-ef-construction 200 \
  --neo4j-quantization false
```

Napomena:
- pri prvom pokretanju Docker ce preuzeti model `djovak/embedic-base`
- model se zatim cuva u `model_cache/` i koristi se ponovo bez novog skidanja
- za najbolji kvalitet opisi i upiti koriste srpsku latinicu sa dijakriticima (`č`, `ć`, `š`, `ž`, `đ`)

Skripta cuva:

- rezime metrika u `rezultati/vektorski_benchmark/rezime.csv`
- detaljne top-k rezultate i score-ove u `rezultati/vektorski_benchmark/detalji.csv`

Metrike koje se prate:

- latencija upita: `avg`, `p50`, `p95`
- vreme kreiranja indeksa
- velicina indeksa na disku
- vreme inserta novih transakcija sa embeddingom
- `recall@k` u odnosu na PostgreSQL exact search
- `overlap top-k` izmedju metoda

### Grafikoni

```bash
python merenja/nacrtaj_vektorske_grafikone.py
```

Grafikoni se cuvaju u `rezultati/vektorski_benchmark/grafikoni/`.

---

## Zaustavljanje

```bash
docker compose down
```

Brisanje i svih podataka (volumeni):

```bash
docker compose down -v
```

---

## Struktura projekta

```
.
├── docker-compose.yml       # PostgreSQL + Neo4j + loader servis
├── Dockerfile               # Python image sa instaliranim paketima
├── requirements.txt         # faker, psycopg2-binary, neo4j
├── generate.py              # Generiše JSON podatke u data/<scale>/
├── run.py                   # Orkestrira generisanje i punjenje
├── data/                    # Generisani JSON fajlovi (nije u git-u)
├── postgresql/
│   ├── schema.sql           # CREATE TABLE definicije
│   └── load.py              # Upisuje JSON u PostgreSQL
└── neo4j/
    ├── constraints.cypher   # CREATE CONSTRAINT / INDEX
    └── load.py              # Upisuje JSON u Neo4j
```
