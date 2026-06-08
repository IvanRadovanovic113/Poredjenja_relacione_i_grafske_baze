CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE Filijala (
    id_fil      SERIAL PRIMARY KEY,
    naziv_fil   VARCHAR(200) NOT NULL,
    adresa_fil  VARCHAR(300),
    grad_fil    VARCHAR(100)
);

CREATE TABLE Bankomat (
    id_bank         SERIAL PRIMARY KEY,
    lokacija_bank   VARCHAR(300),
    grad_bank       VARCHAR(100)
);

CREATE TABLE Klijent (
    id_kli          SERIAL PRIMARY KEY,
    ime_kli         VARCHAR(100) NOT NULL,
    prezime_kli     VARCHAR(100) NOT NULL,
    email_kli       VARCHAR(200),
    datum_reg_kli   DATE,
    jmbg_kli        VARCHAR(13) UNIQUE,
    telefon_kli     VARCHAR(50),
    adresa_kli      VARCHAR(300),
    grad_kli        VARCHAR(100),
    datum_rodj_kli  DATE,
    tip_kli         VARCHAR(20) CHECK (tip_kli IN ('fizicko lice', 'pravno lice'))
);

CREATE TABLE Racun (
    id_rac               SERIAL PRIMARY KEY,
    broj_rac             VARCHAR(34) UNIQUE NOT NULL,
    tip_rac              VARCHAR(20) CHECK (tip_rac IN ('devizni', 'dinarski', 'stedni')),
    saldo_rac            NUMERIC(15, 2) DEFAULT 0,
    valuta_rac           VARCHAR(3),
    datum_otavaranja_rac DATE,
    limit_rac            NUMERIC(15, 2) DEFAULT 0,
    id_kli               INT NOT NULL REFERENCES Klijent(id_kli),
    id_fil               INT REFERENCES Filijala(id_fil)
);

CREATE TABLE Kartica (
    id_kar              SERIAL PRIMARY KEY,
    broj_kar            VARCHAR(20),
    tip_kar             VARCHAR(20),
    datum_isteka_kar    DATE,
    datum_izdavanja_kar DATE,
    CCV_kar             VARCHAR(3),
    id_rac              INT NOT NULL REFERENCES Racun(id_rac)
);

CREATE TABLE Transakcija (
    id_trans                SERIAL PRIMARY KEY,
    iznos_trans             NUMERIC(15, 2) NOT NULL,
    datum_vreme_trans       TIMESTAMP,
    opis_trans              TEXT,
    status_trans            VARCHAR(20),
    semanticka_grupa_trans  VARCHAR(50),
    embedding_trans         VECTOR(768),
    id_rac_platilac         INT NOT NULL REFERENCES Racun(id_rac),
    id_rac_primalac         INT NOT NULL REFERENCES Racun(id_rac)
);

CREATE TABLE Ima_Punomoc (
    id_kli          INT NOT NULL REFERENCES Klijent(id_kli),
    id_rac          INT NOT NULL REFERENCES Racun(id_rac),
    datum_dodele    DATE,
    nivo_pristupa   VARCHAR(30),
    PRIMARY KEY (id_kli, id_rac)
);

CREATE TABLE Gotovinska_Trans (
    id              SERIAL PRIMARY KEY,
    id_rac          INT NOT NULL REFERENCES Racun(id_rac),
    id_bank         INT NOT NULL REFERENCES Bankomat(id_bank),
    tip_got_trans   VARCHAR(10) CHECK (tip_got_trans IN ('uplata', 'isplata'))
);
