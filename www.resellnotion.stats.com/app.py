from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
from flask import current_app, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import random
import urllib.parse
import psycopg2.extras
import time
from curl_cffi import requests as curlr
from functools import wraps
from decimal import Decimal
import matplotlib
import matplotlib.dates as mdates
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import pandas as pd
import json
import os
import requests
from flask import session, redirect, request, url_for, flash
from flask import Response, stream_with_context, jsonify, request, g, flash, redirect, url_for
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
import io
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import datetime as dt
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, send_from_directory
load_dotenv()

app = Flask(__name__)
app.secret_key = 'resell_notion_ultra_secret_key_2026_!@#'
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session dure 7 jours
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'resell.notion2025@gmail.com'
app.config['MAIL_PASSWORD'] = 'aiym thsq fqwo mbqj'
app.config['MAIL_DEFAULT_SENDER'] = 'resell.notion2025@gmail.com'

mail = Mail(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.needs_refresh_message = "Votre session a expiré, veuillez vous reconnecter."
login_manager.needs_refresh_message_category = "info"
CLIENT_ID = '1473320427140026521'
CLIENT_SECRET = 'Tdg1G4bo7BwvK5eA8TccHut_vY6UeQxf'
# L'URL de redirection doit être EXACTEMENT la même que sur le portail Discord
REDIRECT_URI = 'http://127.0.0.1:8000/callback'
BOT_TOKEN = "MTQ3MzMyMDQyNzE0MDAyNjUyMQ.GJZbib.cOopdBhBRoktehqIoGvGpbmrPcX-yRuHojlIUw"
GUILD_ID = '1387477216392384633'
REQUIRED_ROLE_ID = '1473326555609694269'
TABLE_NAME = "sku_database"
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, '..', 'www.resellnotion.stats.com', 'assets')

UPLOAD_FOLDER = 'static/uploads/storage'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

UPLOAD_FOLDER = 'static/uploads/listings'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

cloudinary.config(
  cloud_name = "dzzhezldw",
  api_key = "861593124633537",
  api_secret = "VIBSETb9zJqhiM2nKjUQitgdu4A",
  secure = True
)
mail = Mail(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def send_gmail_stats(recipient_email, subject, html_body):
    sender_email = "resell.notion2025@gmail.com"
    password = "uheb xlvp ozww tnul"

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"Resell Notion Stats <{sender_email}>"
    message["To"] = recipient_email

    part = MIMEText(html_body, "html")
    message.attach(part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.set_debuglevel(1)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Erreur d'envoi d'email : {e}")
        return False

class UserSession:
    def __init__(self, user_id):
        self.id = user_id
    def get_id(self): return str(self.id)
    def is_active(self): return True
    def is_authenticated(self): return True
    def is_anonymous(self): return False

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_performance_report_email(recipient_email, subject, html_body):
    try:
        msg = Message(subject, recipients=[recipient_email])
        msg.html = html_body
        mail.send(msg)
        print(f"E-mail de bilan envoyé à {recipient_email} avec succès.")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'e-mail à {recipient_email}: {e}")
        return False




def create_bar_chart(x_data_dates, y_data_counts, title, y_label):
    if not x_data_dates or not y_data_counts:
        return None

    plt.style.use('dark_background')
    plt.rcParams['axes.edgecolor'] = 'gray'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['grid.color'] = 'gray'

    fig, ax = plt.subplots(figsize=(12, 6))

    # CORRECTION ICI : Changement de la couleur des barres en bleu cyan (#78b3e8)
    ax.bar(x_data_dates, y_data_counts, color='#78b3e8')

    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel(y_label)
    ax.grid(axis='y', linestyle='--', alpha=0.6)

    # Formater les étiquettes de l'axe des x en fonction de la période
    date_diff = (x_data_dates[-1] - x_data_dates[0]).days
    if date_diff <= 7:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif date_diff <= 31:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

def create_pie_chart(labels, values, title):
    if not labels or not values:
        return None

    plt.style.use('dark_background')
    plt.rcParams['axes.edgecolor'] = 'gray'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['grid.color'] = 'gray'

    fig, ax = plt.subplots(figsize=(10, 8))

    num_colors = len(labels)
    colors_list = [plt.cm.get_cmap('tab20', 20)(i) for i in range(num_colors)]

    wedges, texts, autotexts = ax.pie(values, autopct='%1.1f%%', startangle=90, colors=colors_list,
                                     textprops={'color': 'white'},
                                     pctdistance=0.85)

    ax.axis('equal')
    ax.set_title(title)

    for text in texts:
        text.set_color('white')

    # Correction ici : suppression de 'prop={'color': 'white'}' de l'appel à legend
    legend = ax.legend(wedges, labels, title="Tailles", loc="center left", bbox_to_anchor=(1, 0.5), frameon=False)

    # Définir la couleur du titre de la légende
    plt.setp(legend.get_title(), color='white')

    # NOUVEAU : Définir la couleur de chaque élément de texte dans la légende
    for text in legend.get_texts():
        text.set_color('white')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def create_combined_sales_plot(x_data_dates, y_data_revenue, y_data_profit, title):
    if not x_data_dates or (not y_data_revenue and not y_data_profit):
        return None

    plt.style.use('dark_background')
    plt.rcParams['axes.edgecolor'] = 'gray'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['grid.color'] = 'gray'

    fig, ax = plt.subplots(figsize=(12, 6)) # Taille plus large pour un graphique combiné

    # Tracer le Chiffre d'Affaires
    ax.plot(x_data_dates, y_data_revenue, marker='o', linestyle='-', color='#78b3e8', label='Chiffre d\'Affaires') # Bleu clair
    # Tracer le Bénéfice
    ax.plot(x_data_dates, y_data_profit, marker='x', linestyle='--', color='#28a745', label='Bénéfice') # Vert

    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel('Montant (€)')
    ax.grid(True, linestyle='--', alpha=0.6)

    # Formater les étiquettes de l'axe des x en fonction de la période
    date_diff = (x_data_dates[-1] - x_data_dates[0]).days # Différence en jours entre la dernière et la première date

    if date_diff <= 7: # Pour une semaine (affiche chaque jour)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d')) # Ex: Lun 01, Mar 02
        ax.xaxis.set_major_locator(mdates.DayLocator()) # Tick pour chaque jour
    elif date_diff <= 31: # Pour un mois (affiche tous les 2 jours pour éviter le chevauchement)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d')) # Ex: Jan 01, Jan 03
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2)) # Tick tous les 2 jours
    else: # Pour des périodes plus longues (affiche une fois par semaine)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d')) # Ex: 2023-01-01
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1)) # Tick une fois par semaine


    plt.xticks(rotation=45, ha='right') # Rotation des labels pour la lisibilité
    ax.legend() # Ajoute la légende pour les deux courbes

    plt.tight_layout() # Ajuste la mise en page pour éviter les chevauchements

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig) # Ferme la figure pour libérer la mémoire
    return img_base64

# --- Décorateur personnalisé pour vérifier le statut de la clé ---
def key_active_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # S'assure que l'utilisateur est bien connecté (normalement géré par @login_required avant)
        if not current_user.is_authenticated:
            # Flask-Login gérera déjà la redirection vers la page de login
            return login_manager.unauthorized()

        # Vérifie si le statut de la clé est 'inactive'
        if current_user.key_status == 'inactive':
            flash("Votre clé est inactive. Veuillez la réactiver via le bot Discord pour accéder au contenu.", "warning")
            return redirect(url_for('key_activation_required'))
        # Si la clé est active, ou que l'utilisateur est admin (si vous voulez exempter les admins)
        return f(*args, **kwargs)
    return decorated_function


def clean_val(value):
    """Nettoie une chaîne pour la convertir en float (enlève €, $, espaces, change virgule en point)"""
    if value is None or str(value).strip() == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    # Nettoyage complet
    cleaned = str(value).replace('€', '').replace('$', '').strip()
    cleaned = cleaned.replace('\xa0', '')  # Espaces insécables Excel
    cleaned = cleaned.replace(' ', '')  # Espaces classiques
    cleaned = cleaned.replace(',', '.')  # Format européen vers standard

    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- Classe User pour Flask-Login (MISES À JOUR ICI) ---
class User(UserMixin):
    def __init__(self, id, email, username, avatar_url, is_admin, discord_id, key_status):
        self.id = id
        self.email = email
        self.username = username
        self.avatar_url = avatar_url
        self.is_admin = is_admin
        self.discord_id = discord_id
        self.key_status = key_status

    @staticmethod
    def get(user_id):
        # Utilise la connexion existante dans le contexte de l'application (g.db)
        # N'appelez PLUS get_db_connection() directement ici
        conn = g.db
        # Crée un curseur pour exécuter la requête
        # psycopg2.extras.RealDictCursor permet d'accéder aux colonnes par leur nom comme avec sqlite3.Row
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Exécute la requête avec le placeholder '%s' pour PostgreSQL
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()  # Récupère les données du curseur
        cur.close()  # Ferme le curseur après utilisation

        # La connexion 'conn' (g.db) est fermée automatiquement par @app.teardown_appcontext

        if user_data:
            return User(
                id=user_data['id'],
                email=user_data['email'],
                username=user_data['username'],
                avatar_url=user_data['avatar_url'],
                is_admin=bool(user_data['is_admin']),
                discord_id=user_data['discord_id'],
                key_status=user_data['key_status']
            )
        return None

# Récupérez l'URL de la base de données depuis les variables d'environnement de Render

DATABASE_URL = "postgresql://database_resell_notion_stats_user:S93nJbBAUHQR1TimsIH4HfBHxtYCIRJy@dpg-d1v824qdbo4c73f9onog-a.oregon-postgres.render.com/database_resell_notion_stats"
print(f"DEBUG: DATABASE_URL lue : '{DATABASE_URL}'") # Laissez le print

if not DATABASE_URL:
    # Fallback pour le développement local si DATABASE_URL n'est pas défini
    # Vous devrez configurer une base de données PostgreSQL locale pour ce cas
    print("DATABASE_URL non défini. Assurez-vous d'avoir configuré votre base de données Render et/ou une DB locale.")
    raise ValueError("DATABASE_URL n'est pas défini. L'application ne peut pas se connecter à la base de données.")

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db


# Nouvelle fonction pour obtenir une connexion à la DB (retourne un objet connexion psycopg2)
def get_db_connection():
    result = urlparse(DATABASE_URL)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port

    conn = psycopg2.connect(
        host=hostname,
        database=database,
        user=username,
        password=password,
        port=port
    )
    return conn


