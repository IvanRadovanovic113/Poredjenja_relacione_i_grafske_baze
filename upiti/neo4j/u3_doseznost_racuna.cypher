// U3: Doseznost racuna kroz transakcioni graf
//
// Cilj:
// Od top 3 racuna sa najvise odlaznih transakcija, izracunati
// koliko je razlicitih racuna dostupno kroz lanac od najvise
// 2 transakcije.
//
// Zasto ide u korist grafske baze:
// Neo4j prati veze od poznatog polaznog cvora direktno kroz
// index-free adjacency — za svaki korak traversala skace na
// susedne cvorove bez skeniranja tabela. Relaciona baza mora
// rekurzivnim CTE-om da materijalizuje sve putanje kroz JOIN
// operacije nad celom tabelom Transakcija, sto postaje
// eksponencijalno skuplje sa brojem transakcija i dubinom.
MATCH (r:Racun)-[t:TRANSAKCIJA]->(:Racun)
WHERE t.status_trans = 'uspesna'
WITH r, count(t) AS broj_trans
ORDER BY broj_trans DESC
LIMIT 3

MATCH (r)-[:TRANSAKCIJA*..2]->(cilj:Racun)
WHERE r <> cilj
RETURN r.broj_rac AS polazni_racun,
       count(DISTINCT cilj) AS broj_dostupnih_racuna
ORDER BY broj_dostupnih_racuna DESC;