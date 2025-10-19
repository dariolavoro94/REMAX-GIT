import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), "static", "clienti.db")
print("DB path:", DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.executescript(r"""CREATE TABLE IF NOT EXISTS clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cognome TEXT,
    sesso TEXT,
    data_nascita TEXT,
    telefono TEXT,
    email TEXT,
    nome_beneficiario TEXT,
    cognome_beneficiario TEXT,
    sesso_beneficiario TEXT,
    data_nascita_beneficiario TEXT,
    telefono_beneficiario TEXT,
    email_beneficiario TEXT,
    tipologia_immobile TEXT,
    ristrutturato TEXT,
    piano TEXT,
    metri_quadri TEXT,
    classe_energetica TEXT,
    parcheggio TEXT,
    vicinanza_mare TEXT,
    tipo_proprieta TEXT,
    prezzo_ricercato TEXT,
    richiesta_specifica TEXT
);""")
conn.commit()
conn.close()
print("DB inizializzato (tabella clienti).")
