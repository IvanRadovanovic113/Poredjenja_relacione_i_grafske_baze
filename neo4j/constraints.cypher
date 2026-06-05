CREATE CONSTRAINT filijala_id IF NOT EXISTS FOR (n:Filijala)    REQUIRE n.id_fil   IS UNIQUE;
CREATE CONSTRAINT bankomat_id IF NOT EXISTS FOR (n:Bankomat)    REQUIRE n.id_bank  IS UNIQUE;
CREATE CONSTRAINT klijent_id  IF NOT EXISTS FOR (n:Klijent)     REQUIRE n.id_kli   IS UNIQUE;
CREATE CONSTRAINT racun_id    IF NOT EXISTS FOR (n:Racun)        REQUIRE n.id_rac   IS UNIQUE;
CREATE CONSTRAINT kartica_id  IF NOT EXISTS FOR (n:Kartica)      REQUIRE n.id_kar   IS UNIQUE;
