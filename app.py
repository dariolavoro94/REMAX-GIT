import os
import sqlite3
import re
from flask import Flask, request, g, redirect, url_for, render_template, send_file, flash
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import cm
from werkzeug.utils import secure_filename
import datetime

# --- CONFIGURAZIONE ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# --- FLASK APP ---
app = Flask(__name__)
# ASSICURATI DI CAMBIARE QUESTA CHIAVE SEGRETA IN PRODUZIONE!
app.config['SECRET_KEY'] = 'la-tua-chiave-segreta-unica' 
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'img')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- DATABASE ---
DATABASE = os.path.join(BASE_DIR, 'static', 'clienti.db')

def get_db():
    """Stabilisce la connessione al database per la request corrente."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    """Chiude la connessione al database alla fine del contesto applicativo."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inizializza la tabella clienti nel database."""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS clienti (
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
        )
    ''')
    db.commit()

# --- UTILITY E VALIDAZIONE ---
ALLOWED_EXTENSIONS = {'svg'}
def allowed_file(filename):
    """Controlla se l'estensione del file è ammessa (solo SVG)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_phone(value):
    """Valida il formato del numero di telefono (accetta vuoto)."""
    return value == '' or (value.isdigit() and len(value) <= 10)
    
def is_valid_email(value):
    """Valida il formato dell'email (accetta vuoto)."""
    return value == '' or re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value)

def is_valid_name(value, max_length=15):
    """Valida il formato del nome/cognome (accetta vuoto, max 15 caratteri, solo alfabetici)."""
    return value == '' or (value.isalpha() and len(value) <= max_length)
    
def is_valid_number_in_range(value, min_val, max_val):
    """Valida se il valore è un numero intero compreso nel range specificato."""
    try:
        num = int(value)
        return min_val <= num <= max_val
    except ValueError:
        return False
    
def validate_client_data(data):
    """Esegue tutte le validazioni dei campi cliente e immobile."""
    
    # --- VALIDAZIONI CLIENTE (OBBLIGATORIE) ---
    if not is_valid_name(data.get('nome')):
        return "Il nome cliente deve contenere solo lettere ed essere lungo massimo 15 caratteri."
    if not is_valid_name(data.get('cognome')):
        return "Il cognome cliente deve contenere solo lettere ed essere lungo massimo 15 caratteri."
    if not is_valid_phone(data.get('telefono')):
        return "Telefono cliente non valido: solo numeri, massimo 10 cifre."
    
    # --- VALIDAZIONI BENEFICIARIO (OPZIONALI SE VUOTI) ---
    if data['nome_beneficiario'] and not is_valid_name(data['nome_beneficiario']):
          return "Il nome beneficiario non è valido (solo lettere, max 15, o vuoto)."
    if data['cognome_beneficiario'] and not is_valid_name(data['cognome_beneficiario']):
          return "Il cognome beneficiario non è valido (solo lettere, max 15, o vuoto)."
    if data['telefono_beneficiario'] and not is_valid_phone(data['telefono_beneficiario']):
          return "Telefono beneficiario non valido (solo numeri, max 10 cifre, o vuoto)."
    if not is_valid_email(data['email_beneficiario']):
          return "Email beneficiario non valida!"
    if data['sesso_beneficiario'] not in ('M', 'F', ''): 
          return "Sesso beneficiario non valido. Deve essere M, F o vuoto."

    # --- VALIDAZIONI IMMOBILE (OBBLIGATORIE) ---
    if not is_valid_number_in_range(data['metri_quadri'], 20, 400):
        return "I metri quadri devono essere compresi tra 20 e 400."
    if not is_valid_number_in_range(data['prezzo_ricercato'], 20000, 600000):
        return "Il prezzo ricercato deve essere compreso tra 20000 e 600000."
    if len(data['richiesta_specifica']) > 300:
        return "La richiesta specifica può contenere al massimo 300 caratteri."

    return None

def giorni_al_compleanno(data_nascita_str):
    """Calcola i giorni mancanti al compleanno."""
    if not data_nascita_str:
        return None 
        
    try:
        data_nascita = datetime.datetime.strptime(data_nascita_str, '%Y-%m-%d')
    except ValueError:
        return None 
        
    oggi = datetime.date.today()
    compleanno_questanno = datetime.date(oggi.year, data_nascita.month, data_nascita.day)
    
    if compleanno_questanno < oggi:
        compleanno_prossimoanno = datetime.date(oggi.year + 1, data_nascita.month, data_nascita.day)
        differenza = compleanno_prossimoanno - oggi
    else:
        differenza = compleanno_questanno - oggi
        
    return differenza.days

# --- ROTTE ---

@app.route('/')
def home():
    """Mostra la pagina iniziale (home)."""
    return render_template('index.html') 

@app.route('/privacy')
def privacy_policy():
    """Mostra la pagina con l'Informativa sulla Privacy."""
    return render_template('privacy.html')

# ENDPOINT GET PER IL FORM DI ISCRIZIONE (ISCRIZIONE DAL SITO PUBBLICO)
@app.route('/iscrizione_cliente')
def iscrizione_cliente():
    """Mostra la pagina con il form per iscrivere un nuovo cliente."""
    return render_template('iscrizione_cliente.html') 

@app.route('/iscrivi', methods=['POST'])
def iscrivi_nuovo_cliente():
    """Elabora l'iscrizione di un nuovo cliente dal form pubblico (POST)."""
    
    # 1. RACCOLTA DATI (I nomi delle chiavi devono corrispondere alle colonne DB)
    campi_db = ['nome','cognome','sesso','data_nascita','telefono','email', 
                'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
                'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato','piano','metri_quadri',
                'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica']
    
    data = {key: request.form.get(key, '') for key in campi_db}
    data['privacy_accepted'] = request.form.get('privacy_accepted')

    # 2. VALIDAZIONE e CONTROLLO PRIVACY
    error_message = validate_client_data(data)
    
    if not data.get('privacy_accepted'):
        if not error_message:
            error_message = "Devi accettare l'Informativa sulla Privacy per procedere."
        else:
             error_message += " E Devi accettare l'Informativa sulla Privacy per procedere."


    if error_message:
        flash(f"❌ Errore di compilazione: {error_message}")
        # REINDIRIZZAMENTO CORRETTO: usa l'endpoint 'iscrizione_cliente'
        return redirect(url_for('iscrizione_cliente')) 

    # 3. INSERIMENTO NEL DATABASE
    try:
        db = get_db()
        
        # Rimuoviamo il campo privacy prima dell'inserimento
        data.pop('privacy_accepted') 
        
        colonne = list(data.keys())
        placeholder = ', '.join(['?'] * len(colonne))
        
        db.execute(f'''
            INSERT INTO clienti ({', '.join(colonne)}) 
            VALUES ({placeholder})
        ''', tuple(data.values()))
        
        db.commit()
        flash("✅ Iscrizione completata con successo! Verrai ricontattato a breve.")
            
    except sqlite3.Error as e:
        flash(f"❌ Errore Database: Impossibile completare l'iscrizione. Dettagli: {e}", 'error')
        
    except Exception as e:
        flash(f"❌ Errore imprevisto durante l'iscrizione: {e}", 'error')

    return redirect(url_for('iscrizione_cliente'))


# ENDPOINT GET PER IL FORM DI AGGIUNTA MANUALE
@app.route('/aggiungi_form')
def aggiungi_form():
    """Mostra la pagina con il form per aggiungere un nuovo cliente (gestionale)."""
    return render_template('aggiungi_cliente.html') 


@app.route('/aggiungi', methods=['POST'])
def aggiungi_cliente():
    """Elabora l'aggiunta di un nuovo cliente dal form gestionale (POST)."""
    
    campi_db = ['nome','cognome','sesso','data_nascita','telefono','email', 
                'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
                'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato','piano','metri_quadri',
                'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica']

    data = {key: request.form.get(key, '') for key in campi_db}

    error_message = validate_client_data(data)
    
    if error_message:
        flash(f"❌ Errore di compilazione: {error_message}")
        return redirect(url_for('aggiungi_form'))

    try:
        db = get_db()
        colonne = list(data.keys())
        placeholder = ', '.join(['?'] * len(colonne))

        cursor = db.execute(f'''
            INSERT INTO clienti ({', '.join(colonne)}) 
            VALUES ({placeholder})
        ''', tuple(data.values()))
        
        db.commit()

        if cursor.rowcount > 0:
            flash("✅ Cliente aggiunto con successo!")
        else:
            flash("⚠️ Aggiunta fallita. Riprova o contatta il supporto.", 'error')
            
    except sqlite3.Error as e:
        flash(f"❌ Errore Database: Impossibile completare l'aggiunta. Dettagli: {e}", 'error')
        
    except Exception as e:
        flash(f"❌ Errore imprevisto durante l'aggiunta: {e}", 'error')

    return redirect(url_for('lista_clienti'))


@app.route('/clienti', methods=['GET', 'POST'])
def lista_clienti():
    """Mostra la lista dei clienti ed evidenzia i compleanni."""
    db = get_db()
    query = 'SELECT * FROM clienti ORDER BY id DESC' # Ordina per ID decrescente per vedere gli ultimi
    clienti_raw = db.execute(query).fetchall() 

    clienti_compleanni = []
    compleanni_oggi = []
    
    for cliente in clienti_raw:
        cliente_dict = dict(cliente) 
        
        # Gestione compleanno Cliente
        giorni_mancanti_cliente = giorni_al_compleanno(cliente_dict.get('data_nascita'))
        cliente_dict['giorni_mancanti'] = giorni_mancanti_cliente
        
        if giorni_mancanti_cliente == 0:
            cliente_dict['compleanno_oggi'] = True
            compleanni_oggi.append(f"{cliente_dict['nome']} {cliente_dict['cognome']} (Cliente)")
        else:
            cliente_dict['compleanno_oggi'] = False

        # Gestione compleanno Beneficiario
        giorni_mancanti_beneficiario = giorni_al_compleanno(cliente_dict.get('data_nascita_beneficiario'))
        
        if giorni_mancanti_beneficiario == 0 and cliente_dict.get('nome_beneficiario'):
            compleanni_oggi.append(f"{cliente_dict['nome_beneficiario']} {cliente_dict['cognome_beneficiario']} (Beneficiario di {cliente_dict['nome']})")
        
        clienti_compleanni.append(cliente_dict)

    num_compleanni = len(compleanni_oggi)
    
    return render_template('clienti.html', 
                            clienti=clienti_compleanni, 
                            compleanni_oggi=compleanni_oggi,
                            num_compleanni=num_compleanni)


@app.route('/modifica/<int:id>', methods=['GET', 'POST'])
def modifica_cliente(id):
    """Gestisce la visualizzazione e la modifica di un cliente esistente."""
    db = get_db()
    cliente = db.execute('SELECT * FROM clienti WHERE id = ?', (id,)).fetchone()
    
    if not cliente:
        flash("Cliente non trovato")
        return redirect(url_for('lista_clienti'))

    if request.method == 'POST':
        campi_db = ['nome','cognome','sesso','data_nascita','telefono','email', 
                    'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
                    'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato', 'piano','metri_quadri',
                    'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica']
        
        data = {key: request.form.get(key, '') for key in campi_db}

        error_message = validate_client_data(data)

        if error_message:
            flash(error_message)
            return redirect(url_for('modifica_cliente', id=id)) 

        # Esegue l'UPDATE
        valori = list(data.values())
        valori.append(id) 

        db.execute('''
            UPDATE clienti SET
                nome=?, cognome=?, sesso=?, data_nascita=?, telefono=?, email=?,
                nome_beneficiario=?, cognome_beneficiario=?, sesso_beneficiario=?, data_nascita_beneficiario=?,
                telefono_beneficiario=?, email_beneficiario=?, tipologia_immobile=?, ristrutturato=?, piano=?, metri_quadri=?,
                classe_energetica=?, parcheggio=?, vicinanza_mare=?, tipo_proprieta=?, prezzo_ricercato=?, richiesta_specifica=?
            WHERE id=?
        ''', tuple(valori))
        db.commit()
        flash("✅ Cliente modificato con successo!")
        return redirect(url_for('lista_clienti'))

    return render_template('modifica_cliente.html', cliente=cliente)


@app.route('/elimina/<int:id>', methods=['POST'])
def elimina_cliente(id):
    """Elimina un cliente dal database."""
    db = get_db()
    db.execute('DELETE FROM clienti WHERE id = ?', (id,))
    db.commit()
    flash("Cliente eliminato con successo!")
    return redirect(url_for('lista_clienti'))

@app.route('/scheda/<int:id>')
def scheda_cliente(id):
    """Genera e scarica la scheda PDF del cliente."""
    db = get_db()
    cliente = db.execute('SELECT * FROM clienti WHERE id = ?', (id,)).fetchone()
    if not cliente:
        flash("Cliente non trovato")
        return redirect(url_for('lista_clienti'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    # Se l'immagine predefinita esiste, la aggiunge
    img_path = os.path.join(app.static_folder, 'img', 'default.png')
    if os.path.exists(img_path):
        story.append(Image(img_path, width=6*cm, height=6*cm))
    story.append(Spacer(1, 1*cm))

    styles = getSampleStyleSheet()
    story.append(Paragraph(f"<b>{cliente['nome']} {cliente['cognome']}</b>", styles['Title']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>SCHEDA CLIENTE</b>", styles['Heading2']))
    story.append(Spacer(1, 0.5*cm))

    etichette = {
        'nome': 'Nome', 'cognome': 'Cognome', 'sesso': 'Sesso', 'data_nascita': 'Data di Nascita', 
        'telefono': 'Telefono', 'email': 'Email', 
        'nome_beneficiario': 'Nome Beneficiario', 'cognome_beneficiario': 'Cognome Beneficiario', 
        'sesso_beneficiario': 'Sesso Beneficiario', 'data_nascita_beneficiario': 'Data Nascita Beneficiario',
        'telefono_beneficiario': 'Telefono Beneficiario', 'email_beneficiario': 'Email Beneficiario',
        'tipologia_immobile': 'Tipologia Immobile', 'ristrutturato': 'Ristrutturato', 'piano': 'Piano', 
        'metri_quadri': 'Metri Quadri', 'classe_energetica': 'Classe Energetica', 
        'parcheggio': 'Parcheggio', 'vicinanza_mare': 'Vicinanza Mare', 'tipo_proprieta': 'Tipo Proprietà', 
        'prezzo_ricercato': 'Prezzo Ricercato', 'richiesta_specifica': 'Richiesta Specifica', 'id': 'ID'
    }

    # Aggiunge i dettagli del cliente al PDF
    for key, value in cliente.items():
        if key not in ['nome', 'cognome', 'id'] and value:
            story.append(Paragraph(f"<b>{etichette.get(key, key.replace('_',' ').capitalize())}:</b> {value}", styles['Normal']))
            story.append(Spacer(1, 0.2*cm))

    doc.build(story)
    buffer.seek(0)
    
    # Crea un nome file sicuro
    nome_completo = f"{cliente['nome']}_{cliente['cognome']}"
    nome_file_sicuro = re.sub(r'[^\w\-]', '_', nome_completo).replace('__', '_')
    nome_file_finale = f"{nome_file_sicuro}_scheda.pdf"
    
    return send_file(buffer, 
                      as_attachment=True, 
                      download_name=nome_file_finale,
                      mimetype='application/pdf')

@app.route('/upload', methods=['POST'])
def upload_svg():
    """Gestisce il caricamento di file SVG (es. loghi/immagini)."""
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        flash('✅ File caricato con successo!')
    else:
        flash('❌ Solo file SVG ammessi.')
    return redirect(url_for('home'))

# --- AVVIO ---
if __name__ == "__main__":
    # Inizializzazione del database
    with app.app_context():
        init_db()
        print("✅ Database inizializzato (o già esistente) con la tabella 'clienti'.")
        
    print("✅ Gestionale avviato su http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)