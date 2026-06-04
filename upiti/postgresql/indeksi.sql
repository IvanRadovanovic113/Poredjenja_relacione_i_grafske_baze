-- Indeksi za PostgreSQL upite koji se koriste u poredjenju performansi.
--
-- Indeksi su dodati za kolone koje se najcesce koriste u:
-- 1. uslovima filtriranja,
-- 2. JOIN operacijama,
-- 3. grupisanju i agregacijama.

-- U1 i U2 koriste filtriranje transakcija po statusu, datumu i iznosu.
CREATE INDEX IF NOT EXISTS idx_transakcija_status_datum_iznos
ON Transakcija(status_trans, datum_vreme_trans, iznos_trans);

-- U1 koristi racun platioca i racun primaoca.
CREATE INDEX IF NOT EXISTS idx_transakcija_racun_platilac
ON Transakcija(id_rac_platilac);

CREATE INDEX IF NOT EXISTS idx_transakcija_racun_primalac
ON Transakcija(id_rac_primalac);

-- U1 spaja racune sa filijalama.
CREATE INDEX IF NOT EXISTS idx_racun_filijala
ON Racun(id_fil);

-- U2 spaja racune sa klijentima.
CREATE INDEX IF NOT EXISTS idx_racun_klijent
ON Racun(id_kli);

-- U2 spaja kartice sa racunima i filtrira aktivne kartice.
CREATE INDEX IF NOT EXISTS idx_kartica_racun_tip_istek
ON Kartica(id_rac, tip_kar, datum_isteka_kar);

-- U2 filtrira klijente po tipu.
CREATE INDEX IF NOT EXISTS idx_klijent_tip
ON Klijent(tip_kli);