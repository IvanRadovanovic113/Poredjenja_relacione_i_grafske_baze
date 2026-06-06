-- U3: Doseznost racuna kroz transakcioni graf
--
-- Cilj:
-- Od top 3 racuna sa najvise odlaznih transakcija, izracunati
-- koliko je razlicitih racuna dostupno kroz lanac od najvise
-- 2 transakcije.
--
-- Zasto ide u korist grafske baze:
-- Neo4j prati veze direktno kroz index-free adjacency bez
-- skeniranja tabela. Relaciona baza mora rekurzivnim CTE-om
-- da materijalizuje sve putanje kroz JOIN operacije nad celom
-- tabelom Transakcija za svaki nivo dubine, sto postaje
-- eksponencijalno skuplje sa porastom broja transakcija.
WITH RECURSIVE top_racuni AS (
    SELECT
        t.id_rac_platilac   AS id_rac,
        COUNT(*)            AS broj_trans
    FROM Transakcija t
    WHERE t.status_trans = 'uspesna'
    GROUP BY t.id_rac_platilac
    ORDER BY broj_trans DESC
    LIMIT 3
),

lanac AS (
    SELECT
        t.id_rac_platilac   AS pocetak,
        t.id_rac_primalac   AS trenutni,
        1                   AS dubina
    FROM Transakcija t
    JOIN top_racuni tr ON tr.id_rac = t.id_rac_platilac

    UNION ALL

    SELECT
        l.pocetak,
        t.id_rac_primalac,
        l.dubina + 1
    FROM lanac l
    JOIN Transakcija t
        ON t.id_rac_platilac = l.trenutni
    WHERE l.dubina < 2
)

SELECT
    r.broj_rac              AS polazni_racun,
    COUNT(DISTINCT l.trenutni) AS broj_dostupnih_racuna
FROM lanac l
JOIN Racun r ON r.id_rac = l.pocetak
WHERE l.trenutni <> l.pocetak
GROUP BY r.id_rac, r.broj_rac
ORDER BY broj_dostupnih_racuna DESC;