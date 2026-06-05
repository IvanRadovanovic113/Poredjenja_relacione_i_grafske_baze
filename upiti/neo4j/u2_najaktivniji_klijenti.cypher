// U2: Najaktivniji klijenti
//
// Cilj:
// Prikazati klijente koji imaju najveci odlazni promet na osnovu uspesnih
// transakcija, uz prikaz broja racuna i broja aktivnih kartica.
//
// Zasto je upit pogodan za poredjenje:
// U grafskom modelu se za isti poslovni zahtev mora obilaziti vise veza:
// Klijent -> Racun -[:TRANSAKCIJA]-> Racun i Klijent -> Racun -> Kartica.
// Pored toga, rezultat zahteva vise odvojenih agregacija po klijentu.
// Ovakav izvestajni upit prirodnije odgovara relacionoj bazi.

WITH '2022-01-01T00:00:00' AS pocetak_perioda,
     toString(date()) AS danas

MATCH (k:Klijent)
WHERE k.tip_kli = 'fizicko lice'

CALL (k, pocetak_perioda) {
    MATCH (k)-[:POSEDUJE]->(:Racun)-[t:TRANSAKCIJA]->(:Racun)
    WHERE t.status_trans = 'uspesna'
      AND t.datum_vreme_trans >= pocetak_perioda
    RETURN
        count(t) AS broj_uspesnih_odlaznih_transakcija,
        sum(toFloat(t.iznos_trans)) AS ukupan_iznos_poslat,
        round(avg(toFloat(t.iznos_trans)) * 100) / 100 AS prosecan_iznos_transakcije,
        sum(
            CASE
                WHEN toFloat(t.iznos_trans) >= 5000 THEN 1
                ELSE 0
            END
        ) AS broj_velikih_transakcija
}

CALL (k) {
    MATCH (k)-[:POSEDUJE]->(r:Racun)
    RETURN count(DISTINCT r) AS broj_racuna
}

CALL (k, danas) {
    MATCH (k)-[:POSEDUJE]->(:Racun)-[:IMA]->(kar:Kartica)
    WHERE kar.tip_kar IN ['debitna', 'kreditna']
      AND kar.datum_isteka_kar >= danas
    RETURN count(DISTINCT kar) AS broj_aktivnih_kartica
}

WITH
    k,
    broj_racuna,
    broj_aktivnih_kartica,
    broj_uspesnih_odlaznih_transakcija,
    broj_velikih_transakcija,
    ukupan_iznos_poslat,
    prosecan_iznos_transakcije

WHERE broj_aktivnih_kartica >= 1
  AND broj_uspesnih_odlaznih_transakcija >= 1

RETURN
    k.id_kli AS id_kli,
    k.ime_kli AS ime_kli,
    k.prezime_kli AS prezime_kli,
    k.grad_kli AS grad_kli,
    k.tip_kli AS tip_kli,

    broj_racuna,
    broj_aktivnih_kartica,
    broj_uspesnih_odlaznih_transakcija,
    broj_velikih_transakcija,
    round(ukupan_iznos_poslat * 100) / 100 AS ukupan_iznos_poslat,
    prosecan_iznos_transakcije

ORDER BY ukupan_iznos_poslat DESC
LIMIT 20;