-- U4: Detekcija kružnih tokova novca (kružnih transfera)
--
-- Cilj:
-- Identifikacija sumnjivih obrazaca gde se novac kroz lanac od 
-- 2 ili 3 transakcije vraća na polazni račun (ciklus).
--
-- Zasto ide u korist grafske baze:
-- Neo4j koristi pretragu putanja (pattern matching) koja je 
-- optimizovana za detekciju ciklusa u grafu, dok je u SQL-u ovo 
-- "skupa" operacija. Relaciona baza mora ili da vrši rekurzivne 
-- JOIN-ove nad velikim tabelama ili da materijalizuje putanje 
-- putem CTE-a, što drastično povećava kompleksnost i vreme 
-- izvršenja kako se dubina pretrage i broj transakcija povećavaju.
WITH Putanje AS (
    SELECT t1.id_rac_platilac AS start_rac, t1.id_rac_primalac AS mid_rac, t1.id_rac_platilac AS end_rac, 2 AS duzina
    FROM Transakcija t1
    JOIN Transakcija t2 ON t1.id_rac_primalac = t2.id_rac_platilac AND t1.id_rac_platilac = t2.id_rac_primalac
    WHERE t1.status_trans = 'uspesna' AND t2.status_trans = 'uspesna'

    UNION ALL

    SELECT t1.id_rac_platilac, t2.id_rac_primalac, t3.id_rac_primalac, 3 AS duzina
    FROM Transakcija t1
    JOIN Transakcija t2 ON t1.id_rac_primalac = t2.id_rac_platilac
    JOIN Transakcija t3 ON t2.id_rac_primalac = t3.id_rac_platilac
    WHERE t1.id_rac_platilac = t3.id_rac_primalac
      AND t1.status_trans = 'uspesna' AND t2.status_trans = 'uspesna' AND t3.status_trans = 'uspesna'
)
SELECT DISTINCT k.id_kli, k.ime_kli, k.prezime_kli, p.duzina
FROM Putanje p
JOIN Racun r ON r.id_rac = p.start_rac
JOIN Klijent k ON k.id_kli = r.id_kli
LIMIT 20;