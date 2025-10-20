import os
import sqlite3
import re
import datetime
import configparser
from flask import Flask, request, g, redirect, url_for, render_template, send_file, flash, session, abort
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# --- CONFIGURAZIONE E SETUP ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# ⚠️ CAMBIARE QUESTA CHIAVE SEGRETA
app.config['SECRET_KEY'] = 'CHIAVE_SEGRETA_DEFINITIVA_PER_IL_ROUTING' 
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'img')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Percorsi database e configurazione
CLIENTI_DB = os.path.join(BASE_DIR, 'static', 'clienti.db')
USERS_DB = os.path.join(BASE_DIR, 'static', 'users.db') 
CONFIG_FILE = os.path.join(BASE_DIR, 'config.ini')

# --- GESTIONE DATABASE (FUNZIONI DI UTILITY INFERITE) ---

def get_db(db_path=CLIENTI_DB):
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def get_cliente_by_id_or_404(cliente_id):
    cliente = query_db('SELECT * FROM clienti WHERE id = ?', (cliente_id,), one=True)
    if cliente is None:
        abort(404)
    return cliente

def insert_cliente_from_form(form_data, db_path=CLIENTI_DB):
    # La logica di inserimento effettiva è complessa, qui usiamo un placeholder
    # Assumiamo che la validazione dei dati (date, email, etc.) sia stata fatta.
    db = get_db(db_path)
    # Lista di tutti i campi presenti nel DB (vedi init_db.py)
    campi = [
        'nome', 'cognome', 'sesso', 'data_nascita', 'telefono', 'email', 
        'nome_beneficiario', 'cognome_beneficiario', 'sesso_beneficiario', 
        'data_nascita_beneficiario', 'telefono_beneficiario', 'email_beneficiario',
        'tipologia_immobile', 'ristrutturato', 'piano', 'metri_quadri', 
        'classe_energetica', 'parcheggio', 'vicinanza_mare', 'tipo_proprieta', 
        'prezzo_ricercato', 'richiesta_specifica'
    ]
    
    # Prepara i dati, usando None per i campi mancanti (es. i campi del beneficiario se non spuntato)
    valori = [form_data.get(campo, None) for campo in campi]
    
    placeholders = ', '.join(['?' for _ in campi])
    campi_db = ', '.join(campi)
    
    try:
        db.execute(f"INSERT INTO clienti ({campi_db}) VALUES ({placeholders})", tuple(valori))
        db.commit()
        return True
    except sqlite3.Error as e:
        app.logger.error(f"Errore durante l'inserimento del cliente: {e}")
        return False


# --- GESTIONE UTENTI E AUTENTICAZIONE (INFERITE) ---

def load_admin_config():
    # Funzione per caricare le credenziali dal file config.ini
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if 'DARIO' in config:
        return 'DARIO', config['DARIO']['password']
    return None, None

def get_password_hash(username):
    # Recupera l'hash della password per l'utente dal DB
    user_db = get_db(USERS_DB)
    user = user_db.execute('SELECT password FROM users WHERE username = ?', (username,)).fetchone()
    user_db.close()
    return user['password'] if user else None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Devi effettuare il login per accedere a questa pagina.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# =======================================================
# 📌 ROUTES DEFINITIVE E CORRETTE PER IL ROUTING STABILE
# =======================================================

# 1. HOME PUBBLICA (Nuovo endpoint definitivo per la pagina iniziale)
@app.route('/')
def index():
    """Pagina iniziale pubblica, reindirizza alla dashboard se loggato."""
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# 2. LOGIN (Endpoint aggiornato per coerenza)
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gestisce il processo di login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Logica di verifica:
        try:
            hashed_password = get_password_hash(username)
            if hashed_password and check_password_hash(hashed_password, password):
                session['logged_in'] = True
                session['username'] = username
                flash('Accesso effettuato con successo!', 'success')
                return redirect(url_for('dashboard')) # Reindirizza alla dashboard (Nuova rotta)
            else:
                flash('Nome utente o password non validi.', 'danger')
        except Exception:
            flash('Errore di connessione al database utenti.', 'danger')

    return render_template('login.html')

