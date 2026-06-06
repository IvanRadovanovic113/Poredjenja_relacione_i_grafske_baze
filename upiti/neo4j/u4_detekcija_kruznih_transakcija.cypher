// U4: Detekcija kružnih tokova novca (kružnih transfera)
//
// Cilj:
// Identifikacija sumnjivih obrazaca gde se novac kroz lanac od 
// 2 ili 3 transakcije vraća na polazni račun (ciklus).
//
// Zasto ide u korist grafske baze:
// Neo4j koristi pretragu putanja (pattern matching) koja je 
// optimizovana za detekciju ciklusa u grafu, dok je u SQL-u ovo 
// "skupa" operacija. Relaciona baza mora ili da vrši rekurzivne 
// JOIN-ove nad velikim tabelama ili da materijalizuje putanje 
// putem CTE-a, što drastično povećava kompleksnost i vreme 
// izvršenja kako se dubina pretrage i broj transakcija povećavaju.
MATCH path = (r1:Racun)-[:TRANSAKCIJA*2..3]->(r1)
WHERE ALL(t IN relationships(path) WHERE t.status_trans = 'uspesna')
  AND ALL(i in range(0, size(relationships(path))-2) WHERE relationships(path)[i].datum_vreme_trans < relationships(path)[i+1].datum_vreme_trans)

MATCH (k:Klijent)-[:POSEDUJE]->(r:Racun)
WHERE r IN nodes(path)

RETURN DISTINCT 
    k.id_kli AS sumnjivi_klijent,
    k.ime_kli AS ime,
    k.prezime_kli AS prezime,
    length(path) AS duzina_ciklusa
LIMIT 20;