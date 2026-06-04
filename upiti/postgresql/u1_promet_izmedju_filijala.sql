-- U1: Promet izmedju filijala
--
-- Cilj:
-- Prikazati ukupan promet izmedju parova filijala na osnovu uspesnih transakcija.
--
-- Zasto upit ide u korist relacione baze:
-- Upit koristi vise JOIN operacija nad tabelama Transakcija, Racun i Filijala,
-- zatim filtriranje po statusu, datumu i iznosu transakcije, kao i agregacije
-- COUNT, SUM, AVG i MAX. Ovo je tipican izvestajni upit koji relaciona baza
-- efikasno izvrsava nad velikim brojem redova.

SELECT
    fp.id_fil AS id_filijale_platioca,
    fp.naziv_fil AS filijala_platioca,
    fp.grad_fil AS grad_platioca,

    fr.id_fil AS id_filijale_primaoca,
    fr.naziv_fil AS filijala_primaoca,
    fr.grad_fil AS grad_primaoca,

    COUNT(*) AS broj_transakcija,
    SUM(t.iznos_trans) AS ukupan_iznos,
    ROUND(AVG(t.iznos_trans), 2) AS prosecan_iznos,
    MAX(t.iznos_trans) AS najveca_transakcija
FROM Transakcija t
JOIN Racun rp
    ON rp.id_rac = t.id_rac_platilac
JOIN Filijala fp
    ON fp.id_fil = rp.id_fil
JOIN Racun rr
    ON rr.id_rac = t.id_rac_primalac
JOIN Filijala fr
    ON fr.id_fil = rr.id_fil
WHERE t.status_trans = 'uspesna'
  AND t.datum_vreme_trans >= TIMESTAMP '2022-01-01 00:00:00'
  AND t.iznos_trans >= 100
  AND fp.id_fil <> fr.id_fil
GROUP BY
    fp.id_fil,
    fp.naziv_fil,
    fp.grad_fil,
    fr.id_fil,
    fr.naziv_fil,
    fr.grad_fil
ORDER BY ukupan_iznos DESC
LIMIT 20;