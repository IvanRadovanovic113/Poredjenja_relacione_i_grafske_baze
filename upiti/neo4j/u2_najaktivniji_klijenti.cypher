-- U2: Najaktivniji klijenti
--
-- Cilj:
-- Prikazati klijente koji imaju najveci odlazni promet na osnovu uspesnih
-- transakcija, uz prikaz broja racuna i broja aktivnih kartica.
--
-- Zasto upit ide u korist relacione baze:
-- Upit koristi vise tabela, agregacije po klijentu, CTE izraze,
-- filtriranje po statusu transakcije i tipu klijenta, kao i sortiranje
-- po izracunatoj vrednosti ukupnog prometa. Ovo je tipican analiticki
-- upit koji relaciona baza efikasno obradjuje setovski.

WITH transakcije_po_klijentu AS (
    SELECT
        r.id_kli,
        COUNT(*) AS broj_uspesnih_odlaznih_transakcija,
        SUM(t.iznos_trans) AS ukupan_iznos_poslat,
        ROUND(AVG(t.iznos_trans), 2) AS prosecan_iznos_transakcije,
        SUM(
            CASE
                WHEN t.iznos_trans >= 5000 THEN 1
                ELSE 0
            END
        ) AS broj_velikih_transakcija
    FROM Racun r
    JOIN Transakcija t
        ON t.id_rac_platilac = r.id_rac
    WHERE t.status_trans = 'uspesna'
      AND t.datum_vreme_trans >= TIMESTAMP '2022-01-01 00:00:00'
    GROUP BY r.id_kli
),

racuni_i_kartice_po_klijentu AS (
    SELECT
        r.id_kli,
        COUNT(DISTINCT r.id_rac) AS broj_racuna,
        COUNT(DISTINCT kar.id_kar) FILTER (
            WHERE kar.tip_kar IN ('debitna', 'kreditna')
              AND kar.datum_isteka_kar >= CURRENT_DATE
        ) AS broj_aktivnih_kartica
    FROM Racun r
    LEFT JOIN Kartica kar
        ON kar.id_rac = r.id_rac
    GROUP BY r.id_kli
)

SELECT
    k.id_kli,
    k.ime_kli,
    k.prezime_kli,
    k.grad_kli,
    k.tip_kli,

    rk.broj_racuna,
    rk.broj_aktivnih_kartica,

    tp.broj_uspesnih_odlaznih_transakcija,
    tp.broj_velikih_transakcija,
    tp.ukupan_iznos_poslat,
    tp.prosecan_iznos_transakcije
FROM Klijent k
JOIN transakcije_po_klijentu tp
    ON tp.id_kli = k.id_kli
JOIN racuni_i_kartice_po_klijentu rk
    ON rk.id_kli = k.id_kli
WHERE k.tip_kli = 'fizicko lice'
  AND rk.broj_aktivnih_kartica >= 1
  AND tp.broj_uspesnih_odlaznih_transakcija >= 1
ORDER BY tp.ukupan_iznos_poslat DESC
LIMIT 20;