// U1: Promet izmedju filijala
//
// Cilj:
// Prikazati ukupan promet izmedju parova filijala na osnovu uspesnih transakcija.
//
// Zasto je upit pogodan za poredjenje:
// Upit u grafskom modelu mora da prodje kroz vise povezanih cvorova:
// Filijala <- Racun -[:TRANSAKCIJA]-> Racun -> Filijala.
// Nakon pronalazenja putanja, vrse se filtriranje, grupisanje i agregacije.
// Ovakav izvestajni upit je prirodniji za relacionu bazu.

MATCH
    (rp:Racun)-[:OTVOREN_U]->(fp:Filijala),
    (rp)-[t:TRANSAKCIJA]->(rr:Racun),
    (rr)-[:OTVOREN_U]->(fr:Filijala)
WHERE t.status_trans = 'uspesna'
  AND t.datum_vreme_trans >= '2022-01-01T00:00:00'
  AND toFloat(t.iznos_trans) >= 100
  AND fp.id_fil <> fr.id_fil
RETURN
    fp.id_fil AS id_filijale_platioca,
    fp.naziv_fil AS filijala_platioca,
    fp.grad_fil AS grad_platioca,

    fr.id_fil AS id_filijale_primaoca,
    fr.naziv_fil AS filijala_primaoca,
    fr.grad_fil AS grad_primaoca,

    count(t) AS broj_transakcija,
    round(sum(toFloat(t.iznos_trans)) * 100) / 100 AS ukupan_iznos,
    round(avg(toFloat(t.iznos_trans)) * 100) / 100 AS prosecan_iznos,
    max(toFloat(t.iznos_trans)) AS najveca_transakcija
ORDER BY ukupan_iznos DESC
LIMIT 20;