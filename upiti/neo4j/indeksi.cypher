// Indeksi za Neo4j upite koji se koriste u poredjenju performansi.
//
// Indeksi su dodati za atribute koji se koriste u:
// 1. filtriranju cvorova,
// 2. pretrazi transakcija,
// 3. proveri tipa klijenta,
// 4. proveri tipa i datuma isteka kartice.

// U1 i U2 filtriraju transakcije po statusu i datumu.
CREATE INDEX idx_transakcija_status_datum IF NOT EXISTS
FOR (t:Transakcija)
ON (t.status_trans, t.datum_vreme_trans);

// U1 dodatno filtrira transakcije po iznosu.
CREATE INDEX idx_transakcija_iznos IF NOT EXISTS
FOR (t:Transakcija)
ON (t.iznos_trans);

// U2 filtrira klijente po tipu.
CREATE INDEX idx_klijent_tip IF NOT EXISTS
FOR (k:Klijent)
ON (k.tip_kli);

// U2 filtrira kartice po tipu i datumu isteka.
CREATE INDEX idx_kartica_tip_istek IF NOT EXISTS
FOR (kar:Kartica)
ON (kar.tip_kar, kar.datum_isteka_kar);

// Pomocni indeksi za identifikatore cvorova.
// Nisu presudni za traversal, ali su korisni za proveru i stabilnije izvrsavanje.
CREATE INDEX idx_filijala_id IF NOT EXISTS
FOR (f:Filijala)
ON (f.id_fil);

CREATE INDEX idx_racun_id IF NOT EXISTS
FOR (r:Racun)
ON (r.id_rac);

CREATE INDEX idx_klijent_id IF NOT EXISTS
FOR (k:Klijent)
ON (k.id_kli);