# 3. LOGOUT
@app.route('/logout')
@login_required
def logout():
    """Gestisce il logout."""
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('Sei stato disconnesso.', 'info')
    return redirect(url_for('index')) # Torna alla home pubblica


# 4. DASHBOARD GESTIONALE (Nuovo endpoint definitivo per l'area riservata)
@app.route('/dashboard')
@login_required
def dashboard():
    """Area riservata principale con form di inserimento rapido."""
    return render_template('inserimento.html')


# 5. INSERIMENTO CLIENTE RAPIDO (Nuovo endpoint POST per la form in dashboard)
@app.route('/inserisci-cliente-rapido', methods=['POST'])
@login_required
def inserisci_cliente_rapido():
    """Elabora l'inserimento rapido dalla dashboard."""
    if insert_cliente_from_form(request.form):
        flash('Cliente inserito rapidamente con successo!', 'success')
    else:
        flash('Errore durante l\'inserimento rapido del cliente.', 'danger')
    return redirect(url_for('dashboard')) # Torna alla dashboard


# 6. ISCRIZIONE CLIENTE PUBBLICA (Form esteso)
@app.route('/iscrizione-cliente', methods=['GET', 'POST'])
def iscrizione_cliente():
    """Pagina pubblica con form completo di iscrizione cliente."""
    if request.method == 'POST':
        if not request.form.get('privacy_accepted'):
            flash('Devi accettare l\'Informativa sulla Privacy.', 'danger')
            return render_template('iscrizione_cliente.html')
            
        if insert_cliente_from_form(request.form):
            flash('Iscrizione completata! Ti contatteremo a breve.', 'success')
            # Inserimento riuscito, reindirizza per evitare re-submission
            return redirect(url_for('iscrizione_cliente')) 
        else:
            flash('Errore durante l\'invio del form. Riprova più tardi.', 'danger')
    
    return render_template('iscrizione_cliente.html')


# 7. LISTA CLIENTI
@app.route('/clienti')
@login_required
def lista_clienti():
    """Visualizza l'elenco completo dei clienti."""
    clienti = query_db('SELECT * FROM clienti')

    # Logica per compleanni (inferita dal template)
    today = datetime.date.today()
    compleanni_oggi = []
    for c in clienti:
        try:
            # Assumiamo che la data sia salvata come 'YYYY-MM-DD'
            data_nascita = datetime.datetime.strptime(c['data_nascita'], '%Y-%m-%d').date()
            if data_nascita.day == today.day and data_nascita.month == today.month:
                compleanni_oggi.append(f"{c['nome']} {c['cognome']}")
        except (ValueError, TypeError):
            # Ignora o logga l'errore per date malformate
            pass

    return render_template('clienti.html', clienti=clienti, compleanni_oggi=compleanni_oggi)


# 8. MODIFICA CLIENTE
@app.route('/modifica-cliente/<int:id>', methods=['GET', 'POST'])
@login_required
def modifica_cliente(id):
    """Gestisce la visualizzazione e l'aggiornamento dei dati di un cliente."""
    cliente = get_cliente_by_id_or_404(id)
    
    if request.method == 'POST':
        # Logica di UPDATE (Placeholder per brevità)
        campi = request.form.keys()
        set_clause = ', '.join([f'{c} = ?' for c in campi])
        valori = list(request.form.values()) + [id]
        
        db = get_db()
        db.execute(f"UPDATE clienti SET {set_clause} WHERE id = ?", tuple(valori))
        db.commit()
        
        flash(f"Dati di {cliente['nome']} {cliente['cognome']} aggiornati con successo.", 'success')
        return redirect(url_for('lista_clienti'))
        
    return render_template('modifica_cliente.html', cliente=cliente)


