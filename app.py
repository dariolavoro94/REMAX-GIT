import os
import gunicorn
import sqlite3
import configparser
import re
from flask import Flask, request, g, redirect, url_for, render_template, send_file, flash
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import cm
from reportlab.lib import colors
from werkzeug.utils import secure_filename
from reportlab.lib import colors
from werkzeug.utils import secure_filename
import datetime

# --- CONFIGURAZIONE ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# --- FLASK APP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'metti-qui-una-chiave-segreta'
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'img')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- DATABASE ---
DATABASE = os.path.join(BASE_DIR, 'static', 'clienti.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
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

# --- FILE SVG ---
ALLOWED_EXTENSIONS = {'svg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_client_data(data):
    """Esegue tutte le validazioni dei campi cliente e immobile."""
    
    # --- VALIDAZIONI CLIENTE (OBBLIGATORIE) ---
    
    if not is_valid_name(data['nome_cliente']):
        return "Il nome cliente deve contenere solo lettere ed essere lungo massimo 15 caratteri."
    if not is_valid_name(data['cognome_cliente']):
        return "Il cognome cliente deve contenere solo lettere ed essere lungo massimo 15 caratteri."
    if not is_valid_phone(data['telefono_cliente']):
        return "Telefono cliente non valido: solo numeri, massimo 10 cifre."
 

    # --- VALIDAZIONI BENEFICIARIO (OPZIONALI SE VUOTI) ---
    # Nota: usiamo "data['campo'] and not is_valid..." per accettare la stringa vuota ''
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
    # Aggiungi qui eventuali controlli sul formato data_nascita_beneficiario se necessario.

    # --- VALIDAZIONI IMMOBILE (OBBLIGATORIE) ---
    if not is_valid_number_in_range(data['metri_quadri'], 20, 400):
        return "I metri quadri devono essere compresi tra 20 e 400."
    if not is_valid_number_in_range(data['prezzo_ricercato'], 20000, 600000):
        return "Il prezzo ricercato deve essere compreso tra 20000 e 600000."
    if len(data['richiesta_specifica']) > 300:
        return "La richiesta specifica può contenere al massimo 300 caratteri."

    # Se tutte le validazioni passano, ritorna None (nessun errore)
    return None

# --- VALIDAZIONI CAMPI (CORRETTE PER GESTIRE IL CAMPO VUOTO '') ---

def is_valid_phone(value):
    # Accetta stringa vuota ('') O la verifica che sia numerica e max 10 cifre
    return value == '' or (value.isdigit() and len(value) <= 10)
def is_valid_email(value):
    # Accetta stringa vuota ('') O la verifica con regex
    return value == '' or re.match(r"[^@]+@[^@]+\.[^@]+", value)
def is_valid_name(value, max_length=15):
    # Accetta stringa vuota ('') O la verifica che sia alfabetica e max 15 caratteri
    return value == '' or (value.isalpha() and len(value) <= max_length)
def is_valid_number_in_range(value, min_val, max_val):
    try:
        num = int(value)
        return min_val <= num <= max_val
    except ValueError:
        return False
    

# COMPLEANNO CLIENTI 
def giorni_al_compleanno(data_nascita_str):
    if not data_nascita_str:
        return None # Nessuna data, nessun calcolo
        
    try:
        # Assumiamo che il formato sia 'YYYY-MM-DD' o compatibile con input type="date"
        data_nascita = datetime.datetime.strptime(data_nascita_str, '%Y-%m-%d')
    except ValueError:
        return None # Formato data non valido
        
    oggi = datetime.date.today()
    
    # 1. Calcola il compleanno di quest'anno
    compleanno_questanno = datetime.date(oggi.year, data_nascita.month, data_nascita.day)
    
    # 2. Se il compleanno è già passato, considera quello del prossimo anno
    if compleanno_questanno < oggi:
        compleanno_prossimoanno = datetime.date(oggi.year + 1, data_nascita.month, data_nascita.day)
        differenza = compleanno_prossimoanno - oggi
    else:
        differenza = compleanno_questanno - oggi
        
    return differenza.days

# --- ROUTES ---
@app.route('/')
def home():
    return render_template('/index.html')


@app.route('/iscrivi', methods=['POST'])
def iscrivi_nuovo_cliente():
    # 1. RACCOLTA DATI (Assicurati che tutte le chiavi siano corrette)
    data = {key: request.form.get(key, '') for key in [
        'nome_cliente','cognome_cliente','sesso_cliente','data_nascita','telefono_cliente','email_cliente',
        'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
        'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato','piano','metri_quadri',
        'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica',
        'privacy_accepted' # Aggiungi la privacy
    ]}

    # 2. VALIDAZIONE (Riutilizza la funzione che hai)
    error_message = validate_client_data(data)
    
    # 3. CONTROLLO PRIVACY
    if not data.get('privacy_accepted'):
        error_message = "Devi accettare l'Informativa sulla Privacy per procedere."

    if error_message:
        flash(f"❌ Errore di compilazione: {error_message}")
        # MODIFICA: In caso di errore, torna alla pagina del form
        return redirect(url_for('iscrizione_cliente')) 

    # 4. INSERIMENTO NEL DATABASE (con verifica)
    try:
        db = get_db()
        # Nota: Devi assicurarti che la colonna 'privacy_accepted' esista nel tuo DB
        # Se non esiste, rimuovila da 'data' e dalla lista delle colonne qui sotto
        
        # Rimuoviamo il campo privacy per l'inserimento nel DB se non ne hai la colonna
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

    # 5. REINDIRIZZAMENTO FINALE
    # MODIFICA: In caso di successo o fallimento DB, reindirizza sempre alla pagina del form
    return redirect(url_for('iscrizione_cliente'))



@app.route('/clienti', methods=['GET', 'POST'])
def lista_clienti():
    db = get_db()
    
    # Se devi gestire il filtro 'ristrutturato' (come discusso in precedenza), aggiungi qui la logica POST/GET
    # Per semplicità, qui carichiamo tutti i clienti:
    query = 'SELECT * FROM clienti'
    # Per semplicità, i filtri POST/GET andrebbero qui, ma ignoriamo il post per focalizzarci sui compleanni
    clienti_raw = db.execute(query).fetchall() 

    clienti_compleanni = []
    compleanni_oggi = []
    
    # Elaborazione dei dati:
    for cliente in clienti_raw:
        cliente_dict = dict(cliente) # Converti la riga SQLite in un dizionario modificabile
        
        # CLIENTE PRINCIPALE
        giorni_mancanti_cliente = giorni_al_compleanno(cliente_dict.get('data_nascita'))
        cliente_dict['giorni_mancanti'] = giorni_mancanti_cliente
        
        # Controlla se il compleanno è oggi
        if giorni_mancanti_cliente == 0:
            cliente_dict['compleanno_oggi'] = True
            compleanni_oggi.append(f"{cliente_dict['nome']} {cliente_dict['cognome']} (Cliente)")
        else:
            cliente_dict['compleanno_oggi'] = False

        # BENEFICIARIO (Opzionale: puoi aggiungere la stessa logica se vuoi evidenziare anche i beneficiari)
        giorni_mancanti_beneficiario = giorni_al_compleanno(cliente_dict.get('data_nascita_beneficiario'))
        
        if giorni_mancanti_beneficiario == 0:
            compleanni_oggi.append(f"{cliente_dict['nome_beneficiario']} {cliente_dict['cognome_beneficiario']} (Beneficiario di {cliente_dict['nome']})")
        
        clienti_compleanni.append(cliente_dict)

    num_compleanni = len(compleanni_oggi)
    
    return render_template('clienti.html', 
                           clienti=clienti_compleanni, 
                           compleanni_oggi=compleanni_oggi,
                           num_compleanni=num_compleanni)


# --- NUOVA ROTTA PER LA PRIVACY ---
@app.route('/privacy')
def privacy_policy():
    """Mostra la pagina con l'Informativa sulla Privacy."""
    # Dovrai creare il template HTML chiamato 'privacy.html'
    return render_template('privacy.html')
# --- FINE NUOVA ROTTA ---


@app.route('/aggiungi', methods=['POST'])
def aggiungi_cliente():
    # 1. RACCOLTA DATI
    data = {key: request.form.get(key, '') for key in [
        'nome_cliente','cognome_cliente','sesso_cliente','data_nascita','telefono_cliente','email_cliente',
        'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
        'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato','piano','metri_quadri',
        'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica'
    ]}

    # 2. VALIDAZIONE
    error_message = validate_client_data(data)
    
    if error_message:
        flash(f"❌ Errore di compilazione: {error_message}")
        # MODIFICA 1: In caso di errore, reindirizza alla lista clienti
        return redirect(url_for('lista_clienti')) 

    # 3. INSERIMENTO NEL DATABASE (con verifica)
    try:
        db = get_db()
        cursor = db.execute('''
            INSERT INTO clienti (
                nome, cognome, sesso, data_nascita, telefono, email,
                nome_beneficiario, cognome_beneficiario, sesso_beneficiario, data_nascita_beneficiario,
                telefono_beneficiario, email_beneficiario, tipologia_immobile, ristrutturato, piano, metri_quadri,
                classe_energetica, parcheggio, vicinanza_mare, tipo_proprieta, prezzo_ricercato, richiesta_specifica
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # 4. REINDIRIZZAMENTO FINALE
    # MODIFICA 2: In caso di successo o fallimento DB, reindirizza sempre alla lista clienti
    return redirect(url_for('lista_clienti'))

@app.route('/modifica/<int:id>', methods=['GET', 'POST'])
def modifica_cliente(id):
    db = get_db()
    cliente = db.execute('SELECT * FROM clienti WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        data = {key: request.form.get(key, '') for key in [
            'nome_cliente','cognome_cliente','sesso_cliente','data_nascita','telefono_cliente','email_cliente',
            'nome_beneficiario','cognome_beneficiario','sesso_beneficiario','data_nascita_beneficiario',
            'telefono_beneficiario','email_beneficiario','tipologia_immobile', 'ristrutturato', 'piano','metri_quadri',
            'classe_energetica','parcheggio','vicinanza_mare','tipo_proprieta','prezzo_ricercato','richiesta_specifica'
        ]}

        # CHIAMA LA FUNZIONE UNICA DI VALIDAZIONE
        error_message = validate_client_data(data)

        if error_message:
            flash(error_message)
            # Reindirizza all'URL di modifica, mantenendo l'ID
            return redirect(url_for('modifica_cliente', id=id)) 

        db.execute('''
            UPDATE clienti SET
                nome=?, cognome=?, sesso=?, data_nascita=?, telefono=?, email=?,
                nome_beneficiario=?, cognome_beneficiario=?, sesso_beneficiario=?, data_nascita_beneficiario=?,
                telefono_beneficiario=?, email_beneficiario=?, tipologia_immobile=?, ristrutturato=?, piano=?, metri_quadri=?,
                classe_energetica=?, parcheggio=?, vicinanza_mare=?, tipo_proprieta=?, prezzo_ricercato=?, richiesta_specifica=?
            WHERE id=?
        ''', tuple(data.values()) + (id,))
        db.commit()
        flash("Cliente modificato con successo!")
        return redirect(url_for('lista_clienti'))

    return render_template('modifica_cliente.html', cliente=cliente)


@app.route('/elimina/<int:id>', methods=['POST'])
def elimina_cliente(id):
    db = get_db()
    db.execute('DELETE FROM clienti WHERE id = ?', (id,))
    db.commit()
    flash("Cliente eliminato con successo!")
    return redirect(url_for('lista_clienti'))

# --- ROUTES ---
# ... (altre rotte)

@app.route('/scheda/<int:id>')
def scheda_cliente(id):
    db = get_db()
    cliente = db.execute('SELECT * FROM clienti WHERE id = ?', (id,)).fetchone()
    if not cliente:
        flash("Cliente non trovato")
        return redirect(url_for('lista_clienti'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    # Immagine predefinita
    img_path = os.path.join(app.static_folder, 'img', 'default.png')
    if os.path.exists(img_path):
        story.append(Image(img_path, width=6*cm, height=6*cm))
    story.append(Spacer(1, 1*cm))

    styles = getSampleStyleSheet()
    story.append(Paragraph(f"<b>{cliente['nome']} {cliente['cognome']}</b>", styles['Title']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>SCHEDA CLIENTE</b>", styles['Heading2']))
    story.append(Spacer(1, 0.5*cm))

    for key in cliente.keys():
        if key not in ['nome', 'cognome']:
            story.append(Paragraph(f"<b>{key.replace('_',' ').capitalize()}:</b> {cliente[key]}", styles['Normal']))
            story.append(Spacer(1, 0.2*cm))

    doc.build(story)
    buffer.seek(0)
    
    # --- MODIFICA CHIAVE QUI ---
    # Costruiamo il nome file: "NOME_COGNOME_scheda.pdf"
    # Sostituiamo spazi e rimuoviamo caratteri non validi per i file.
    nome_completo = f"{cliente['nome']}_{cliente['cognome']}"
    nome_file_sicuro = "".join(c for c in nome_completo if c.isalnum() or c in (' ', '_')).rstrip()
    nome_file_finale = f"{nome_file_sicuro}_scheda.pdf"
    # --- FINE MODIFICA CHIAVE ---
    
    return send_file(buffer, 
                     as_attachment=True, 
                     download_name=nome_file_finale,  # Utilizziamo il nuovo nome
                     mimetype='application/pdf')

@app.route('/upload', methods=['POST'])
def upload_svg():
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
# --- AVVIO ---
if __name__ == "__main__":
    # 1. INIZIALIZZAZIONE DEL DATABASE
    # Creiamo un contesto applicativo e chiamiamo la funzione di inizializzazione
    with app.app_context():
        init_db()
        print("✅ Database inizializzato (o già esistente) con la tabella 'clienti'.")
        
    # Avvia il server Flask su tutte le interfacce
    print("✅ Gestionale avviato su http://localhost:5000 (oppure http://<IP_locale>:5000)")
    app.run(host="0.0.0.0", port=5000, debug=True)