def get_quantum_proxy():
    """Récupère un proxy depuis ton fichier de 250 proxies Quantum."""
    proxy_path = os.path.join('static', 'proxy_tracker.txt')
    try:
        with open(proxy_path, 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        if not lines: return None
        line = random.choice(lines)
        host, port, user, password = line.split(':')
        # Encodage pour les caractères spéciaux Quantum
        return f"http://{urllib.parse.quote(user)}:{urllib.parse.quote(password)}@{host}:{port}"
    except: return None
# Gérer la connexion à la base de données pour chaque requête
@app.before_request
def before_request():
    # Ouvre une connexion à la DB et la stocke dans l'objet 'g' global de Flask
    # Cela évite d'ouvrir/fermer la connexion dans chaque route
    g.db = get_db_connection()

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Accès non autorisé. Vous devez être administrateur.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

SKU_DATA = []
SKU_FILE_PATH = os.path.join(ASSETS_DIR, 'sku_img_with_name.json')
try:
    if os.path.exists(SKU_FILE_PATH):
        with open(SKU_FILE_PATH, 'r', encoding='utf-8') as f:
            SKU_DATA = json.load(f)
        print(f"SKU data loaded successfully from: {SKU_FILE_PATH}")
    else:
        print(f"Erreur: Le fichier sku_img.json n'a pas été trouvé à l'emplacement: {SKU_FILE_PATH}")
        print("L'auto-complétion des SKU ne fonctionnera pas.")
except Exception as e:
    print(f"Erreur lors du chargement des données SKU depuis le fichier {SKU_FILE_PATH}: {e}")
    SKU_DATA = []

# USERS

@app.route('/storage', methods=['GET', 'POST'])
@login_required
def storage():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content')
        file = request.files.get('file')
        file_url = None

        if file and file.filename != '':
            try:
                # Envoi direct vers Cloudinary dans un dossier spécifique
                upload_result = cloudinary.uploader.upload(file, folder="resell_notion_storage")
                file_url = upload_result['secure_url'] # L'URL permanente
            except Exception as e:
                flash(f"Erreur Cloudinary : {e}", "danger")
                return redirect(url_for('storage'))

        try:
            cur.execute("""
                INSERT INTO user_storage (user_id, title, category, content, file_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (current_user.id, title, category, content, file_url))
            conn.commit()
            flash("Élément sauvegardé sur le Cloud permanent.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Erreur DB : {e}", "danger")
        return redirect(url_for('storage'))

    cur.execute("SELECT * FROM user_storage WHERE user_id = %s ORDER BY created_at DESC", (current_user.id,))
    items = cur.fetchall()
    cur.close()
    return render_template('storage.html', items=items)

@app.route('/storage/item/<int:item_id>')
@login_required
def view_storage_item(item_id):
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM user_storage WHERE id = %s AND user_id = %s", (item_id, current_user.id))
    item = cur.fetchone()
    cur.close()
    if not item:
        flash("Document introuvable.", "danger")
        return redirect(url_for('storage'))
    return render_template('view_storage_item.html', item=item)

@app.route('/storage/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_storage_item(item_id):
    conn = g.db
    cur = conn.cursor()
    cur.execute("DELETE FROM user_storage WHERE id = %s AND user_id = %s", (item_id, current_user.id))
    conn.commit()
    cur.close()
    flash("Élément supprimé de votre Cloud.", "info")
    return redirect(url_for('storage'))

@app.route('/storage/file/<int:item_id>')
@login_required
def get_storage_file(item_id):
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT file_path FROM user_storage WHERE id = %s AND user_id = %s", (item_id, current_user.id))
    item = cur.fetchone()
    cur.close()

    if not item or not item['file_path']:
        print("DEBUG: Aucun chemin de fichier trouvé en base de données.")
        abort(404)

    # On récupère uniquement le nom du fichier (au cas où le chemin complet soit stocké)
    filename = os.path.basename(item['file_path'])
    # Construction du chemin absolu pour éviter toute erreur Windows/Linux
    full_path = os.path.abspath(os.path.join('static', 'uploads', 'storage', filename))

    print(f"DEBUG: Tentative d'ouverture du fichier : {full_path}")

    if not os.path.exists(full_path):
        print(f"DEBUG: Le fichier n'existe pas physiquement à l'adresse : {full_path}")
        abort(404)

    return send_file(full_path)

@app.route('/supplementary-operations', methods=['GET', 'POST'])
@login_required
def supplementary_operations():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    user_id = current_user.id

    if request.method == 'POST':
        # 1. Récupération des données du formulaire
        op_type = request.form.get('type')
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        # Si la date n'est pas remplie, on prend la date du jour
        op_date = request.form.get('operation_date') or datetime.now().strftime('%Y-%m-%d')

        try:
            # 2. Insertion dans la table supplementary_operations
            cur.execute("""
                INSERT INTO supplementary_operations (user_id, type, amount, description, operation_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, op_type, amount, description, op_date))
            conn.commit()
            flash("Opération enregistrée avec succès !", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Erreur lors de l'enregistrement : {str(e)}", "danger")
        return redirect(url_for('supplementary_operations'))

    # --- Lecture des données pour l'affichage ---

    # Récupérer l'historique complet
    cur.execute("""
        SELECT id, type, amount, description, operation_date 
        FROM supplementary_operations 
        WHERE user_id = %s 
        ORDER BY operation_date DESC, created_at DESC
    """, (user_id,))
    operations = cur.fetchall()

    # Calcul du montant cumulé (Bénéfice/Déficit hors ventes)
    cur.execute("SELECT SUM(amount) as total FROM supplementary_operations WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    total_balance = float(result['total'] or 0)

    return render_template('supplementary_operations.html',
                           operations=operations,
                           total_balance=total_balance)


@app.route('/delete-operation/<int:op_id>', methods=['POST'])
@login_required
def delete_operation(op_id):
    conn = g.db
    cur = conn.cursor()
    user_id = current_user.id

    try:
        # On vérifie que l'ID appartient bien à l'utilisateur pour la sécurité
        cur.execute("DELETE FROM supplementary_operations WHERE id = %s AND user_id = %s", (op_id, user_id))
        conn.commit()
        flash("Opération supprimée.", "info")
    except Exception as e:
        conn.rollback()
        flash(f"Erreur lors de la suppression : {str(e)}", "danger")

    return redirect(url_for('supplementary_operations'))

@app.route('/badges')
@login_required
def show_badges():
    conn = g.db
    cur = None
    try:
        cur = conn.cursor()
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        cur.execute('''
            SELECT SUM(profit) 
            FROM sales 
            WHERE user_id = %s 
            AND EXTRACT(MONTH FROM sale_date) = %s
            AND EXTRACT(YEAR FROM sale_date) = %s
        ''', (current_user.id, current_month, current_year))
        result = cur.fetchone()
        total_sales_profit = float(result[0]) if result and result[0] is not None else 0.0
        return render_template('badges.html', total_sales_profit=total_sales_profit)
    except Exception as e:
        print(f"--- ERREUR CALCUL BADGES MENSUELS ---")
        print(f"Détails : {e}")
        flash(f"Erreur lors du calcul de vos statistiques mensuelles.", 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cur and not cur.closed:
            cur.close()
@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']
        if not username or not email or not password:
            flash('Veuillez remplir tous les champs.', 'danger')
            return render_template('register.html', email=email, username=username)
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = g.db
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cur.fetchone()
            cur.close()
            if existing_user:
                flash("Cet email est déjà enregistré. Veuillez en utiliser un autre ou vous connecter.", "danger")
                return render_template('register.html', email=email, username=username)
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password_hash, username) VALUES (%s, %s, %s)",
                        (email, hashed_password, username))
            conn.commit()
            cur.close()
            flash("Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash(f"Une erreur est survenue lors de l'enregistrement: {e}", "danger")
            print(f"Erreur lors de l'enregistrement de l'utilisateur: {e}")
            return render_template('register.html', email=email, username=username)
    return render_template('register.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    # Modification 1 : Si l'utilisateur est déjà connecté, on redirige directement sans vérifier la clé
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form
        conn = g.db
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cur.fetchone()
            cur.close()

            if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
                user = User(
                    id=user_data['id'],
                    email=user_data['email'],
                    username=user_data['username'],
                    avatar_url=user_data['avatar_url'],
                    is_admin=bool(user_data['is_admin']),
                    discord_id=user_data['discord_id'],
                    key_status=user_data['key_status']
                )
                login_user(user, remember=remember)

                # Modification 2 : Suppression du bloc "if user.key_status == 'inactive'"
                # On passe directement au succès
                flash("Connexion réussie !", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Email ou mot de passe incorrect.", "danger")
        except Exception as e:
            flash(f"Une erreur est survenue lors de la connexion: {e}", 'danger')
            print(f"Erreur de connexion: {e}")  # Pour le débogage

    return render_template('login.html')
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    # --- VERIFICATION DISCORD ---
    if not session.get('discord_auth'):
        flash("Veuillez vous connecter avec Discord pour accéder au tableau de bord.", "warning")
        return redirect(url_for('login_discord'))
    # ----------------------------

    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        today = date.today()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        # 1. Calcul du nombre de produits en stock
        cur.execute("SELECT SUM(quantity) FROM products WHERE user_id = %s", (current_user.id,))
        products_in_stock_query = cur.fetchone()
        products_in_stock = products_in_stock_query['sum'] if products_in_stock_query and products_in_stock_query['sum'] is not None else 0

        # 2. Valeur totale du stock
        cur.execute("SELECT SUM(purchase_price * quantity) FROM products WHERE user_id = %s", (current_user.id,))
        total_stock_value_query = cur.fetchone()
        total_stock_value = total_stock_value_query['sum'] if total_stock_value_query and total_stock_value_query['sum'] is not None else Decimal('0.00')

        # 3. Calcul du bénéfice total (Ventes + Opérations Supplémentaires)
        # --- Partie A : Profit des ventes ---
        cur.execute("""
            SELECT SUM(profit) FROM sales 
            WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s
        """, (current_user.id, start_of_month, end_of_month))
        sales_res = cur.fetchone()
        total_sales_profit = sales_res['sum'] if sales_res and sales_res['sum'] is not None else Decimal('0.00')

        # --- Partie B : Montant des opérations supplémentaires ---
        cur.execute("""
            SELECT SUM(amount) FROM supplementary_operations 
            WHERE user_id = %s AND operation_date >= %s AND operation_date <= %s
        """, (current_user.id, start_of_month, end_of_month))
        ops_res = cur.fetchone()
        total_ops_amount = ops_res['sum'] if ops_res and ops_res['sum'] is not None else Decimal('0.00')

        # --- Partie C : Calcul du Bénéfice Net ---
        total_net_profit = total_sales_profit + total_ops_amount

        # 4. Calcul du chiffre d'affaires pour le mois en cours
        cur.execute("SELECT SUM(sale_price) FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s", (current_user.id, start_of_month, end_of_month))
        total_revenue_query = cur.fetchone()
        total_revenue = total_revenue_query['sum'] if total_revenue_query and total_revenue_query['sum'] is not None else Decimal('0.00')

        # 7. Calcul du total des paiements en attente
        cur.execute("SELECT COALESCE(SUM(sale_price), 0) FROM sales WHERE user_id = %s AND payment_status = 'en_attente'", (current_user.id,))
        total_pending_payments_query = cur.fetchone()
        total_pending_payments = total_pending_payments_query['coalesce'] if total_pending_payments_query else Decimal('0.00')

        # 8. Récupération des 5 dernières ventes
        cur.execute('''
            SELECT 
                s.item_name, s.quantity, s.sale_price, s.sale_date, s.profit,
                COALESCE(s.sku, p.sku) as sku, 
                COALESCE(s.size, p.size) as size,
                COALESCE(s.image_url, p.image_url) as image_url
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.id
            WHERE s.user_id = %s
            ORDER BY s.sale_date DESC, s.id DESC
            LIMIT 5
        ''', (current_user.id,))
        latest_sales_raw = cur.fetchall()

        latest_sales_for_template = []
        for sale in latest_sales_raw:
            sale_dict = dict(sale)
            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'
            sale_dict['image_url'] = sale['image_url'] if sale['image_url'] else None
            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(float(sale_dict['sale_price'] or 0.0))
            sale_dict['profit_formatted'] = '{:.2f} €'.format(float(sale_dict['profit'] or 0.0))
            latest_sales_for_template.append(sale_dict)

        # Rendu avec l'ajout des variables manquantes (net_profit et ops_amount)
        return render_template('dashboard.html',
                               total_stock_value=total_stock_value,
                               total_sales_profit=total_sales_profit,
                               total_ops_amount=total_ops_amount,
                               total_net_profit=total_net_profit,
                               total_revenue=total_revenue,
                               total_pending_payments=total_pending_payments,
                               latest_sales=latest_sales_for_template)

    except Exception as e:
        flash(f"Erreur tableau de bord: {e}", 'danger')
        return redirect(url_for('login'))
    finally:
        if cur: cur.close()
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = g.db
    cur = None
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        new_password = request.form.get('password')

        if not new_username or not new_email:
            flash("Le nom d'utilisateur et l'email ne peuvent pas être vides.", "danger")
            return render_template('profile.html', user=current_user)

        try:
            cur = conn.cursor()

            # Si un nouveau mot de passe est saisi, on le hache et on met tout à jour
            if new_password and new_password.strip() != "":
                hashed_pw = generate_password_hash(new_password)
                cur.execute(
                    "UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s",
                    (new_username, new_email, hashed_pw, current_user.id)
                )
            else:
                # Sinon, on ne met à jour que le nom et l'email
                cur.execute(
                    "UPDATE users SET username = %s, email = %s WHERE id = %s",
                    (new_username, new_email, current_user.id)
                )

            conn.commit()

            # Mise à jour de l'objet en session
            current_user.username = new_username
            current_user.email = new_email

            flash("Votre profil a été mis à jour avec succès !", "success")
            return redirect(url_for('profile'))

        except Exception as e:
            conn.rollback()
            flash(f"Une erreur est survenue lors de la mise à jour : {e}", "danger")
            print(f"Error updating profile: {e}")
        finally:
            if cur: cur.close()

    return render_template('profile.html', user=current_user)

@app.route('/leaderboard')
@login_required
def leaderboard():
    conn = g.db
    cur = None
    leaderboard_data = []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                cu.user_id,  -- AJOUTÉ : Pour que l'ID utilisateur soit disponible pour la comparaison
                cu.total_ca,
                cu.total_benefice,
                u.username,
                ROW_NUMBER() OVER (ORDER BY cu.total_ca DESC) as rank_ca,
                ROW_NUMBER() OVER (ORDER BY cu.total_benefice DESC) as rank_benefice
            FROM
                classement_utilisateurs cu
            JOIN
                users u ON cu.user_id = u.id
            ORDER BY
                cu.total_ca DESC; -- Tri principal par chiffre d'affaires
            """
        )
        leaderboard_data = cur.fetchall()
    except Exception as e:
        flash(f"Erreur lors du chargement du classement : {e}", "danger")
        print(f"DEBUG: Erreur de chargement leaderboard : {e}")
    finally:
        if cur and not cur.closed:
            cur.close()
    return render_template('leaderboard.html', leaderboard=leaderboard_data)



# PRODUCTS
@app.route('/get_sku_suggestions', methods=['GET'])
@login_required
def get_sku_suggestions():
    query = request.args.get('query', '').strip()
    suggestions = []
    if not query:
        return jsonify(suggestions)
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Impossible de se connecter à la base de données."}), 500
        cur = conn.cursor()
        search_pattern = f"%{query}%"
        sql_query = f"""
            SELECT sku, image_url, product_name
            FROM {TABLE_NAME}
            WHERE sku ILIKE %s OR product_name ILIKE %s
            LIMIT 10;
        """
        cur.execute(sql_query, (search_pattern, search_pattern))
        results = cur.fetchall()
        for row in results:
            suggestions.append({
                'sku': row[0],
                'image_url': row[1],
                'product_name': row[2]
            })
        cur.close()
        conn.close()
        return jsonify(suggestions)
    except Exception as e:
        print(f"Erreur lors de la récupération des suggestions de SKU : {e}")
        return jsonify({"error": f"Une erreur est survenue lors de la recherche de SKU: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/products/add', methods=('GET', 'POST'))
@login_required
def add_product():
    if request.method == 'POST':
        sku = request.form.get('sku', '')
        name = request.form.get('name', '')
        image_url = request.form.get('image_url', '')
        description = request.form.get('description', '')
        sizes = request.form.getlist('sizes[]')
        prices_str = request.form.getlist('prices[]')
        if not sku or not name:
            flash('La référence SKU et le nom sont requis.', 'danger')
            return redirect(url_for('add_product'))
        if not sizes or not prices_str:
            flash('Veuillez ajouter au moins une taille et un prix.', 'danger')
            return redirect(url_for('add_product'))
        if len(sizes) != len(prices_str):
            flash('Erreur de formulaire: le nombre de tailles et de prix ne correspond pas.', 'danger')
            return redirect(url_for('add_product'))
        conn = g.db
        cur = conn.cursor()
        try:
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for size, price_str in zip(sizes, prices_str):
                try:
                    purchase_price = float(price_str)
                    quantity = 1
                except ValueError:
                    flash(f'Erreur de format pour le prix "{price_str}". Veuillez entrer un nombre valide.', 'danger')
                    conn.rollback()
                    return redirect(url_for('add_product'))
                cur.execute(
                    'INSERT INTO products (user_id, sku, name, size, purchase_price, quantity, price, description, image_url, date_added) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    (current_user.id, sku, name, size, purchase_price, quantity, purchase_price, description, image_url,
                     current_date)
                )
            conn.commit()
            flash(f'{len(sizes)} produit(s) ajouté(s) avec succès !', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            conn.rollback()
            flash(f'Une erreur est survenue lors de l\'ajout des produits : {e}', 'danger')
            return redirect(url_for('add_product'))
        finally:
            cur.close()
    return render_template('add_product.html',
                           sku='',
                           name='',
                           image_url='',
                           description='')

def get_product_name_suggestions():
    query = request.args.get('query', '').strip()  # .strip() pour enlever les espaces inutiles
    suggestions = []
    if not query:
        return jsonify(suggestions)  # Retourne une liste vide si la requête est vide
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Impossible de se connecter à la base de données."}), 500
        cur = conn.cursor()
        search_pattern = f"%{query}%"
        sql_query = f"""
            SELECT sku, product_name, image_url
            FROM {TABLE_NAME}
            WHERE product_name ILIKE %s OR sku ILIKE %s
            LIMIT 10;
        """
        cur.execute(sql_query, (search_pattern, search_pattern))
        results = cur.fetchall()
        for row in results:
            suggestions.append({
                'sku': row[0],
                'name': row[1],
                'image_url': row[2]
            })
        cur.close()
        conn.close()  # Toujours fermer la connexion
        return jsonify(suggestions)
    except Exception as e:
        print(f"Erreur lors de la récupération des suggestions : {e}")
        return jsonify({"error": f"Une erreur est survenue lors de la recherche: {e}"}), 500
    finally:
        if conn:
            conn.close()
@app.route('/get_product_name_suggestions', methods=['GET'])
@login_required
def get_product_name_suggestions():
    query = request.args.get('query', '').strip()
    suggestions = []
    if not query:
        return jsonify(suggestions)
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Impossible de se connecter à la base de données."}), 500
        cur = conn.cursor()
        search_pattern = f"%{query}%"
        sql_query = f"""
            SELECT sku, product_name, image_url
            FROM {TABLE_NAME}
            WHERE product_name ILIKE %s OR sku ILIKE %s
            LIMIT 10;
        """
        cur.execute(sql_query, (search_pattern, search_pattern))
        results = cur.fetchall()
        for row in results:
            suggestions.append({
                'sku': row[0],
                'name': row[1],
                'image_url': row[2]
            })
        cur.close()
        conn.close()
        return jsonify(suggestions)
    except Exception as e:
        print(f"Erreur lors de la récupération des suggestions : {e}")
        return jsonify({"error": f"Une erreur est survenue lors de la recherche: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/products/<int:id>/edit', methods=('GET', 'POST'))
@login_required
def edit_product(id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur pour la sélection
        cur.execute('SELECT * FROM products WHERE id = %s AND user_id = %s',
                               (id, current_user.id))
        product = cur.fetchone()
        cur.close()
        if product is None:
            abort(404)
        if request.method == 'POST':
            sku = request.form['sku']
            name = request.form['name']
            size = request.form.get('size')
            purchase_price = request.form['purchase_price']
            quantity = request.form['quantity']
            image_url = request.form.get('image_url')
            if not sku or not name or not purchase_price or not quantity:
                flash('Veuillez remplir tous les champs obligatoires.', 'danger')
                return render_template('edit_product.html', product=product)
            try:
                purchase_price = float(purchase_price)
                quantity = int(quantity)
            except ValueError:
                flash('Le prix d\'achat et la quantité doivent être des nombres valides.', 'danger')
                return render_template('edit_product.html', product=product)
            cur = conn.cursor()
            cur.execute(
                "UPDATE products SET sku = %s, name = %s, size = %s, purchase_price = %s, quantity = %s, image_url = %s WHERE id = %s AND user_id = %s", # Placeholders %s
                (sku, name, size, purchase_price, quantity, image_url, id, current_user.id))
            conn.commit()
            flash('Produit mis à jour avec succès !', 'success')
            return redirect(url_for('products'))
    except psycopg2.IntegrityError as e:
        conn.rollback()
        if 'duplicate key value violates unique constraint "products_sku_key"' in str(e): # Exemple de message PostgreSQL
            flash('Un produit avec ce SKU existe déjà. Veuillez utiliser une référence unique.', 'danger')
        else:
            flash(f"Une erreur d'intégrité est survenue lors de la mise à jour du produit : {e}", 'danger')
        print(f"Database IntegrityError on product edit: {e}")
        return render_template('edit_product.html', product=product)
    except Exception as e:
        conn.rollback()
        flash(f"Une erreur inattendue est survenue : {e}", "danger")
        print(f"Error editing product: {e}")
        return render_template('edit_product.html', product=product)
    finally:
        if cur and not cur.closed:
            cur.close()
    return render_template('edit_product.html', product=product)

@app.route('/products/<int:id>/delete', methods=('POST',))
@login_required
def delete_product(id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT id FROM products WHERE id = %s AND user_id = %s',
                               (id, current_user.id))
        product = cur.fetchone()
        cur.close()
        if product is None:
            abort(404)
        cur = conn.cursor()
        cur.execute('DELETE FROM products WHERE id = %s AND user_id = %s', (id, current_user.id))
        conn.commit()
        flash('Produit supprimé avec succès !', 'success')
        return redirect(url_for('products'))
    except Exception as e:
        conn.rollback()
        flash(f"Une erreur est survenue lors de la suppression du produit : {e}", 'danger')
        print(f"Erreur suppression produit: {e}")
        return redirect(url_for('products'))
    finally:
        if cur and not cur.closed:
            cur.close()


# --- Mise à jour de la route existante ---
@app.route('/products')
@login_required
def products():
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''
            SELECT id, sku, name, size, purchase_price, quantity, price, image_url, 
                   date_added, tracking_number, shipping_status 
            FROM products 
            WHERE user_id = %s AND quantity > 0 
            ORDER BY date_added DESC
        ''', (current_user.id,))
        products_data = cur.fetchall()

        # --- LOGIQUE DE CALCUL DES INDICATEURS ---
        total_value = 0.0
        present_value = 0.0
        transit_value = 0.0

        for p in products_data:
            price = float(p['purchase_price'] or 0)
            total_value += price

            status = (p['shipping_status'] or "").upper()
            if p['tracking_number'] and status != 'DELIVERED' and "LIVRÉ" not in status:
                transit_value += price
            else:
                present_value += price

        cur.execute('SELECT DISTINCT size FROM products WHERE user_id = %s', (current_user.id,))
        available_sizes = [row['size'] for row in cur.fetchall()]

        # On transmet le type 'product' pour l'appel API universel
        return render_template('products.html',
                               products=products_data,
                               available_sizes=available_sizes,
                               total_value=total_value,
                               present_value=present_value,
                               transit_value=transit_value,
                               item_type='product')

    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement des produits: {e}", 'danger')
        return redirect(url_for('dashboard'))

    finally:
        if cur and not cur.closed:
            cur.close()

# --- MAINTENANT TU PEUX AJOUTER LA NOUVELLE ROUTE ---

@app.route('/api/track-live', methods=['POST'])
@login_required
def track_live_universal():
    data = request.json
    num = data.get('tracking_number')
    item_id = data.get('item_id')
    item_type = data.get('item_type')
    save_to_db = data.get('save', False)

    config = {'product': {'table': 'products'}, 'sale': {'table': 'sales'}}
    if item_type not in config:
        return jsonify({"success": False, "message": "Type invalide"}), 400

    max_retries = 3  # Nombre de tentatives avec des proxys différents
    attempt = 0
    last_error = ""

    while attempt < max_retries:
        attempt += 1
        session = requests.Session()
        proxy_url = get_quantum_proxy()  # On récupère un nouveau nœud à chaque essai

        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            'authority': 'api.ordertracker.com',
            'accept': 'application/json, text/plain, */*',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'referer': 'https://www.ordertracker.com/',
            'origin': 'https://www.ordertracker.com',
            'accept-language': 'fr-FR,fr;q=0.9',
            'content-type': 'application/json'
        }

        try:
            # ÉTAPE 1 : Init
            url_html = f"https://www.ordertracker.com/fr/track/{num}"
            session.get(url_html, headers=headers, timeout=15)
            time.sleep(1)

            # ÉTAPE 2 : Links
            url_links = f"https://api.ordertracker.com/public/trackinglinks?trackingstring={num}"
            headers['referer'] = url_html
            session.get(url_links, headers=headers, timeout=15)

            # ÉTAPE 3 : Final
            url_final = f"https://api.ordertracker.com/public/track/{num}?lang=FR"
            response = session.get(url_final, headers=headers, timeout=15)

            if response.status_code == 200:
                res_data = response.json()
                status_label = res_data.get('statusLabel', 'En transit')

                if save_to_db and item_id:
                    table_name = config[item_type]['table']
                    cur = g.db.cursor()
                    query = f"UPDATE {table_name} SET tracking_number=%s, shipping_status=%s, tracking_data=%s, last_tracking_update=%s WHERE id=%s AND user_id=%s"
                    cur.execute(query,
                                (num, status_label, json.dumps(res_data), datetime.now(), item_id, current_user.id))
                    g.db.commit()
                    cur.close()

                return jsonify({"success": True, "status": status_label, "full_data": res_data})

            # Si le serveur répond mais avec une erreur (ex: 403), on retente
            last_error = f"Erreur Serveur {response.status_code}"

        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
            # C'est ici qu'on attrape ton erreur 503
            last_error = "Proxy saturé (503). Nouvelle tentative..."
            time.sleep(1)  # Petit délai avant de changer de nœud
            continue

        except Exception as e:
            last_error = str(e)
            break  # Erreur critique, on arrête

    return jsonify(
        {"success": False, "message": f"Échec après {max_retries} tentatives. Dernière erreur : {last_error}"}), 500
# SALES

@app.route('/import-excel', methods=['GET', 'POST'])
@login_required
def import_excel_page():
    if request.method == 'POST':
        try:
            file = request.files.get('excel_file')
            if not file:
                return jsonify({"error": "Aucun fichier détecté"}), 400
            if not file.filename.endswith(('.xlsx', '.xls')):
                return jsonify({"error": "Format invalide (Utilisez .xlsx)"}), 400
            df = pd.read_excel(file)
            columns = [str(col) for col in df.columns.tolist()]
            temp_filename = f"temp_import_{current_user.id}.xlsx"
            upload_dir = os.path.join(app.root_path, 'static', 'uploads')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            temp_path = os.path.join(upload_dir, temp_filename)
            df.to_excel(temp_path, index=False)
            relative_path = f"static/uploads/{temp_filename}"
            return jsonify({"columns": columns, "temp_path": relative_path})

        except Exception as e:
            print(f"--- ERREUR SERVEUR UPLOAD ---")
            print(str(e))
            return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500
    return render_template('import_sales.html')

@app.route('/process-import', methods=['POST'])
@login_required
def process_import_logic():
    data = request.json
    mapping = data.get('mapping')
    temp_path = data.get('temp_path')

    def generate():
        if not temp_path or not os.path.exists(temp_path):
            yield f"data: {json.dumps({'msg': 'Fichier introuvable.', 'type': 'danger'})}\n\n"
            return

        df = pd.read_excel(temp_path)
        df = df.fillna('')
        total_rows = len(df)

        yield f"data: {json.dumps({'msg': 'Initialisation...', 'type': 'start', 'total': total_rows})}\n\n"
        conn = g.db
        success_count = 0
        # Blacklist pour ignorer les lignes de résumé
        blacklist_words = ['TOTAL', 'JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
                           'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE']
        for index, row in df.iterrows():
            try:
                item_name = str(row[mapping['item_name']]).strip()
                is_year = item_name.isdigit() and len(item_name) == 4
                contains_blacklist = any(word in item_name.upper() for word in blacklist_words)
                if not item_name or is_year or contains_blacklist:
                    yield f"data: {json.dumps({'type': 'skip', 'index': index + 1})}\n\n"
                    continue
                sku = str(row[mapping['sku']]).strip() if mapping.get('sku') and mapping['sku'] in row else 'N/A'
                size = str(row[mapping['size']]).strip() if mapping.get('size') and mapping['size'] in row else 'N/A'
                if mapping.get('sale_date') and mapping['sale_date'] in row and str(
                        row[mapping['sale_date']]).strip() != '':
                    try:
                        sale_date = pd.to_datetime(row[mapping['sale_date']]).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        sale_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    sale_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sale_price = clean_val(row[mapping['sale_price']])
                profit = clean_val(row[mapping['profit']])
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO sales (user_id, item_name, sku, size, quantity, sale_price, profit, sale_date, payment_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'reçu')
                    ''', (current_user.id, item_name, sku, size, 1, sale_price, profit, sale_date))
                conn.commit()
                success_count += 1
                yield f"data: {json.dumps({'msg': f'Importé: {item_name}', 'type': 'success', 'index': index + 1})}\n\n"
            except Exception as e:
                conn.rollback()
                yield f"data: {json.dumps({'msg': f'Erreur ligne {index + 1}', 'type': 'danger', 'index': index + 1})}\n\n"
        yield f"data: {json.dumps({'msg': f'{success_count} ventes importées.', 'type': 'finish'})}\n\n"
        if os.path.exists(temp_path): os.remove(temp_path)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/sales/share/<int:sale_id>')
@login_required
def share_sale(sale_id):
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('''
        SELECT item_name, image_url, sku, size, purchase_price_at_sale, sale_price, profit 
        FROM sales 
        WHERE id = %s AND user_id = %s
    ''', (sale_id, current_user.id))
    sale = cur.fetchone()
    cur.close()
    if not sale:
        return "Vente non trouvée", 404
    return render_template('share_recap.html', sale=sale)

@app.route('/sales/add', methods=['GET', 'POST'])
@login_required
def add_sale():
    conn = g.db
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'sales' not in data:
            return jsonify({"success": False, "message": "Aucune donnée reçue"}), 400
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        webhook_url = "https://discord.com/api/webhooks/1404523543512748035/teqgeczafL9-rViNAysRP-EPViALok9DGfH1v19Kvekvk2mbACbNzB9ltqv7ZxRV6gW5"
        last_sale_id = None
        try:
            for sale_data in data['sales']:
                product_id = sale_data.get('product_id')
                sale_price = Decimal(str(sale_data.get('sale_price', 0)))
                sale_date = sale_data.get('sale_date') or date.today()
                payment_status = sale_data.get('payment_status', 'reçu')
                platform = sale_data.get('platform', 'Autre')

                # 1. Récupération des infos produit
                cur.execute(
                    "SELECT name, purchase_price, quantity, sku, size, image_url FROM products WHERE id = %s AND user_id = %s",
                    (product_id, current_user.id))
                product = cur.fetchone()
                if not product:
                    continue
                profit = sale_price - product['purchase_price']

                # 2. Insertion en base de données avec RETURNING pour le bouton Partager
                cur.execute('''
                    INSERT INTO sales (user_id, product_id, item_name, quantity, sale_price, purchase_price_at_sale, profit, sale_date, payment_status, sku, size, image_url)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                current_user.id, product_id, product['name'], sale_price, product['purchase_price'], profit, sale_date,
                payment_status, product['sku'], product['size'], product['image_url']))
                last_sale_id = cur.fetchone()['id']

                # 3. Mise à jour du stock
                if product['quantity'] <= 1:
                    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
                else:
                    cur.execute("UPDATE products SET quantity = quantity - 1 WHERE id = %s", (product_id,))

                # 4. ENVOI DU WEBHOOK DISCORD
                discord_data = {
                    "embeds": [{
                        "title": "👟 Nouvelle Vente !",
                        "color": 3066993,
                        "fields": [
                            {"name": "Modèle", "value": f"**{product['name']}**", "inline": False},
                            {"name": "SKU", "value": f"`{product['sku']}`", "inline": True},
                            {"name": "Taille", "value": f"{product['size']}", "inline": True},
                            {"name": "Prix de Vente", "value": f"**{sale_price}€**", "inline": True},
                            {"name": "Plateforme", "value": f"{platform}", "inline": True}
                        ],
                        "thumbnail": {"url": product['image_url'] if product['image_url'] else ""}
                    }]
                }
                try:
                    requests.post(webhook_url, json=discord_data)
                except Exception as e:
                    print(f"Erreur Webhook Discord: {e}")
            conn.commit()
            return jsonify({
                "success": True,
                "redirect": url_for('dashboard'),
                "sale_id": last_sale_id
            })
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            cur.close()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM products WHERE user_id = %s AND quantity > 0", (current_user.id,))
    products = cur.fetchall()
    cur.close()
    return render_template('add_sale.html', products=products, today=date.today())

@app.route('/sale_success/<int:sale_id>')
@login_required
def sale_success(sale_id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # ÉTAPE 1 : On récupère TOUT de la vente
        cur.execute("SELECT * FROM sales WHERE id = %s AND user_id = %s", (sale_id, current_user.id))
        sale_row = cur.fetchone()
        if not sale_row:
            print("--- DEBUG : Vente introuvable dans la table sales ---")
            return redirect(url_for('dashboard'))

        # ÉTAPE 2 : On cherche l'image spécifiquement (Priorité Produits, puis SKU)
        # On ne fait pas de JOIN pour éviter l'erreur de tuple
        image_url = None
        product_id = sale_row.get('product_id')
        item_name = sale_row.get('item_name')
        if product_id:
            cur.execute("SELECT image_url FROM products WHERE id = %s", (product_id,))
            p_row = cur.fetchone()
            if p_row:
                image_url = p_row.get('image_url')
        if not image_url and item_name:
            cur.execute("SELECT image_url FROM sku_database WHERE product_name ILIKE %s LIMIT 1", (f"%{item_name}%",))
            sd_row = cur.fetchone()
            if sd_row:
                image_url = sd_row.get('image_url')

        # ÉTAPE 3 : Préparation propre pour le HTML
        sale_display = {
            'item_name': item_name or "Produit inconnu",
            'sale_price_formatted': f"{float(sale_row.get('sale_price') or 0):.2f}€",
            'purchase_price_formatted': f"{float(sale_row.get('purchase_price_at_sale') or 0):.2f}€",
            'profit': float(sale_row.get('profit') or 0),
            'profit_formatted': f"{float(sale_row.get('profit') or 0):+.2f}€"
        }
        final_image = image_url if image_url else url_for('static', filename='placeholder_product.png')
        print(f"--- DEBUG SUCCESS : Image trouvée -> {final_image} ---")
        return render_template('sale_success.html',
                               sale=sale_display,
                               product_image_url=final_image,
                               success_checkmark_url=url_for('static', filename='success_checkmark.png'))

    except Exception as e:
        import traceback
        print("--- ERREUR CRITIQUE ---")
        print(traceback.format_exc())  # Ça va te dire la LIGNE exacte du crash
        return f"Erreur interne : {e}"
    finally:
        if cur: cur.close()


@app.route('/sales')
@login_required
def sales():
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''
            SELECT
                id, item_name, quantity, sale_price, purchase_price_at_sale,
                sale_date, notes, sale_channel, shipping_cost, fees, profit,
                COALESCE(payment_status, 'reçu') as payment_status,
                sku, size, tracking_number, shipping_status
            FROM sales
            WHERE user_id = %s
            ORDER BY sale_date DESC
        ''', (current_user.id,))
        sales_data_raw = cur.fetchall()

        # --- LOGIQUE DE CALCUL DES INDICATEURS ---
        total_transit_value = 0.0

        sales_for_template = []
        for sale in sales_data_raw:
            sale_dict = dict(sale)
            price = float(sale['sale_price'] or 0.0)

            # Détermination du statut pour le calcul
            status = (sale['shipping_status'] or "").upper()
            if sale['tracking_number'] and status != 'DELIVERED' and "LIVRÉ" not in status:
                total_transit_value += price

            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'
            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(price)
            sale_dict['profit_formatted'] = '{:.2f} €'.format(float(sale_dict['profit'] or 0.0))
            sales_for_template.append(sale_dict)

        # On ajoute item_type='sale' pour le fonctionnement du tracking universel
        return render_template('sales.html',
                               sales=sales_for_template,
                               total_transit_value=total_transit_value,
                               item_type='sale')
    except Exception as e:
        flash(f"Erreur lors du chargement des ventes: {e}", 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cur and not cur.closed:
            cur.close()


@app.route('/sales/<int:sale_id>/update_status', methods=['POST'])
@login_required
def update_sale_status(sale_id):
    conn = g.db
    cur = None
    try:
        data = request.get_json()
        new_status = data.get('status')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. On récupère d'abord les infos de la vente (prix et ancien statut)
        cur.execute('''
            SELECT sale_price, payment_status 
            FROM sales 
            WHERE id = %s AND user_id = %s
        ''', (sale_id, current_user.id))
        sale = cur.fetchone()

        if not sale:
            return jsonify({"success": False, "message": "Vente non trouvée"}), 404

        # 2. Mise à jour du statut de la vente
        cur.execute('''
            UPDATE sales 
            SET payment_status = %s 
            WHERE id = %s AND user_id = %s
        ''', (new_status, sale_id, current_user.id))

        # 3. Automatisation du Cashflow
        # Si le nouveau statut est "reçu" et que l'ancien ne l'était pas, on ajoute au cash_flow
        if new_status == 'reçu' and sale['payment_status'] != 'reçu':
            amount_to_add = float(sale['sale_price'] or 0)
            cur.execute('''
                UPDATE users 
                SET cash_flow = cash_flow + %s 
                WHERE id = %s
            ''', (amount_to_add, current_user.id))

        conn.commit()
        return jsonify({"success": True, "status": new_status}), 200

    except Exception as e:
        if conn: conn.rollback()
        print(f"Erreur update_status: {e}")
        return jsonify({"success": False}), 500
    finally:
        if cur: cur.close()
@app.route('/sales/<int:id>/edit', methods=('GET', 'POST'))
@login_required
def edit_sale(id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM sales WHERE id = %s AND user_id = %s',
                    (id, current_user.id))
        sale = cur.fetchone()
        cur.close()
        if sale is None:
            abort(404)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT id, name, sku FROM products WHERE user_id = %s ORDER BY name',
                    (current_user.id,))
        products_for_dropdown = cur.fetchall()
        cur.close()
        if request.method == 'POST':
            product_id = request.form.get('product_id')
            item_name = request.form['item_name']
            quantity = request.form['quantity']
            sale_price = request.form['sale_price']
            sale_date = request.form['sale_date']
            notes = request.form.get('notes')
            if not item_name or not quantity or not sale_price or not sale_date:
                flash('Veuillez remplir tous les champs obligatoires.', 'danger')
                return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
            try:
                quantity = int(quantity)
                sale_price = float(sale_price)
                if quantity <= 0:
                    flash('La quantité doit être un nombre positif.', 'danger')
                    return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
                datetime.strptime(sale_date, '%Y-%m-%d')
            except ValueError:
                flash('La quantité, le prix de vente et la date doivent être des valeurs valides.', 'danger')
                return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
            if sale['product_id']:
                cur = conn.cursor()
                cur.execute('UPDATE products SET quantity = quantity + %s WHERE id = %s',
                            (sale['quantity'], sale['product_id']))
                cur.close()
            if product_id:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute('SELECT quantity FROM products WHERE id = %s AND user_id = %s',
                            (product_id, current_user.id))
                current_product = cur.fetchone()
                cur.close()
                if current_product:
                    new_stock = current_product['quantity'] - quantity
                    if new_stock < 0:
                        flash(
                            f"Quantité insuffisante en stock pour '{item_name}'. Stock actuel : {current_product['quantity']}",
                            "danger")
                        conn.rollback()
                        return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
                    cur = conn.cursor()
                    cur.execute('UPDATE products SET quantity = %s WHERE id = %s', (new_stock, product_id))
                    cur.close()
            cur = conn.cursor()
            cur.execute(
                "UPDATE sales SET product_id = %s, item_name = %s, quantity = %s, sale_price = %s, sale_date = %s, notes = %s WHERE id = %s AND user_id = %s",
                (product_id, item_name, quantity, sale_price, sale_date, notes, id, current_user.id))
            cur.close()
            conn.commit()
            flash('Vente mise à jour avec succès !', 'success')
            return redirect(url_for('sales'))
    except Exception as e:
        conn.rollback()
        flash(f"Une erreur est survenue lors de la mise à jour de la vente : {e}", 'danger')
        print(f"Erreur édition vente: {e}")
        return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
    finally:
        if cur and not cur.closed:
            cur.close()
    return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)

@app.route('/sales/<int:id>/delete', methods=('POST',))
@login_required
def delete_sale(id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            'SELECT user_id, product_id, quantity, sale_price, profit FROM sales WHERE id = %s AND user_id = %s',
            (id, current_user.id)
        )
        sale_details = cur.fetchone()
        cur.close()
        if sale_details is None:
            abort(404)

        sale_user_id = sale_details['user_id']
        sale_product_id = sale_details['product_id']
        sale_quantity = sale_details['quantity']
        sale_price_to_deduct = sale_details['sale_price']
        profit_to_deduct = sale_details['profit']
        if sale_product_id:
            cur = conn.cursor()
            cur.execute('UPDATE products SET quantity = quantity + %s WHERE id = %s', (sale_quantity, sale_product_id))
            cur.close()
        cur = conn.cursor()
        cur.execute('DELETE FROM sales WHERE id = %s AND user_id = %s', (id, current_user.id))
        cur.close()

        # 2. Mettre à jour (décrémenter) les totaux dans la table classement_utilisateurs
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE classement_utilisateurs
            SET
                total_ca = total_ca - %s,
                total_benefice = total_benefice - %s,
                last_updated = NOW()
            WHERE user_id = %s;
            """,
            (sale_price_to_deduct, profit_to_deduct, sale_user_id)
        )
        cur.close()
        conn.commit()
        flash('Vente supprimée avec succès et classement mis à jour !', 'success')
        return redirect(url_for('sales'))
    except Exception as e:
        conn.rollback()
        flash(f"Une erreur est survenue lors de la suppression de la vente : {e}", 'danger')
        print(f"Erreur suppression vente: {e}")
        return redirect(url_for('sales'))
    finally:
        pass


# STATISTICS

@app.route('/statistics', methods=['GET', 'POST'])  # Ajout de POST
@login_required
def statistics():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # --- MISE À JOUR DU CASH (Persistance) ---
    if request.method == 'POST' and 'update_cash' in request.form:
        new_cash = request.form.get('cash_flow', 0)
        cur.execute("UPDATE users SET cash_flow = %s WHERE id = %s", (new_cash, current_user.id))
        conn.commit()
        # On reste sur la page avec les mêmes paramètres de filtrage

    # --- RÉCUPÉRATION DU CASH ENREGISTRÉ ---
    cur.execute("SELECT cash_flow FROM users WHERE id = %s", (current_user.id,))
    u_data = cur.fetchone()
    current_cash = float(u_data['cash_flow'] or 0)

    # --- LOGIQUE EXISTANTE (PÉRIODES) ---
    period = request.args.get('period', 'month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    now_dt = dt.datetime.now()
    today_date = now_dt.date()
    filter_start = dt.datetime.combine(today_date, dt.time.min)
    filter_end = dt.datetime.combine(today_date, dt.time.max)

    if period == 'day':
        pass
    elif period == 'week':
        monday = today_date - dt.timedelta(days=today_date.weekday())
        filter_start = dt.datetime.combine(monday, dt.time.min)
        filter_end = dt.datetime.combine(monday + dt.timedelta(days=6), dt.time.max)
    elif period == 'month':
        first_day = today_date.replace(day=1)
        filter_start = dt.datetime.combine(first_day, dt.time.min)
        if today_date.month == 12:
            last_day = dt.date(today_date.year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            last_day = dt.date(today_date.year, today_date.month + 1, 1) - dt.timedelta(days=1)
        filter_end = dt.datetime.combine(last_day, dt.time.max)
    elif period == 'year':
        filter_start = dt.datetime(today_date.year, 1, 1, 0, 0, 0)
        filter_end = dt.datetime(today_date.year, 12, 31, 23, 59, 59)
    elif period == 'custom' and start_str and end_str:
        try:
            filter_start = dt.datetime.strptime(start_str, '%Y-%m-%d')
            filter_end = dt.datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except:
            period = 'month'

    # 1. RÉCUPÉRATION DES VENTES
    cur.execute("SELECT * FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s ORDER BY sale_date ASC",
                (current_user.id, filter_start, filter_end))
    sales = cur.fetchall()

    total_revenue = sum(float(s['sale_price'] or 0) for s in sales)
    total_sales_profit = sum(float(s['profit'] or 0) for s in sales)
    total_purchase_cost = sum(float(s['purchase_price_at_sale'] or 0) for s in sales)
    volume = len(sales)

    # 1.1 OPÉRATIONS SUPPLÉMENTAIRES
    cur.execute("""
        SELECT SUM(amount) as total FROM supplementary_operations 
        WHERE user_id = %s AND operation_date >= %s AND operation_date <= %s
    """, (current_user.id, filter_start.date(), filter_end.date()))
    total_ops_profit = float(cur.fetchone()['total'] or 0)
    total_profit = total_sales_profit + total_ops_profit

    roi_avg = (total_sales_profit / total_purchase_cost * 100) if total_purchase_cost > 0 else 0
    health_score = round((min(6, roi_avg / 5) if roi_avg > 0 else 0) + min(4, volume / 2), 1)

    # 2. PAIEMENTS EN ATTENTE
    cur.execute(
        "SELECT COALESCE(SUM(sale_price), 0) as total FROM sales WHERE user_id = %s AND payment_status = 'en_attente'",
        (current_user.id,))
    pending_payments = float(cur.fetchone()['total'] or 0)

    # 3. STOCK
    cur.execute(
        "SELECT SUM(purchase_price) as total_val, SUM(quantity) as total_qty FROM products WHERE user_id = %s AND quantity = 1",
        (current_user.id,))
    stock_info = cur.fetchone()
    valeur_achat_stock = float(stock_info['total_val'] or 0)
    stock_qty = stock_info['total_qty'] or 0

    # 4. TRÉSORERIE ENTIÈRE (Utilise le cash de la DB)
    total_base_cash = current_cash + valeur_achat_stock + pending_payments

    # 5. PROJECTIONS ET FLUX
    cur.execute("SELECT MIN(sale_date) as first_sale, SUM(sale_price) as total_ca_all FROM sales WHERE user_id = %s",
                (current_user.id,))
    all_stats = cur.fetchone()
    first_date = (all_stats['first_sale'].date() if isinstance(all_stats['first_sale'], dt.datetime) else all_stats[
        'first_sale']) if all_stats['first_sale'] else today_date
    weeks_active = max(1, (today_date - first_date).days / 7)
    avg_ca_weekly = float(all_stats['total_ca_all'] or 0) / weeks_active
    net_flow_weekly = avg_ca_weekly * 0.25

    proj_1w = total_base_cash + net_flow_weekly
    proj_1m = total_base_cash + (net_flow_weekly * 4.3)
    proj_1y = total_base_cash + (net_flow_weekly * 52)

    # 6. OBJECTIFS
    delta_year = dt.timedelta(days=365)
    start_n1 = filter_start - delta_year
    end_n1 = filter_end - delta_year
    cur.execute(
        "SELECT SUM(sale_price) as rev, SUM(profit) as prof FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s",
        (current_user.id, start_n1, end_n1))
    ref_data = cur.fetchone()
    if not ref_data or not ref_data['rev']:
        delta_period = filter_end - filter_start
        start_prev = filter_start - delta_period
        cur.execute(
            "SELECT SUM(sale_price) as rev, SUM(profit) as prof FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s",
            (current_user.id, start_prev, filter_start))
        ref_data = cur.fetchone()
    ref_rev = float(ref_data['rev'] or 0)
    ref_prof = float(ref_data['prof'] or 0)
    has_ref = ref_rev > 0

    # 7. STOCK MANAGEMENT
    cur.execute(
        "SELECT AVG((profit / NULLIF(purchase_price_at_sale, 0)) * 100) as avg_roi_all FROM sales WHERE user_id = %s",
        (current_user.id,))
    avg_roi_all_time = float(cur.fetchone()['avg_roi_all'] or 20.0)
    profit_latent = valeur_achat_stock * (avg_roi_all_time / 100)
    ca_latent = valeur_achat_stock + profit_latent
    cur.execute("SELECT date_added FROM products WHERE user_id = %s AND quantity = 1", (current_user.id,))
    stock_items = cur.fetchall()
    ages = [
        (today_date - (i['date_added'].date() if isinstance(i['date_added'], dt.datetime) else i['date_added'])).days
        for i in stock_items if i['date_added']]
    stock_avg_age = int(sum(ages) / len(ages)) if ages else 0

    # 9. FOCUS ACTIFS
    cur.execute(
        "SELECT name, sku, size, purchase_price, image_url, date_added FROM products WHERE user_id = %s AND quantity = 1 ORDER BY date_added ASC LIMIT 1",
        (current_user.id,))
    old_res = cur.fetchone()
    oldest_pair = None
    if old_res:
        d_added = old_res['date_added'].date() if isinstance(old_res['date_added'], dt.datetime) else old_res[
            'date_added']
        oldest_pair = {'name': old_res['name'], 'sku': old_res['sku'], 'size': old_res['size'],
                       'purchase_price': float(old_res['purchase_price'] or 0), 'image_url': old_res['image_url'],
                       'age': (today_date - d_added).days}
    cur.execute(
        "SELECT name, sku, size, purchase_price, image_url, date_added FROM products WHERE user_id = %s AND quantity = 1 ORDER BY purchase_price DESC LIMIT 2",
        (current_user.id,))
    expensive_res = cur.fetchall()
    expensive_pairs = [
        {'name': p['name'], 'sku': p['sku'], 'size': p['size'], 'purchase_price': float(p['purchase_price'] or 0),
         'image_url': p['image_url'],
         'age': (p['date_added'].date() if isinstance(p['date_added'], dt.datetime) else p['date_added'])} for p in
        expensive_res]

    # 10. ANALYTIQUE
    days_dist = {i: {'count': 0, 'profit': 0} for i in range(7)}
    sizes_dist = {}
    platforms_dist = {}
    for s in sales:
        d_idx = s['sale_date'].weekday()
        days_dist[d_idx]['count'] += 1
        days_dist[d_idx]['profit'] += float(s['profit'] or 0)
        sz = str(s['size'] or "N/A")
        if sz not in sizes_dist: sizes_dist[sz] = {'count': 0, 'profit': 0}
        sizes_dist[sz]['count'] += 1
        sizes_dist[sz]['profit'] += float(s['profit'] or 0)
        ch = s['sale_channel'] or "Inconnu"
        if ch not in platforms_dist: platforms_dist[ch] = {'count': 0, 'profit': 0}
        platforms_dist[ch]['count'] += 1
        platforms_dist[ch]['profit'] += float(s['profit'] or 0)

    return render_template('statistics.html',
                           sales=sales, revenue=total_revenue, profit=total_profit,
                           total_sales_profit=total_sales_profit, total_ops_profit=total_ops_profit,
                           volume=volume, roi_avg=roi_avg, health_score=health_score,
                           stock_value=valeur_achat_stock, stock_qty=stock_qty,
                           period=period, start_date=start_str, end_date=end_str,
                           valeur_achat_stock=valeur_achat_stock, profit_latent=profit_latent,
                           ca_latent=ca_latent, stock_avg_age=stock_avg_age,
                           current_cash=current_cash, pending_payments=pending_payments,
                           total_base_cash=total_base_cash,
                           proj_1w=proj_1w, proj_1m=proj_1m, proj_1y=proj_1y,
                           ref_rev=ref_rev, ref_prof=ref_prof, has_ref=has_ref,
                           oldest_pair=oldest_pair, expensive_pairs=expensive_pairs,
                           days_dist=days_dist, sizes_dist=sizes_dist, platforms_dist=platforms_dist)
@app.route('/api/overlay_stats')
@login_required
def api_overlay_stats():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    user_id = current_user.id
    now = dt.datetime.now()
    today = now.date()
    monday = today - dt.timedelta(days=today.weekday())

    # --- 1. VOLUMES ET PROFIT (Formule identique à ta route /statistics) ---
    cur.execute("""
        SELECT 
            SUM(sale_price) as total_revenue,
            SUM(profit) as total_profit,
            SUM(purchase_price_at_sale) as total_cost,
            COUNT(*) as volume
        FROM sales WHERE user_id = %s
    """, (user_id,))
    main_stats = cur.fetchone()

    t_profit = float(main_stats['total_profit'] or 0)
    t_cost = float(main_stats['total_cost'] or 0)
    roi_avg = round((t_profit / t_cost * 100), 1) if t_cost > 0 else 0

    # --- 2. RECORDS (Utilisation de item_name) ---
    cur.execute("SELECT profit, item_name FROM sales WHERE user_id = %s ORDER BY profit DESC LIMIT 1", (user_id,))
    rec = cur.fetchone()
    record_val = float(rec['profit'] or 0) if rec else 0
    record_name = rec['item_name'] if rec else "N/A"

    # --- 3. VOLUMES TEMPORELS ---
    cur.execute("SELECT SUM(sale_price) as v FROM sales WHERE user_id = %s AND sale_date::date = %s", (user_id, today))
    s_today = float(cur.fetchone()['v'] or 0)

    cur.execute("SELECT SUM(sale_price) as v FROM sales WHERE user_id = %s AND sale_date >= %s",
                (user_id, dt.datetime.combine(monday, dt.time.min)))
    s_week = float(cur.fetchone()['v'] or 0)

    cur.execute(
        "SELECT SUM(sale_price) as v FROM sales WHERE user_id = %s AND EXTRACT(MONTH FROM sale_date) = %s AND EXTRACT(YEAR FROM sale_date) = %s",
        (user_id, today.month, today.year))
    s_month = float(cur.fetchone()['v'] or 0)

    cur.execute("SELECT SUM(sale_price) as v FROM sales WHERE user_id = %s AND EXTRACT(YEAR FROM sale_date) = %s",
                (user_id, today.year))
    s_year = float(cur.fetchone()['v'] or 0)

    # --- 4. TOP/FLOP HEBDO ---
    cur.execute("SELECT MAX(profit) as b, MIN(profit) as w FROM sales WHERE user_id = %s AND sale_date >= %s",
                (user_id, dt.datetime.combine(monday, dt.time.min)))
    hebdo = cur.fetchone()
    b_week = float(hebdo['b'] or 0)
    w_week = float(hebdo['w'] or 0)

    # --- 5. STOCK ET TRÉSO ---
    cur.execute("SELECT SUM(purchase_price) as v FROM products WHERE user_id = %s AND quantity = 1", (user_id,))
    s_val = float(cur.fetchone()['v'] or 0)

    cur.execute("SELECT SUM(sale_price) as v FROM sales WHERE user_id = %s AND payment_status = 'en_attente'",
                (user_id,))
    pending = float(cur.fetchone()['v'] or 0)

    # --- 6. PROGRESSION OBJECTIF ---
    last_monday = monday - dt.timedelta(days=7)
    cur.execute("SELECT SUM(profit) as p FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date < %s",
                (user_id, last_monday, monday))
    prev_p = float(cur.fetchone()['p'] or 0)
    cur.execute("SELECT SUM(profit) as p FROM sales WHERE user_id = %s AND sale_date >= %s", (user_id, monday))
    curr_p = float(cur.fetchone()['p'] or 0)
    progression = min(100, round((curr_p / prev_p * 100))) if prev_p > 0 else (100 if curr_p > 0 else 0)

    return jsonify({
        "total_profit": t_profit,
        "roi_avg": roi_avg,
        "record_value": record_val,
        "record_pair": record_name,
        "avg_margin": round(t_profit / main_stats['volume'], 2) if main_stats['volume'] and main_stats[
            'volume'] > 0 else 0,
        "sales_today": s_today,
        "sales_week": s_week,
        "sales_month": s_month,
        "sales_year": s_year,
        "best_sale_week": b_week,
        "worst_sale_week": w_week,
        "stock_value": s_val,
        "weekly_progress": progression,
        "total_base_cash": s_val + pending
    })

# OTHER

@app.route('/livraisons')
@login_required
def livraisons():
    conn = g.db
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. STOCK EN TRANSIT (Non livré)
        cur.execute('''
            SELECT id, name, purchase_price as price, image_url, tracking_number, 
                   shipping_status, tracking_data 
            FROM products 
            WHERE user_id = %s AND tracking_number IS NOT NULL 
            AND (shipping_status IS NULL OR (UPPER(shipping_status) NOT LIKE '%%LIVRÉ%%' AND UPPER(shipping_status) != 'DELIVERED'))
        ''', (current_user.id,))
        incoming_transit = cur.fetchall()

        # 2. VENTES EN TRANSIT (Non livrées)
        cur.execute('''
            SELECT id, item_name as name, sale_price as price, tracking_number, 
                   shipping_status, tracking_data 
            FROM sales 
            WHERE user_id = %s AND tracking_number IS NOT NULL 
            AND (shipping_status IS NULL OR (UPPER(shipping_status) NOT LIKE '%%LIVRÉ%%' AND UPPER(shipping_status) != 'DELIVERED'))
        ''', (current_user.id,))
        outgoing_transit = cur.fetchall()

        # 3. TOUS LES COLIS LIVRÉS (Catégorie à part)
        cur.execute('''
            SELECT id, name, purchase_price as price, image_url, tracking_number, shipping_status, tracking_data, 'product' as type
            FROM products 
            WHERE user_id = %s AND (UPPER(shipping_status) LIKE '%%LIVRÉ%%' OR UPPER(shipping_status) = 'DELIVERED')
            UNION ALL
            SELECT id, item_name as name, sale_price as price, NULL as image_url, tracking_number, shipping_status, tracking_data, 'sale' as type
            FROM sales 
            WHERE user_id = %s AND (UPPER(shipping_status) LIKE '%%LIVRÉ%%' OR UPPER(shipping_status) = 'DELIVERED')
        ''', (current_user.id, current_user.id))
        delivered_items = cur.fetchall()

        # Calcul des totaux UNIQUEMENT sur le transit
        total_incoming = sum(float(i['price'] or 0) for i in incoming_transit)
        total_outgoing = sum(float(i['price'] or 0) for i in outgoing_transit)

        return render_template('livraisons.html',
                               incoming=incoming_transit,
                               outgoing=outgoing_transit,
                               delivered=delivered_items,
                               total_incoming=total_incoming,
                               total_outgoing=total_outgoing)
    finally:
        if cur and not cur.closed: cur.close()
# ADMIN

@app.route('/login-discord')
def login_discord():
    # On demande l'accès à l'identité et à la liste des membres des serveurs
    scope = "identify guilds.members.read"
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope={scope}"
    )
    return redirect(discord_auth_url)


@app.route('/callback')
def callback():
    print("\n--- [DEBUG] ENTRÉE DANS CALLBACK ---")
    code = request.args.get('code')
    if not code:
        print("!!! ERREUR : Pas de code reçu de Discord")
        return "Erreur : Aucun code reçu.", 400

    # Échange du token
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }

    token_response = requests.post("https://discord.com/api/v10/oauth2/token", data=data)
    print(f"Statut Token Discord : {token_response.status_code}")

    token_json = token_response.json()
    access_token = token_json.get('access_token')

    if not access_token:
        print(f"!!! ERREUR TOKEN : {token_json}")
        return "Erreur Token", 400

    # Récupération du membre
    member_headers = {'Authorization': f'Bearer {access_token}'}
    member_url = f"https://discord.com/api/v10/users/@me/guilds/{GUILD_ID}/member"
    member_response = requests.get(member_url, headers=member_headers)

    print(f"Statut Membre Discord : {member_response.status_code}")
    member_data = member_response.json()

    if member_response.status_code != 200:
        print(f"!!! ERREUR MEMBRE : {member_data}")
        flash("Non présent sur le serveur.", "danger")
        return redirect(url_for('login'))

    user_roles = member_data.get('roles', [])
    username = member_data.get('user', {}).get('username')

    print(f"Utilisateur identifié : {username}")
    print(f"Rôles de l'utilisateur (reçus) : {user_roles}")
    print(f"Rôle requis (attendu) : {REQUIRED_ROLE_ID}")

    # Comparaison STRICTE
    has_role = str(REQUIRED_ROLE_ID) in [str(r) for r in user_roles]
    print(f"Résultat de la vérification du rôle : {has_role}")

    if has_role:
        session.clear()  # On repart sur une session propre
        session['discord_auth'] = True
        session['discord_user'] = username
        session['discord_user_id'] = member_data.get('user', {}).get('id')
        session['last_discord_check'] = time.time()
        session.permanent = True
        session.modified = True

        print("✅ Session Discord validée et enregistrée !")
        print(f"Contenu de la session juste avant redirect : {dict(session)}")

        flash(f"Bienvenue {username} !", "success")
        return redirect(url_for('dashboard'))
    else:
        print("❌ Accès refusé : Rôle non trouvé dans la liste.")
        flash("Rôle manquant.", "danger")
        return redirect(url_for('login'))
@app.route('/logout-discord')
def logout_discord():
    session.pop('discord_auth', None)
    session.pop('discord_user', None)
    return redirect(url_for('login'))

@app.route('/admin/broadcast', methods=['GET', 'POST'])
@login_required
def broadcast_email():
    if current_user.email != 'bidardgab@gmail.com':
        return redirect(url_for('statistics'))
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == 'POST':
        subject = request.form.get('subject')
        content = request.form.get('content')
        selected_recipients = request.form.getlist('selected_emails')
        attachments = request.files.getlist('attachments')
        campaign_id = str(uuid.uuid4())[:8]
        base_url = request.host_url.rstrip('/')
        with mail.connect() as conn_mail:
            for email_addr in selected_recipients:
                tracking_token = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO email_analytics (token, recipient_email, subject, campaign_id) VALUES (%s, %s, %s, %s)",
                    (tracking_token, email_addr, subject, campaign_id)
                )
                conn.commit()
                html_body = render_template('email_layout.html',
                                            content=content,
                                            tracking_token=tracking_token,
                                            base_url=base_url)
                msg = Message(recipients=[email_addr], subject=subject, html=html_body)
                for file in attachments:
                    if file and file.filename:
                        msg.attach(file.filename, file.content_type, file.read())
                        file.seek(0)
                conn_mail.send(msg)
        flash(f"Diffusion (ID: {campaign_id}) envoyée avec succès.", "success")
        return redirect(url_for('broadcast_email'))
    cur.execute("SELECT email, username FROM users ORDER BY username ASC")
    return render_template('send_email.html', users=cur.fetchall(), base_url=request.host_url.rstrip('/'))

@app.route('/track/click')
def track_click():
    token = request.args.get('t')
    target_url = request.args.get('url')
    if token:
        conn = g.db
        cur = conn.cursor()
        cur.execute("UPDATE email_analytics SET clicks = clicks + 1 WHERE token = %s", (token,))
        conn.commit()
    return redirect(target_url or url_for('statistics'))

@app.route('/secret-monitor-v5')
@login_required
def admin_monitor():
    if current_user.email != 'bidardgab@gmail.com':
        abort(403)
    cur = g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT id, email, username, key_status FROM users")
        rows = cur.fetchall()
        users_list = []
        for r in rows:
            cur.execute("SELECT MAX(sale_date) as last_v FROM sales WHERE user_id = %s", (r['id'],))
            v = cur.fetchone()['last_v']
            cur.execute("SELECT MAX(date_added) as last_p FROM products WHERE user_id = %s", (r['id'],))
            p = cur.fetchone()['last_p']
            last_act = max(filter(None, [v, p]), default="Aucune")
            cur.execute("SELECT total_ca, total_benefice FROM classement_utilisateurs WHERE user_id = %s", (r['id'],))
            s = cur.fetchone()
            users_list.append({
                'id': r['id'],
                'email': r['email'],
                'username': r['username'] or r['email'],
                'key_status': r['key_status'],
                'ca': float(s['total_ca'] or 0) if s else 0,
                'profit': float(s['total_benefice'] or 0) if s else 0,
                'last_active': last_act
            })
        return render_template('admin_monitor.html', users=users_list)
    except Exception as e:
        return f"Erreur : {str(e)}", 500

@app.route('/admin/send-ping/<int:user_id>')
@login_required
def admin_send_ping(user_id):
    if current_user.email != 'bidardgab@gmail.com':
        abort(403)
    cur = g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Récupération des données utilisateur
    cur.execute("SELECT email, username FROM users WHERE id = %s", (user_id,))
    target = cur.fetchone()

    # Récupération de la dernière vente pour le texte du mail
    cur.execute("SELECT MAX(sale_date) as last_v FROM sales WHERE user_id = %s", (user_id,))
    v_date = cur.fetchone()['last_v']
    date_str = v_date.strftime('%d %B %Y') if v_date else "quelques temps"

    if target:
        subject = "🔐 Conserver votre accès - Resell Notion Stats"

        # 2. Le template HTML (le même que précédemment, simplifié ici pour la lisibilité)
        html_content = f"""
        <div style="background-color: #0f172a; color: #f1f5f9; font-family: sans-serif; padding: 40px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 16px; padding: 40px; border: 1px solid #334155;">
                <h1 style="color: #4f46e5; text-align: center;">RESELL NOTION <span style="color: #ffffff;">STATS</span></h1>
                <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
                <h2 style="color: #ffffff;">Bonjour {target['username']},</h2>
                <p style="color: #94a3b8; font-size: 16px;">
                    Votre dernière activité remonte au <strong style="color: #f59e0b;">{date_str}</strong>.
                </p>
                <p style="color: #94a3b8;">
                    Nous effectuons un nettoyage des comptes inactifs. Souhaitez-vous conserver vos données ? 
                    Répondez simplement <b>"OUI"</b> à ce mail.
                </p>
                <div style="text-align: center; margin-top: 30px; font-size: 12px; color: #64748b;">
                    &copy; 2026 Resell Notion Stats
                </div>
            </div>
        </div>
        """

        # 3. ENVOI RÉEL
        success = send_gmail_stats(target['email'], subject, html_content)

        if success:
            flash(f"✅ Email envoyé avec succès à {target['email']}", "success")
        else:
            flash(f"❌ Échec de l'envoi à {target['email']}", "danger")

    return redirect(url_for('admin_monitor'))

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(app.root_path, 'manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def serve_service_worker():
    return send_from_directory(app.root_path, 'service-worker.js', mimetype='application/javascript')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/offline.html')
def offline_page():
    return render_template('offline.html')


@app.before_request
def global_security_check():
    # A. On initialise la DB d'abord pour éviter l'AttributeError: db
    if not hasattr(g, 'db'):
        from database import get_db_connection  # ou ta fonction de connexion
        g.db = get_db_connection()

    # B. Liste blanche : pages accessibles sans vérification Discord
    allowed_endpoints = ['login', 'login_discord', 'callback', 'static', 'logout']
    if request.endpoint in allowed_endpoints or not request.endpoint:
        return

    # C. Vérification de l'identité Flask-Login
    if current_user.is_authenticated:

        # 1. Est-ce qu'il est déjà passé par l'auth Discord ?
        if not session.get('discord_auth'):
            return redirect(url_for('login_discord'))

        # 2. LE VIGILE : Vérification dynamique (toutes les 5 minutes)
        last_check = session.get('last_discord_check', 0)
        if time.time() - last_check > 300:  # 300 secondes = 5 mins
            discord_id = session.get('discord_user_id')

            # On interroge Discord via le Bot (invisible pour l'utilisateur)
            url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_id}"
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}

            try:
                r = requests.get(url, headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    # Si le rôle n'est plus là -> DECONNEXION
                    if str(REQUIRED_ROLE_ID) not in data.get('roles', []):
                        session.clear()
                        flash("Accès révoqué : rôle Discord retiré.", "danger")
                        return redirect(url_for('login'))
                    else:
                        session['last_discord_check'] = time.time()  # On valide pour 5 mins
                else:
                    # Si l'utilisateur a quitté le serveur
                    session.clear()
                    return redirect(url_for('login'))
            except Exception as e:
                print(f"Erreur check vigile: {e}")
                # En cas d'erreur API, on laisse passer pour ne pas bloquer le site
                pass

@app.before_request
def debug_security_check():
    # On ignore le check pour les pages de login/callback et le statique
    allowed = ['login', 'login_discord', 'callback', 'static']
    if request.endpoint in allowed or not request.endpoint:
        return

    # Si on arrive ici, on est sur une page protégée (ex: dashboard)
    print(f"\n--- [DEBUG] CHECK SÉCURITÉ sur : {request.endpoint} ---")
    print(f"Utilisateur Flask identifié : {current_user.is_authenticated}")
    print(f"Session Discord Auth : {session.get('discord_auth')}")

    if current_user.is_authenticated:
        if not session.get('discord_auth'):
            print("⚠️ Pas de session Discord -> REDIRECTION VERS AUTH")
            return redirect(url_for('login_discord'))
        else:
            print("🟢 Accès autorisé (Session OK)")
@app.route('/logout-debug')
def logout_debug():
    session.clear() # Efface TOUTE la session
    return "Session vidée. Refais le test maintenant."

def init_db():
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE
            );
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                sku VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                size VARCHAR(50) NOT NULL,
                purchase_price REAL NOT NULL,
                selling_price REAL,
                date_added DATE NOT NULL,
                date_sold DATE,
                image_url VARCHAR(500)
            );
            CREATE TABLE IF NOT EXISTS marketplace_listings (
                id SERIAL PRIMARY KEY,
                seller_id INTEGER NOT NULL REFERENCES users (id),
                sku VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                sizes VARCHAR(200),
                description TEXT NOT NULL,
                price REAL NOT NULL,
                image_urls TEXT,
                date_posted TIMESTAMP NOT NULL DEFAULT NOW()
            
            
            );
           
            
            CREATE TABLE IF NOT EXISTS marketplace_requests (
                id SERIAL PRIMARY KEY,
                listing_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                client_name TEXT NOT NULL,
                client_email TEXT NOT NULL,
                client_phone TEXT,
                offer_price DECIMAL,
                client_message TEXT,
                request_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'en_attente',
                FOREIGN KEY (listing_id) REFERENCES marketplace_listings (id) ON DELETE CASCADE,
                FOREIGN KEY (seller_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        conn.commit()
        cur.close()

if __name__ == '__main__':
    with app.app_context():
        print("Initialisation/Vérification du schéma PostgreSQL...")
        init_db()
    app.run(debug=False, port=8000)