# 9. ELIMINA CLIENTE
@app.route('/elimina-cliente/<int:id>', methods=['POST'])
@login_required
def elimina_cliente(id):
    """Gestisce l'eliminazione di un cliente."""
    cliente = get_cliente_by_id_or_404(id)
    db = get_db()
    db.execute('DELETE FROM clienti WHERE id = ?', (id,))
    db.commit()
    flash(f"Cliente {cliente['nome']} {cliente['cognome']} eliminato con successo.", 'success')
    return redirect(url_for('lista_clienti'))


# 10. GENERAZIONE PDF
@app.route('/genera-pdf/<int:id>')
@login_required
def genera_pdf(id):
    """Genera e invia un PDF con la scheda cliente."""
    cliente = get_cliente_by_id_or_404(id)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Crea il contenuto del PDF
    story = [
        Paragraph("SCHEDA CLIENTE", styles['Heading1']),
        Spacer(1, 0.5*cm),
        Paragraph(f"<b>DATI PERSONALI</b>", styles['Heading2']),
        Paragraph(f"{cliente['nome']} {cliente['cognome']}", styles['Title']),
        Spacer(1, 0.5*cm),
        Paragraph(f"Telefono: {cliente['telefono']}", styles['Normal']),
        Paragraph(f"Email: {cliente['email']}", styles['Normal']),
        Spacer(1, 0.5*cm),
        Paragraph("<b>RICHIESTA IMMOBILE</b>", styles['Heading2']),
        Paragraph(f"Tipo: {cliente['tipologia_immobile']}, MQ: {cliente['metri_quadri']}", styles['Normal']),
        Paragraph(f"Prezzo Ricercato: {cliente['prezzo_ricercato']}", styles['Normal']),
        Paragraph(f"Note: {cliente['richiesta_specifica']}", styles['Normal']),
    ]
    doc.build(story)
    buffer.seek(0)
    
    nome_completo = f"{cliente['nome']}_{cliente['cognome']}"
    # Sanitizza il nome del file
    nome_file_sicuro = re.sub(r'[^\w\-]', '_', nome_completo).replace('__', '_')
    return send_file(buffer, 
                     as_attachment=True, 
                     download_name=f"{nome_file_sicuro}_scheda.pdf",
                     mimetype='application/pdf')

# 11. PRIVACY POLICY (Placeholder per l'Informativa)
@app.route('/privacy-policy')
def privacy_policy():
    """Pagina di informativa sulla privacy (Placeholder)."""
    return "<h1>Informativa sulla Privacy Placeholder</h1><p>Qui andrà il testo della privacy policy.</p>" # Placeholder


# --- AVVIO ---
if __name__ == "__main__":
    with app.app_context():
        # 1. GESTIONE DELLA PASSWORD: Eseguita solo all'avvio
        admin_username, admin_password = load_admin_config() # Legge entrambi i valori
        if admin_username and admin_password:
            # Crea o aggiorna l'utente admin nel DB users.db
            user_db = get_db(USERS_DB)
            # user_db.execute('DROP TABLE IF EXISTS users') # Scommenta per resettare
            user_db.execute('''CREATE TABLE IF NOT EXISTS users (
                                username TEXT PRIMARY KEY,
                                password TEXT NOT NULL
                            )''')
            
            # Controlla se l'utente esiste e lo aggiorna o inserisce
            existing_user = user_db.execute('SELECT * FROM users WHERE username = ?', (admin_username,)).fetchone()
            hashed_password = generate_password_hash(admin_password)

            if existing_user:
                 # Aggiorna la password (opzionale)
                 user_db.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_password, admin_username))
                 print(f"Utente '{admin_username}' aggiornato in {USERS_DB}")
            else:
                user_db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (admin_username, hashed_password))
                print(f"Utente '{admin_username}' creato in {USERS_DB}")
                
            user_db.commit()
            user_db.close()
        
    app.run(debug=True)