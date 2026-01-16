import os
import decimal
import psycopg2 # Importez psycopg2
import psycopg2.extras # Pour RealDictCursor
from urllib.parse import urlparse # Pour parser l'URL de la DB
from flask import current_app, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import json
from flask import Flask, request, redirect, url_for, flash, jsonify, g # Importez jsonify ici
from functools import wraps # Importez wraps pour le décorateur
from decimal import Decimal
import matplotlib
import matplotlib.dates as mdates # Assurez-vous d'avoir cet import
matplotlib.use('Agg') # Important: Utilisez le backend 'Agg' pour la génération d'images non-interactives
import matplotlib.pyplot as plt
import base64
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import time
import datetime as dt
from werkzeug.utils import secure_filename # Assurez-vous d'avoir cet import au début du fichier
import uuid # Pour générer des noms de fichiers uniques
load_dotenv()
# Render définit automatiquement DATABASE_URL pour votre base de données liée.


app = Flask(__name__)
app.config['DEBUG'] = True # <--- TRÈS IMPORTANT
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session dure 7 jours
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Remplacez par le serveur SMTP de votre fournisseur d'e-mail (ex: smtp.gmail.com)
app.config['MAIL_PORT'] = 587                  # Port SMTP (généralement 587 pour TLS, 465 pour SSL)
app.config['MAIL_USE_TLS'] = True              # Utiliser TLS (recommandé)
app.config['MAIL_USE_SSL'] = False             # Ne pas utiliser SSL si TLS est activé
app.config['MAIL_USERNAME'] = 'resell.notion2025@gmail.com' # Votre adresse e-mail d'envoi
app.config['MAIL_PASSWORD'] = 'aiym thsq fqwo mbqj' # Le mot de passe de votre e-mail (ou un mot de passe d'application si Gmail)
app.config['MAIL_DEFAULT_SENDER'] = 'resell.notion2025@gmail.com' # L'expéditeur par défaut

mail = Mail(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.needs_refresh_message = "Votre session a expiré, veuillez vous reconnecter."
login_manager.needs_refresh_message_category = "info"

TABLE_NAME = "sku_database" # Le nom de la table
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, '..', 'www.resellnotion.stats.com', 'assets')

# Configuration pour l'upload de fichiers
UPLOAD_FOLDER = 'static/uploads/listings' # Dossier où les images seront sauvegardées
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



mail = Mail(app)
# Crée le dossier d'upload s'il n'existe pas
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_performance_report_email(recipient_email, subject, html_body):
    """
    Envoie un e-mail de bilan de performance à un destinataire donné.
    """
    try:
        msg = Message(subject, recipients=[recipient_email])
        msg.html = html_body # Le corps de l'e-mail sera en HTML
        mail.send(msg)
        print(f"E-mail de bilan envoyé à {recipient_email} avec succès.")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'e-mail à {recipient_email}: {e}")
        return False

def _save_report_metadata(conn, user_id, report_type, period_label, report_start_date, report_end_date):
    """Sauvegarde les métadonnées d'un rapport dans la base de données."""
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO generated_reports (user_id, report_type, period_label, report_start_date, report_end_date, generation_date, file_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (user_id, report_type, period_label, report_start_date, report_end_date, datetime.now(), None)) # file_path est None pour les rapports dynamiques
        report_id = cur.fetchone()[0]
        conn.commit()
        print(f"Rapport de type '{report_type}' pour la période '{period_label}' enregistré avec l'ID: {report_id}")
        return report_id
    except Exception as e:
        print(f"ERREUR lors de l'enregistrement des métadonnées du rapport: {e}")
        if conn:
            conn.rollback() # Annuler la transaction en cas d'erreur
        return None
    finally:
        if cur and not cur.closed:
            cur.close()

# --- Fonction get_report_data (mise à jour pour la correction Decimal) ---
def get_report_data(conn, user_id, start_date, end_date, report_type):
    cur = None
    report_data = {
        'sales_summary': {
            'total_revenue': decimal.Decimal(0),
            'total_profit': decimal.Decimal(0),
            'margin_rate': decimal.Decimal(0)
        },
        'sales_history': [],
        'stock_indicators': {
            'total_products_in_stock': 0,
            'total_stock_value': decimal.Decimal(0),
            'stock_rotation_rate': decimal.Decimal(0)
        },
        'stock_by_size': [],
        'daily_sales_count': [],
        'daily_purchases_count': [],
        'oldest_product_in_stock': None # NOUVEAU : pour la paire la plus vieille
    }

    print(f"\n--- DEBUG get_report_data ---")
    print(f"  user_id: {user_id}")
    print(f"  start_date: {start_date} (Type: {type(start_date)})")
    print(f"  end_date: {end_date} (Type: {type(end_date)})")
    print(f"  report_type: '{report_type}' (Type: {type(report_type)})")

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Requête pour le résumé des ventes
        cur.execute("""
            SELECT
                COALESCE(SUM(sale_price), 0.00) AS total_revenue,
                COALESCE(SUM(profit), 0.00) AS total_profit
            FROM
                sales
            WHERE
                user_id = %s AND sale_date BETWEEN %s AND %s;
        """, (user_id, start_date, end_date))
        summary = cur.fetchone()

        report_data['sales_summary']['total_revenue'] = summary['total_revenue']
        report_data['sales_summary']['total_profit'] = summary['total_profit']
        if summary['total_revenue'] > 0:
            report_data['sales_summary']['margin_rate'] = (summary['total_profit'] / summary['total_revenue'] * 100).quantize(decimal.Decimal('0.01'))
        else:
            report_data['sales_summary']['margin_rate'] = decimal.Decimal(0)

        # 2. Requête pour l'historique des ventes (toujours par jour)
        group_by_clause = "DATE_TRUNC('day', sale_date)"

        sql_query_history = f"""
            SELECT
                {group_by_clause} AS period,
                COALESCE(SUM(sale_price), 0.00) AS revenue,
                COALESCE(SUM(profit), 0.00) AS profit
            FROM
                sales
            WHERE
                user_id = %s AND sale_date BETWEEN %s AND %s
            GROUP BY
                period
            ORDER BY
                period;
        """
        print(f"  SQL Query History (Daily Grouping): {sql_query_history}")
        print(f"  Parameters: (user_id={user_id}, start_date={start_date}, end_date={end_date})")

        cur.execute(sql_query_history, (user_id, start_date, end_date))
        sales_history = cur.fetchall()
        report_data['sales_history'] = sales_history
        print(f"  Sales History fetched: {sales_history}")

        # 3. Requêtes pour les indicateurs de stock (total)
        cur.execute("""
            SELECT
                COUNT(id) AS total_products_in_stock,
                COALESCE(SUM(purchase_price), 0.00) AS total_stock_value
            FROM
                products
            WHERE
                user_id = %s;
        """, (user_id,))
        stock_summary = cur.fetchone()

        report_data['stock_indicators']['total_products_in_stock'] = stock_summary['total_products_in_stock']
        report_data['stock_indicators']['total_stock_value'] = stock_summary['total_stock_value']

        # Taux de rotation du stock
        if report_data['stock_indicators']['total_stock_value'] > 0:
            report_data['stock_indicators']['stock_rotation_rate'] = (
                report_data['sales_summary']['total_revenue'] / report_data['stock_indicators']['total_stock_value']
            ).quantize(decimal.Decimal('0.01'))
        else:
            report_data['stock_indicators']['stock_rotation_rate'] = decimal.Decimal(0)

        # Requête pour le décompte du stock par taille
        cur.execute("""
            SELECT
                COALESCE(size, 'Non spécifié') AS size,
                COUNT(id) AS product_count
            FROM
                products
            WHERE
                user_id = %s
            GROUP BY
                size
            ORDER BY
                product_count DESC;
        """, (user_id,))
        stock_by_size_data = cur.fetchall()
        report_data['stock_by_size'] = stock_by_size_data
        print(f"  Stock by Size fetched: {stock_by_size_data}")

        # Requête pour le nombre de ventes (transactions) par jour
        cur.execute("""
            SELECT
                DATE_TRUNC('day', sale_date) AS period,
                COUNT(id) AS sales_count
            FROM
                sales
            WHERE
                user_id = %s AND sale_date BETWEEN %s AND %s
            GROUP BY
                period
            ORDER BY
                period;
        """, (user_id, start_date, end_date))
        daily_sales_data = cur.fetchall()
        report_data['daily_sales_count'] = daily_sales_data
        print(f"  Daily Sales Count fetched: {daily_sales_data}")


        # Requête pour le nombre de produits achetés (entrées en stock) par jour
        cur.execute("""
            SELECT
                DATE_TRUNC('day', date_added) AS period,
                COUNT(id) AS products_bought_count
            FROM
                products
            WHERE
                user_id = %s AND date_added BETWEEN %s AND %s
            GROUP BY
                period
            ORDER BY
                period;
        """, (user_id, start_date, end_date))
        daily_purchases_data = cur.fetchall()
        report_data['daily_purchases_count'] = daily_purchases_data
        print(f"  Daily Purchases Count fetched: {daily_purchases_data}")

        # NOUVEAU : Requête pour la paire la plus vieille en stock
        cur.execute("""
            SELECT
                name,
                sku,
                date_added,
                size,
                image_url
            FROM
                products
            WHERE
                user_id = %s
            ORDER BY
                date_added ASC
            LIMIT 1;
        """, (user_id,))
        oldest_product = cur.fetchone()
        report_data['oldest_product_in_stock'] = oldest_product
        print(f"  Oldest product in stock fetched: {oldest_product}")


        print(f"--- FIN DEBUG get_report_data ---")
        return report_data

    except Exception as e:
        print(f"ERREUR DANS get_report_data: {e}")
        return None

    finally:
        if cur and not cur.closed:
            cur.close()


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

# Gérer la connexion à la base de données pour chaque requête
@app.before_request
def before_request():
    # Ouvre une connexion à la DB et la stocke dans l'objet 'g' global de Flask
    # Cela évite d'ouvrir/fermer la connexion dans chaque route
    g.db = get_db_connection()

@app.teardown_appcontext
def close_db(error):
    # Ferme la connexion à la DB à la fin de chaque requête, même en cas d'erreur
    if hasattr(g, 'db'):
        g.db.close()










# --- Décorateur pour les rôles admin ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Accès non autorisé. Vous devez être administrateur.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# --- Routes d'authentification ---
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- NOUVEAU : Chargement des données SKU au démarrage de l'application ---
SKU_DATA = []
# Utilisez le chemin absolu fourni par l'utilisateur


# Chemin complet vers le fichier JSON
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
    SKU_DATA = [] # S'assurer que SKU_DATA est une liste vide en cas d'échec

# --- NOUVELLE ROUTE POUR LES SUGGESTIONS SKU ---
@app.route('/get_sku_suggestions', methods=['GET'])
@login_required  # Cette ligne est conservée comme demandé
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

        # Le pattern de recherche pour ILIKE
        search_pattern = f"%{query}%"

        # Requête SQL pour rechercher dans 'sku' ou 'product_name' et limiter les résultats
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
                'sku': row[0],  # Premier élément est le sku
                'image_url': row[1],  # Deuxième élément est l'image_url
                'product_name': row[2]  # Troisième élément est le product_name
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


@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']

        # Vérification des champs vides
        if not username or not email or not password:
            flash('Veuillez remplir tous les champs.', 'danger')
            return render_template('register.html', email=email, username=username)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = g.db  # Utilise la connexion existante fournie par g.db

        try:
            # Vérification si l'utilisateur existe déjà
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # Crée un curseur pour la sélection
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))  # Utilisez %s pour PostgreSQL
            existing_user = cur.fetchone()
            cur.close()  # Fermez le curseur après l'opération

            if existing_user:
                flash("Cet email est déjà enregistré. Veuillez en utiliser un autre ou vous connecter.", "danger")
                return render_template('register.html', email=email, username=username)

            # Insertion du nouvel utilisateur
            cur = conn.cursor()  # Crée un nouveau curseur pour l'insertion
            cur.execute("INSERT INTO users (email, password_hash, username) VALUES (%s, %s, %s)",
                        # Utilisez %s pour PostgreSQL
                        (email, hashed_password, username))
            conn.commit()  # Engage la transaction sur la connexion
            cur.close()  # Fermez le curseur après l'opération

            flash("Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            # En cas d'erreur, annule la transaction pour éviter les données partielles
            conn.rollback()
            flash(f"Une erreur est survenue lors de l'enregistrement: {e}", "danger")
            print(f"Erreur lors de l'enregistrement de l'utilisateur: {e}")  # Pour le débogage
            return render_template('register.html', email=email, username=username)

    return render_template('register.html')


# MODIFIÉ: Route de connexion pour vérifier le statut de la clé immédiatement après la connexion
@app.route('/login', methods=('GET', 'POST'))
def login():
    # Si l'utilisateur est déjà connecté, vérifiez son statut de clé avant de le rediriger vers le tableau de bord
    if current_user.is_authenticated:
        if current_user.key_status == 'inactive':
            flash("Votre clé est inactive. Veuillez la réactiver via le bot Discord pour accéder au contenu.", "warning")
            return redirect(url_for('key_activation_required'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form

        conn = g.db # Utilise la connexion existante fournie par g.db

        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur
            cur.execute("SELECT * FROM users WHERE email = %s", (email,)) # Utilisez %s pour PostgreSQL
            user_data = cur.fetchone()
            cur.close() # Fermez le curseur après l'opération

            if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
                user = User(
                    id=user_data['id'],
                    email=user_data['email'],
                    username=user_data['username'],
                    avatar_url=user_data['avatar_url'],
                    is_admin=bool(user_data['is_admin']),
                    discord_id=user_data['discord_id'],
                    key_status=user_data['key_status'] # Assurez-vous que key_status est bien chargé ici
                )
                login_user(user, remember=remember)

                # VÉRIFICATION IMMÉDIATE DU STATUT DE LA CLÉ APRÈS LA CONNEXION
                if user.key_status == 'inactive':
                    flash("Connexion réussie, mais votre clé est inactive. Veuillez la réactiver via le bot Discord pour accéder au contenu.", "warning")
                    return redirect(url_for('key_activation_required'))
                else:
                    flash("Connexion réussie !", "success")
                    return redirect(url_for('dashboard'))
            else:
                flash("Email ou mot de passe incorrect.", "danger")
        except Exception as e:
            flash(f"Une erreur est survenue lors de la connexion: {e}", 'danger')
            print(f"Erreur de connexion: {e}") # Pour le débogage
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('login'))

# NOUVELLE ROUTE : Page requise pour l'activation de la clé
@app.route('/key_activation_required')
@login_required # L'utilisateur doit être connecté pour voir cette page
def key_activation_required():
    # Si la clé est devenue active pendant que l'utilisateur était sur cette page, redirigez-le
    if current_user.key_status == 'active':
        flash("Votre clé est maintenant active ! Bienvenue.", "success")
        return redirect(url_for('dashboard'))
    return render_template('key_activation_required.html') # Ce template est à créer

import psycopg2.extras # Assurez-vous que cet import est présent en haut de votre fichier


@app.route('/')
@login_required

def dashboard():
    conn = g.db
    cur = None

    try:
        # Définir le début et la fin du mois en cours
        today = date.today()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        # 1. Calcul du nombre de produits en stock
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(quantity) FROM products WHERE user_id = %s", (current_user.id,))
        products_in_stock_query = cur.fetchone()
        products_in_stock = products_in_stock_query['sum'] if products_in_stock_query and products_in_stock_query['sum'] is not None else 0
        cur.close()

        # 2. Valeur totale du stock
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(purchase_price * quantity) FROM products WHERE user_id = %s", (current_user.id,))
        total_stock_value_query = cur.fetchone()
        total_stock_value = total_stock_value_query['sum'] if total_stock_value_query and total_stock_value_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # 3. Calcul du bénéfice des ventes pour le mois en cours
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(profit) FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s", (current_user.id, start_of_month, end_of_month))
        total_sales_profit_query = cur.fetchone()
        total_sales_profit = total_sales_profit_query['sum'] if total_sales_profit_query and total_sales_profit_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # 4. Calcul du chiffre d'affaires pour le mois en cours
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(sale_price) FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s", (current_user.id, start_of_month, end_of_month))
        total_revenue_query = cur.fetchone()
        total_revenue = total_revenue_query['sum'] if total_revenue_query and total_revenue_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # 7. NOUVEAU : Calcul du total des paiements en attente
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COALESCE(SUM(sale_price), 0) FROM sales WHERE user_id = %s AND payment_status = 'en_attente'", (current_user.id,))
        total_pending_payments_query = cur.fetchone()
        total_pending_payments = total_pending_payments_query['coalesce'] if total_pending_payments_query else Decimal('0.00')
        cur.close()

        # 8. Récupération des 5 dernières ventes (CORRECTION ICI)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # On essaie de prendre l'image, le sku et la taille depuis sales s'ils existent, sinon via le JOIN
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
        cur.close()

        latest_sales_for_template = []
        for sale in latest_sales_raw:
            sale_dict = dict(sale)
            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'
            sale_dict['image_url'] = sale['image_url'] if sale['image_url'] else None
            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(float(sale_dict['sale_price'] or 0.0))
            sale_dict['profit_formatted'] = '{:.2f} €'.format(float(sale_dict['profit'] or 0.0))
            latest_sales_for_template.append(sale_dict)

        return render_template('dashboard.html',
                               total_stock_value=total_stock_value,
                               total_sales_profit=total_sales_profit,
                               total_revenue=total_revenue,
                               total_pending_payments=total_pending_payments,
                               latest_sales=latest_sales_for_template)

    except Exception as e:
        flash(f"Erreur tableau de bord: {e}", 'danger')
        return redirect(url_for('login'))
    finally:
        if cur and not cur.closed: cur.close()
@app.route('/profile', methods=('GET', 'POST'))
@login_required  # L'utilisateur doit être connecté pour accéder à cette page
def profile():
    conn = g.db
    cur = None # Initialisation du curseur

    if request.method == 'POST':
        new_username = request.form.get('username')
        new_discord_id = request.form.get('discord_id')

        if not new_username:
            flash("Le nom d'utilisateur ne peut pas être vide.", "danger")
            return render_template('profile.html', user=current_user)

        try:
            cur = conn.cursor() # Crée un curseur pour l'UPDATE
            cur.execute(
                "UPDATE users SET username = %s, discord_id = %s WHERE id = %s", # Placeholders %s
                (new_username, new_discord_id, current_user.id)
            )
            conn.commit()
            cur.close() # Ferme le curseur

            current_user.username = new_username
            current_user.discord_id = new_discord_id

            flash("Votre profil a été mis à jour avec succès !", "success")
            return redirect(url_for('profile'))
        except psycopg2.IntegrityError as e: # Changement ici : psycopg2.IntegrityError
            conn.rollback() # Annuler la transaction en cas d'erreur
            # Gérer l'erreur si l'ID Discord est déjà utilisé (erreur de contrainte UNIQUE)
            # Le message d'erreur peut varier, ou utiliser e.pgcode
            if 'duplicate key value violates unique constraint "users_discord_id_key"' in str(e) or 'duplicate key value violates unique constraint' in str(e): # Exemple de message PostgreSQL
                flash("Cet ID Discord est déjà utilisé par un autre compte.", "danger")
            else:
                flash("Une erreur est survenue lors de la mise à jour de votre profil.", "danger")
            print(f"Database error on profile update: {e}")
            return render_template('profile.html', user=current_user)
        except Exception as e:
            conn.rollback() # Annuler la transaction pour toute autre erreur
            flash(f"Une erreur inattendue est survenue : {e}", "danger")
            print(f"Error updating profile: {e}")
            return render_template('profile.html', user=current_user)
        finally:
            if cur and not cur.closed: # S'assurer que le curseur est fermé même en cas d'erreur
                cur.close()

    # Pour la requête GET, passez l'objet current_user au template
    return render_template('profile.html', user=current_user)
@app.route('/products')
@login_required
def products():
    conn = g.db
    cur = None # Initialisation du curseur

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur
        # MODIFICATION ICI : Ajouter 'date_added' à la liste des colonnes sélectionnées
        # et utiliser %s pour le placeholder
        cur.execute('SELECT id, sku, name, size, purchase_price, quantity, price, image_url, date_added FROM products WHERE user_id = %s AND quantity > 0 ORDER BY date_added DESC',
                                     (current_user.id,))
        products_data = cur.fetchall()
        cur.close() # Ferme le curseur

        return render_template('products.html', products=products_data)
    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement des produits: {e}", 'danger')
        print(f"Erreur produits: {e}")
        return redirect(url_for('dashboard')) # Ou une page d'erreur appropriée
    finally:
        if cur and not cur.closed:
            cur.close()


@app.route('/add_cashback/<int:product_id>', methods=['POST'])
@login_required
def add_cashback(product_id):
    conn = g.db
    cur = None
    try:
        data = request.get_json()
        cashback_amount = data.get('amount')

        if cashback_amount is None or not isinstance(cashback_amount, (int, float)) or float(cashback_amount) <= 0:
            return jsonify({'success': False, 'message': 'Montant invalide.'}), 400

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Vérifier que le produit existe et appartient à l'utilisateur actuel
        cur.execute("SELECT purchase_price FROM products WHERE id = %s AND user_id = %s", (product_id, current_user.id))
        product = cur.fetchone()

        if not product:
            return jsonify({'success': False, 'message': 'Produit non trouvé ou non autorisé.'}), 404

        current_price = product['purchase_price']

        # **Correction ici : conversion en float avant la soustraction**
        new_price = float(current_price) - float(cashback_amount)

        # S'assurer que le prix ne devient pas négatif
        if new_price < 0:
            new_price = 0

        # 2. Mettre à jour le prix d'achat dans la base de données
        # Note : Le pilote psycopg2 est capable de convertir un float en type décimal de la BDD
        cur.execute("UPDATE products SET purchase_price = %s WHERE id = %s AND user_id = %s",
                    (new_price, product_id, current_user.id))
        conn.commit()

        return jsonify({'success': True, 'message': 'Cashback ajouté avec succès!'})

    except Exception as e:
        print(f"Erreur lors de l'ajout du cashback: {e}")
        conn.rollback()  # Annuler les modifications en cas d'erreur
        return jsonify({'success': False, 'message': 'Une erreur est survenue.'}), 500
    finally:
        if cur:
            cur.close()


@app.route('/products/add', methods=('GET', 'POST'))
@login_required
def add_product():
    if request.method == 'POST':
        sku = request.form.get('sku', '')
        name = request.form.get('name', '')
        image_url = request.form.get('image_url', '')
        description = request.form.get('description', '')

        # Récupération des listes de tailles et de prix
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
                    # Quantité par défaut à 1, car le champ a été supprimé
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

    # Pour les requêtes GET, on s'assure que toutes les variables sont définies
    # avec des valeurs par défaut pour éviter l'erreur Jinja2.
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

        # Nous allons utiliser la clause ILIKE pour une recherche insensible à la casse
        # et le caractère '%' pour les correspondances partielles.
        # Nous concaténons '%' au début et à la fin de la requête.
        search_pattern = f"%{query}%"

        # Requête SQL pour rechercher dans product_name ou sku et limiter les résultats
        sql_query = f"""
            SELECT sku, product_name, image_url
            FROM {TABLE_NAME}
            WHERE product_name ILIKE %s OR sku ILIKE %s
            LIMIT 10;
        """

        cur.execute(sql_query, (search_pattern, search_pattern))

        results = cur.fetchall()  # Récupère tous les résultats

        for row in results:
            suggestions.append({
                'sku': row[0],  # Premier élément est le sku
                'name': row[1],  # Deuxième élément est le product_name
                'image_url': row[2]  # Troisième élément est l'image_url
            })

        cur.close()
        conn.close()  # Toujours fermer la connexion

        return jsonify(suggestions)

    except Exception as e:
        print(f"Erreur lors de la récupération des suggestions : {e}")
        return jsonify({"error": f"Une erreur est survenue lors de la recherche: {e}"}), 500
    finally:
        if conn:
            # S'assurer que la connexion est fermée même en cas d'erreur non gérée
            conn.close()

@app.route('/get_product_name_suggestions', methods=['GET'])
@login_required
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

        # Nous allons utiliser la clause ILIKE pour une recherche insensible à la casse
        # et le caractère '%' pour les correspondances partielles.
        # Nous concaténons '%' au début et à la fin de la requête.
        search_pattern = f"%{query}%"

        # Requête SQL pour rechercher dans product_name ou sku et limiter les résultats
        sql_query = f"""
            SELECT sku, product_name, image_url
            FROM {TABLE_NAME}
            WHERE product_name ILIKE %s OR sku ILIKE %s
            LIMIT 10;
        """

        cur.execute(sql_query, (search_pattern, search_pattern))

        results = cur.fetchall()  # Récupère tous les résultats

        for row in results:
            suggestions.append({
                'sku': row[0],  # Premier élément est le sku
                'name': row[1],  # Deuxième élément est le product_name
                'image_url': row[2]  # Troisième élément est l'image_url
            })

        cur.close()
        conn.close()  # Toujours fermer la connexion

        return jsonify(suggestions)

    except Exception as e:
        print(f"Erreur lors de la récupération des suggestions : {e}")
        return jsonify({"error": f"Une erreur est survenue lors de la recherche: {e}"}), 500
    finally:
        if conn:
            # S'assurer que la connexion est fermée même en cas d'erreur non gérée
            conn.close()


@app.route('/generate_wtb_wts_image', methods=['POST'])
@login_required # Si la génération d'image nécessite une connexion, laissez-le. Sinon, retirez-le.
def generate_wtb_wts_image():
    try:
        data = request.json
        products_to_generate_raw = data.get('products')
        mode = data.get('mode')

        if not products_to_generate_raw:
            return jsonify({'error': 'No products provided for image generation'}), 400

        # 1. Regrouper les produits (conserve la logique de regroupement précédente)
        grouped_products = {}
        for product in products_to_generate_raw:
            sku = product.get('sku', 'N/A')
            # Utilisez defaultImageUrl défini côté client pour correspondre à la logique
            default_placeholder_url_client = url_for('static', filename='sku_not_found.png', _external=True)
            image_url = product.get('image_url', default_placeholder_url_client)
            name = product.get('name', 'Produit Inconnu')
            size = product.get('size', 'N/A')

            key = (sku, image_url)  # Regroupement par SKU et URL d'image
            if key not in grouped_products:
                grouped_products[key] = {
                    'name': name,
                    'sku': sku,
                    'image_url': image_url,
                    'sizes': []
                }
            if size != 'N/A' and size not in grouped_products[key]['sizes']:
                grouped_products[key]['sizes'].append(size)

        final_products_for_image = list(grouped_products.values())
        for p in final_products_for_image:
            p['sizes'] = sorted(p['sizes'])

        # --- NOUVEAU : Pagination des produits ---
        max_products_per_image = 15  # 5 colonnes * 3 lignes
        # Divise la liste des produits en lots
        product_batches = [final_products_for_image[i:i + max_products_per_image]
                           for i in range(0, len(final_products_for_image), max_products_per_image)]

        generated_image_urls = []

        for batch_index, product_batch in enumerate(product_batches):
            # Charger l'image de fond
            base_image_path = os.path.join(current_app.root_path, 'static', 'logo.png')
            if not os.path.exists(base_image_path):
                raise FileNotFoundError('Background image logo.png not found at path: ' + base_image_path)

            base_img = Image.open(base_image_path).convert("RGBA")
            img_width, img_height = base_img.size
            draw = ImageDraw.Draw(base_img)

            # Définir les polices par défaut (elles seront ajustées plus tard)
            try:
                font_path_bold = os.path.join(current_app.root_path, 'static', 'arialbd.ttf')
                font_path_regular = os.path.join(current_app.root_path, 'static', 'arial.ttf')
                # Les tailles de base sont des valeurs de référence pour le calcul de getlength
                font_sku_base_ref = ImageFont.truetype(font_path_bold, 100)
                font_size_base_ref = ImageFont.truetype(font_path_regular, 80)
            except IOError:
                current_app.logger.warning("Warning: Custom fonts not found, using default font.")
                font_sku_base_ref = ImageFont.load_default()
                font_size_base_ref = ImageFont.load_default()
            except Exception as e:
                current_app.logger.error(f"Error loading custom fonts: {e}, using default font.")
                font_sku_base_ref = ImageFont.load_default()
                font_size_base_ref = ImageFont.load_default()

            num_products_in_batch = len(product_batch)
            if num_products_in_batch == 0:
                continue  # Passer au lot suivant si vide

            # Définition des paramètres de disposition
            margin_x = 50  # Marge horizontale totale pour l'image (gauche + droite)
            margin_y = 50  # Marge verticale totale pour l'image (haut + bas)
            spacing_x = 30  # Espace entre les colonnes
            spacing_y = 30  # Espace entre les lignes

            # Calcul du nombre de colonnes et de lignes pour ce lot
            # Max 5 colonnes, Max 3 lignes par image
            max_cols_per_image = 5
            max_rows_per_image = 3

            # Ajustement dynamique du nombre de colonnes pour 1, 2, 3, 4, 5 produits pour optimiser l'espace
            if num_products_in_batch == 1:
                cols = 1
                rows = 1
            elif num_products_in_batch == 2:
                cols = 2
                rows = 1
            elif num_products_in_batch <= 5:  # 3, 4, 5 produits
                cols = num_products_in_batch
                rows = 1
            elif num_products_in_batch <= 10:  # 6 à 10 produits
                cols = 5
                rows = 2
            else:  # num_products_in_batch > 10 et <= 15 (max par image)
                cols = 5
                rows = 3

            # Calcul des dimensions disponibles pour la grille de contenu
            available_width = img_width - margin_x
            available_height = img_height - margin_y

            # Calcul de la largeur de cellule et de la hauteur de cellule
            if cols > 0:
                cell_width = (available_width - (cols - 1) * spacing_x) / cols
            else:
                cell_width = available_width

            if rows > 0:
                cell_height = (available_height - (rows - 1) * spacing_y) / rows
            else:
                cell_height = available_height

            if cell_width <= 0 or cell_height <= 0:
                current_app.logger.error(
                    f"Calculated cell dimensions are invalid: cell_width={cell_width}, cell_height={cell_height}")
                raise ValueError('Calculated cell dimensions are invalid. Not enough space for products.')

            # Facteurs pour la répartition de l'espace dans chaque cellule
            img_ratio = 0.6  # 60% de la hauteur de la cellule pour l'image
            text_ratio = 0.4  # 40% de la hauteur de la cellule pour le texte
            padding_inside_cell = 10  # Petit padding à l'intérieur de chaque cellule

            # MODIFICATIONS ICI POUR LES TAILLES DE POLICE
            # Définir une taille de police maximale et minimale pour assurer la lisibilité.
            # J'ai augmenté ces valeurs pour une meilleure visibilité.
            MIN_FONT_SIZE_PX_SKU = 35  # Augmenté pour une meilleure lisibilité
            MIN_FONT_SIZE_PX_GENERAL = 30  # Augmenté pour une meilleure lisibilité
            MAX_FONT_SIZE_PX_SKU = 70  # Nouvelle limite max plus haute
            MAX_FONT_SIZE_PX_GENERAL = 60  # Nouvelle limite max plus haute

            text_height_available = cell_height * text_ratio - 2 * padding_inside_cell

            # Calcul d'une taille de police suggérée basée sur la hauteur disponible pour une ligne de texte
            # On considère qu'il y aura 2 lignes de texte (SKU + Tailles) et un petit espacement entre elles.
            # Diviser par 2.2 donne un peu plus d'espace pour chaque ligne et le padding.
            suggested_font_size_height_sku = int(text_height_available / 2.1)  # Ajustement pour plus d'espace
            suggested_font_size_height_general = int(text_height_available / 2.1)  # Ajustement pour plus d'espace

            # Suggérer une taille de police basée sur la largeur de la cellule
            # Pour que le texte ne dépasse pas la largeur de la cellule.
            # On utilise getlength pour estimer la largeur du texte avec une taille de référence
            # et on scale proportionnellement pour qu'il rentre dans la largeur disponible.
            # On prend un facteur de 0.9 pour laisser un peu de marge.
            avg_char_width_sku = font_sku_base_ref.getlength("M")  # Largeur moyenne d'un caractère
            avg_char_width_general = font_size_base_ref.getlength("M")

            # Estimer la largeur d'une chaîne typique (ex: SKU le plus long, liste de tailles)
            # On prend un exemple de texte assez long pour le SKU et les tailles
            sample_sku_text = "555088-105"  # Exemple de SKU typique
            sample_sizes_text = "42 EU, 9 US, 8 UK"  # Exemple de tailles typiques

            # Calcul basé sur la largeur disponible et une estimation de la longueur du texte
            # On divise la largeur disponible par la "largeur relative" d'un texte de référence à sa taille de base
            if font_sku_base_ref.getlength(sample_sku_text) > 0:
                suggested_font_size_width_sku = int((cell_width - 2 * padding_inside_cell) / (
                            font_sku_base_ref.getlength(sample_sku_text) / font_sku_base_ref.size) * 0.9)
            else:
                suggested_font_size_width_sku = MAX_FONT_SIZE_PX_SKU  # Fallback si le calcul échoue

            if font_size_base_ref.getlength(sample_sizes_text) > 0:
                suggested_font_size_width_general = int((cell_width - 2 * padding_inside_cell) / (
                            font_size_base_ref.getlength(sample_sizes_text) / font_size_base_ref.size) * 0.9)
            else:
                suggested_font_size_width_general = MAX_FONT_SIZE_PX_GENERAL  # Fallback

            # Prendre le minimum des suggestions de largeur et de hauteur pour chaque police
            final_font_size_sku = min(suggested_font_size_height_sku, suggested_font_size_width_sku)
            final_font_size_general = min(suggested_font_size_height_general, suggested_font_size_width_general)

            # Appliquer les tailles minimales et maximales
            final_font_size_sku = max(MIN_FONT_SIZE_PX_SKU, min(final_font_size_sku, MAX_FONT_SIZE_PX_SKU))
            final_font_size_general = max(MIN_FONT_SIZE_PX_GENERAL,
                                          min(final_font_size_general, MAX_FONT_SIZE_PX_GENERAL))

            # Charger les polices avec les tailles adaptées
            if font_path_bold and os.path.exists(font_path_bold):
                font_sku_adapted = ImageFont.truetype(font_path_bold, final_font_size_sku)
            else:
                font_sku_adapted = ImageFont.load_default()

            if font_path_regular and os.path.exists(font_path_regular):
                font_size_adapted = ImageFont.truetype(font_path_regular, final_font_size_general)
            else:
                font_size_adapted = ImageFont.load_default()

            for i, product in enumerate(product_batch):
                col_index = i % cols
                row_index = i // cols

                # Calcul des coordonnées de départ pour chaque cellule
                start_x = (margin_x // 2) + col_index * (cell_width + spacing_x)
                start_y = (margin_y // 2) + row_index * (cell_height + spacing_y)

                # Dessiner la carte noire semi-transparente
                card_color = (0, 0, 0, 128)  # Noir avec 50% d'opacité (RGBA)
                draw.rectangle([int(start_x), int(start_y), int(start_x + cell_width), int(start_y + cell_height)],
                               fill=card_color)

                # Zone allouée pour l'image dans la cellule
                allocated_img_height = cell_height * img_ratio

                # Charger et placer l'image du produit
                max_img_width = cell_width - 2 * padding_inside_cell

                try:
                    product_image_url = product.get('image_url')
                    sku_not_found_local_path = os.path.join(current_app.root_path, 'static', 'sku_not_found.png')

                    if not product_image_url or \
                            product_image_url == url_for('static', filename='placeholder.png', _external=True) or \
                            product_image_url == url_for('static', filename='sku_not_found.png', _external=True):
                        image_to_load_path = sku_not_found_local_path
                        if os.path.exists(image_to_load_path):
                            product_img = Image.open(image_to_load_path).convert("RGBA")
                        else:
                            raise FileNotFoundError(f"Default image sku_not_found.png not found: {image_to_load_path}")
                    elif product_image_url.startswith('/static/'):
                        local_path_from_static = os.path.join(current_app.root_path, product_image_url.lstrip('/'))
                        if os.path.exists(local_path_from_static):
                            product_img = Image.open(local_path_from_static).convert("RGBA")
                        else:
                            raise FileNotFoundError(f"Local static image not found: {local_path_from_static}")
                    else:
                        response = requests.get(product_image_url, timeout=5)
                        response.raise_for_status()
                        product_img_data = response.content
                        product_img = Image.open(io.BytesIO(product_img_data)).convert("RGBA")

                    product_img.thumbnail((max_img_width, allocated_img_height), Image.Resampling.LANCZOS)

                    img_x_centered = start_x + (cell_width - product_img.width) // 2
                    img_y_centered = start_y + padding_inside_cell + (allocated_img_height - product_img.height) // 2

                    base_img.paste(product_img, (int(img_x_centered), int(img_y_centered)), product_img)

                except (requests.exceptions.RequestException, FileNotFoundError, ValueError) as e:
                    current_app.logger.error(
                        f"Error fetching/processing image for product {product.get('name', 'N/A')} ({product.get('sku', 'N/A')}): {e}")
                    error_text = "Image Indisponible"
                    # Utiliser la police adaptée pour le message d'erreur également
                    bbox_error = font_size_adapted.getbbox(error_text)
                    text_width_error, text_height_error = bbox_error[2], bbox_error[3]
                    text_x_error_centered = start_x + (cell_width - text_width_error) // 2
                    text_y_error_centered = start_y + padding_inside_cell + (
                                allocated_img_height - text_height_error) / 2
                    draw.text((int(text_x_error_centered), int(text_y_error_centered)),
                              error_text, font=font_size_adapted, fill=(255, 0, 0, 255))

                except Exception as e:
                    current_app.logger.error(
                        f"Unexpected error processing image for product {product.get('name', 'N/A')} ({product.get('sku', 'N/A')}): {e}")
                    error_text = "Erreur Image"
                    bbox_error = font_size_adapted.getbbox(error_text)
                    text_width_error, text_height_error = bbox_error[2], bbox_error[3]
                    text_x_error_centered = start_x + (cell_width - text_width_error) // 2
                    text_y_error_centered = start_y + padding_inside_cell + (
                                allocated_img_height - text_height_error) / 2
                    draw.text((int(text_x_error_centered), int(text_y_error_centered)),
                              error_text, font=font_size_adapted, fill=(255, 0, 0, 255))

                # Placer le SKU
                sku_text = f"{product['sku']}"
                actual_img_height_in_cell = product_img.height if 'product_img' in locals() else allocated_img_height

                text_area_start_y = start_y + allocated_img_height
                text_area_height = cell_height * text_ratio

                bbox_sku = font_sku_adapted.getbbox(sku_text)
                text_width_sku, text_height_sku = bbox_sku[2], bbox_sku[3]

                sizes_text = f"{', '.join(product['sizes'])}"
                bbox_sizes = font_size_adapted.getbbox(sizes_text)
                text_width_size, text_height_size = bbox_sizes[2], bbox_sizes[3]

                total_text_content_height = text_height_sku + text_height_size + padding_inside_cell / 2

                text_block_y_offset_in_area = (text_area_height - total_text_content_height) / 2

                text_y_sku = text_area_start_y + text_block_y_offset_in_area

                text_x_sku_centered = start_x + (cell_width - text_width_sku) // 2
                draw.text((int(text_x_sku_centered), int(text_y_sku)), sku_text, font=font_sku_adapted,
                          fill=(255, 255, 255, 255))

                # Placer les tailles
                text_y_size = text_y_sku + text_height_sku + padding_inside_cell / 2

                text_x_size_centered = start_x + (cell_width - text_width_size) // 2
                draw.text((int(text_x_size_centered), int(text_y_size)), sizes_text, font=font_size_adapted,
                          fill=(255, 255, 255, 255))

            # Enregistrer l'image générée temporairement et ajouter son URL
            output_dir = os.path.join(current_app.root_path, 'static', 'generated_images')
            os.makedirs(output_dir, exist_ok=True)

            timestamp = int(time.time())
            output_filename = f'generated_image_{mode}_{timestamp}_batch{batch_index + 1}.png'
            output_path = os.path.join(output_dir, output_filename)

            base_img.save(output_path)
            generated_image_urls.append(
                url_for('static', filename=f'generated_images/{output_filename}', _external=True))

        return jsonify({'image_urls': generated_image_urls})

    except Exception as e:
        current_app.logger.error(f"Error in generate_wtb_wts_image: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/products/<int:id>/edit', methods=('GET', 'POST'))
@login_required

def edit_product(id):
    conn = g.db
    cur = None # Initialisation du curseur

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur pour la sélection
        cur.execute('SELECT * FROM products WHERE id = %s AND user_id = %s',
                               (id, current_user.id))
        product = cur.fetchone()
        cur.close() # Ferme le curseur après la sélection

        if product is None:
            abort(404)  # Produit non trouvé ou non autorisé

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

            cur = conn.cursor() # Crée un nouveau curseur pour l'UPDATE
            cur.execute(
                "UPDATE products SET sku = %s, name = %s, size = %s, purchase_price = %s, quantity = %s, image_url = %s WHERE id = %s AND user_id = %s", # Placeholders %s
                (sku, name, size, purchase_price, quantity, image_url, id, current_user.id))
            conn.commit()
            flash('Produit mis à jour avec succès !', 'success')
            return redirect(url_for('products'))

    except psycopg2.IntegrityError as e: # Changement ici : psycopg2.IntegrityError
        conn.rollback() # Annuler la transaction en cas d'erreur
        if 'duplicate key value violates unique constraint "products_sku_key"' in str(e): # Exemple de message PostgreSQL
            flash('Un produit avec ce SKU existe déjà. Veuillez utiliser une référence unique.', 'danger')
        else:
            flash(f"Une erreur d'intégrité est survenue lors de la mise à jour du produit : {e}", 'danger')
        print(f"Database IntegrityError on product edit: {e}")
        return render_template('edit_product.html', product=product)
    except Exception as e:
        conn.rollback() # Annuler la transaction pour toute autre erreur
        flash(f"Une erreur inattendue est survenue : {e}", "danger")
        print(f"Error editing product: {e}")
        return render_template('edit_product.html', product=product)
    finally:
        if cur and not cur.closed: # S'assurer que le curseur est fermé
            cur.close()

    # Pour la requête GET, le produit est déjà chargé en dehors du POST
    return render_template('edit_product.html', product=product)

@app.route('/products/<int:id>/delete', methods=('POST',))
@login_required

def delete_product(id):
    conn = g.db
    cur = None # Initialisation du curseur

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur pour la sélection
        cur.execute('SELECT id FROM products WHERE id = %s AND user_id = %s',
                               (id, current_user.id))
        product = cur.fetchone()
        cur.close() # Ferme le curseur après la sélection

        if product is None:
            abort(404)

        cur = conn.cursor() # Crée un nouveau curseur pour la suppression
        cur.execute('DELETE FROM products WHERE id = %s AND user_id = %s', (id, current_user.id))
        conn.commit()
        flash('Produit supprimé avec succès !', 'success')
        return redirect(url_for('products'))

    except Exception as e:
        conn.rollback() # Annuler la transaction en cas d'erreur
        flash(f"Une erreur est survenue lors de la suppression du produit : {e}", 'danger')
        print(f"Erreur suppression produit: {e}")
        return redirect(url_for('products'))
    finally:
        if cur and not cur.closed: # S'assurer que le curseur est fermé
            cur.close()


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

        try:
            for sale_data in data['sales']:
                product_id = sale_data.get('product_id')
                sale_price = Decimal(str(sale_data.get('sale_price', 0)))
                sale_date = sale_data.get('sale_date') or date.today()
                payment_status = sale_data.get('payment_status', 'reçu')
                platform = sale_data.get('platform', 'Autre')

                # 1. Récupération des infos produit
                cur.execute("SELECT name, purchase_price, quantity, sku, size, image_url FROM products WHERE id = %s AND user_id = %s", (product_id, current_user.id))
                product = cur.fetchone()

                if not product:
                    continue # On passe au suivant si le produit est introuvable

                profit = sale_price - product['purchase_price']

                # 2. Insertion en base de données
                cur.execute('''
                    INSERT INTO sales (user_id, product_id, item_name, quantity, sale_price, purchase_price_at_sale, profit, sale_date, payment_status, sku, size, image_url)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (current_user.id, product_id, product['name'], sale_price, product['purchase_price'], profit, sale_date, payment_status, product['sku'], product['size'], product['image_url']))

                # 3. Mise à jour du stock
                if product['quantity'] <= 1:
                    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
                else:
                    cur.execute("UPDATE products SET quantity = quantity - 1 WHERE id = %s", (product_id, ))

                # 4. ENVOI DU WEBHOOK DISCORD
                discord_data = {
                    "embeds": [{
                        "title": "👟 Nouvelle Vente !",
                        "color": 3066993, # Vert émeraude
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
            return jsonify({"success": True, "redirect": url_for('dashboard')})

        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            cur.close()

    # GET
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM products WHERE user_id = %s AND quantity > 0", (current_user.id,))
    products = cur.fetchall()
    cur.close()
    return render_template('add_sale.html', products=products, today=date.today())
@app.route('/leaderboard')
@login_required # Pour que seuls les utilisateurs connectés puissent voir le classement
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


@app.route('/sale_success/<int:sale_id>')
@login_required
def sale_success(sale_id):
    conn = g.db
    cur = None
    try:
        # Utilisation de DictCursor pour appeler les colonnes par leur nom
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

        # Si toujours pas d'image, on fouille dans la sku_database via le nom
        if not image_url and item_name:
            cur.execute("SELECT image_url FROM sku_database WHERE product_name ILIKE %s LIMIT 1", (f"%{item_name}%",))
            sd_row = cur.fetchone()
            if sd_row:
                image_url = sd_row.get('image_url')

        # ÉTAPE 3 : Préparation propre pour le HTML
        # On crée un dictionnaire propre pour ne pas dépendre des index de la base
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
        # Utilisation de RealDictCursor pour récupérer les résultats sous forme de dictionnaire
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Requête optimisée : on récupère tout directement depuis la table 'sales'
        # car elle contient déjà le SKU et la Taille au moment de la vente.
        cur.execute('''
            SELECT
                id,
                item_name,
                quantity,
                sale_price,
                purchase_price_at_sale,
                sale_date,
                notes,
                sale_channel,
                shipping_cost,
                fees,
                profit,
                COALESCE(payment_status, 'reçu') as payment_status,
                sku,
                size
            FROM sales
            WHERE user_id = %s
            ORDER BY sale_date DESC
        ''', (current_user.id,))

        sales_data_raw = cur.fetchall()
        cur.close()

        sales_for_template = []
        for sale in sales_data_raw:
            sale_dict = dict(sale)

            # Gestion des valeurs par défaut si le SKU ou la Taille sont vides
            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'

            # Formatage des montants pour l'affichage (optionnel car fait aussi en Jinja2)
            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(float(sale_dict['sale_price'] or 0.0))
            sale_dict['profit_formatted'] = '{:.2f} €'.format(float(sale_dict['profit'] or 0.0))

            sales_for_template.append(sale_dict)

        return render_template('sales.html', sales=sales_for_template)

    except Exception as e:
        # Log de l'erreur précise dans la console pour le débogage
        print(f"--- ERREUR CRITIQUE VENTES ---")
        print(f"Détails : {e}")
        flash(f"Erreur lors du chargement des ventes. Veuillez contacter l'administrateur.", 'danger')
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
        # Assurez-vous d'avoir 'from flask import jsonify, request'
        data = request.get_json()
    except Exception as e:
        return jsonify({"success": False, "message": "Format de données invalide."}), 400

    new_status = data.get('status')

    if new_status not in ['reçu', 'en_attente']:
        return jsonify({"success": False, "message": "Statut de paiement invalide."}), 400

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM sales WHERE id = %s AND user_id = %s",
            (sale_id, current_user.id)
        )
        if not cur.fetchone():
            cur.close()
            return jsonify({"success": False, "message": "Vente non trouvée ou accès refusé."}), 403

        cur.execute(
            "UPDATE sales SET payment_status = %s WHERE id = %s",
            (new_status, sale_id)
        )
        conn.commit()
        cur.close()

        return jsonify({"success": True, "message": "Statut mis à jour.", "new_status": new_status})

    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de la mise à jour du statut de paiement: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur: {e}"}), 500
    finally:
        if cur and not cur.closed:
            cur.close()
@app.route('/sales/<int:id>/edit', methods=('GET', 'POST'))
@login_required

def edit_sale(id):
    conn = g.db
    cur = None  # Initialisation du curseur

    try:
        # Récupérer la vente existante
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM sales WHERE id = %s AND user_id = %s',
                    (id, current_user.id))
        sale = cur.fetchone()
        cur.close()

        if sale is None:
            abort(404)

        # Récupérer les produits de l'utilisateur pour le menu déroulant
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

            # Logique de mise à jour de la quantité en stock si le produit lié change ou si la quantité vendue change
            # Démarre une transaction explicite si plusieurs UPDATE sont en jeu

            # Remettre l'ancienne quantité en stock si un produit était lié
            if sale['product_id']:
                cur = conn.cursor()
                cur.execute('UPDATE products SET quantity = quantity + %s WHERE id = %s',
                            (sale['quantity'], sale['product_id']))
                cur.close()

            # Déduire la nouvelle quantité si un nouveau produit est lié
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
                        conn.rollback()  # Annuler les changements précédents si stock insuffisant
                        return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)

                    cur = conn.cursor()
                    cur.execute('UPDATE products SET quantity = %s WHERE id = %s', (new_stock, product_id))
                    cur.close()

            # Mettre à jour la vente elle-même
            cur = conn.cursor()
            cur.execute(
                "UPDATE sales SET product_id = %s, item_name = %s, quantity = %s, sale_price = %s, sale_date = %s, notes = %s WHERE id = %s AND user_id = %s",
                # Placeholders %s
                (product_id, item_name, quantity, sale_price, sale_date, notes, id, current_user.id))
            cur.close()

            conn.commit()
            flash('Vente mise à jour avec succès !', 'success')
            return redirect(url_for('sales'))

    except Exception as e:
        conn.rollback()  # Annuler toutes les modifications en cas d'erreur
        flash(f"Une erreur est survenue lors de la mise à jour de la vente : {e}", 'danger')
        print(f"Erreur édition vente: {e}")
        return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
    finally:
        if cur and not cur.closed:
            cur.close()

    # Pour la requête GET (affichage initial du formulaire d'édition)
    return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)

@app.route('/wtb_wts_gen', methods=('GET', 'POST'))
@login_required

def wtb_wts_gen():
    conn = g.db
    cur = None
    products = [] # Liste pour les produits en stock (WTS)

    try:
        # Récupérer tous les produits en stock de l'utilisateur pour le mode WTS
        # Nous avons besoin de l'image_url, sku, size pour la génération d'image
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT id, name, sku, size, image_url, quantity FROM products WHERE user_id = %s ORDER BY name',
                    (current_user.id,))
        products = cur.fetchall()
        cur.close()

    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement des produits : {e}", 'danger')
        print(f"Error loading products for WTS/WTB Gen: {e}")
    finally:
        if cur and not cur.closed:
            cur.close()

    # Le mode initial sera 'WTS' par défaut ou selon le paramètre de la requête si implémenté plus tard
    # Pour l'instant, on ne gère pas de POST pour le choix du mode, juste l'affichage GET.
    return render_template('wtb_wts_gen.html', products=products)


@app.route('/statistics')
@login_required
def statistics():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    period = request.args.get('period', 'month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    current_cash = float(request.args.get('current_cash', 0))

    now_dt = dt.datetime.now()
    today_date = now_dt.date()

    # --- Logique de filtrage de date ---
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
    total_profit = sum(float(s['profit'] or 0) for s in sales)
    total_purchase_cost = sum(float(s['purchase_price_at_sale'] or 0) for s in sales)
    volume = len(sales)

    roi_avg = (total_profit / total_purchase_cost * 100) if total_purchase_cost > 0 else 0
    health_score = round((min(6, roi_avg / 5) if roi_avg > 0 else 0) + min(4, volume / 2), 1)

    # 2. PAIEMENTS EN ATTENTE
    cur.execute(
        "SELECT COALESCE(SUM(sale_price), 0) as total FROM sales WHERE user_id = %s AND payment_status = 'en_attente'",
        (current_user.id,))
    res_pending = cur.fetchone()
    pending_payments = float(res_pending['total'] or 0)

    # 3. STOCK (quantité = 1)
    cur.execute(
        "SELECT SUM(purchase_price) as total_val, SUM(quantity) as total_qty FROM products WHERE user_id = %s AND quantity = 1",
        (current_user.id,))
    stock_info = cur.fetchone()
    valeur_achat_stock = float(stock_info['total_val'] or 0)
    stock_qty = stock_info['total_qty'] or 0

    # 4. TRÉSORERIE ENTIÈRE
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

    # 6. OBJECTIFS (N-1 ou Période précédente)
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

    # 7. STOCK MANAGEMENT (Latent)
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

    # 8. CONSEILS EXPERTS DIFFÉRENCIÉS
    expert_proj = f"Analyse Flux : Avec un profit net hebdomadaire estimé à {int(net_flow_weekly)}€, votre capital devrait croître de {int(proj_1m - total_base_cash)}€ d'ici 30 jours."

    if stock_avg_age > 30:
        expert_stock = f"Alerte Rotation : L'âge moyen de votre stock est de {stock_avg_age} jours. Il serait judicieux de liquider les pièces les plus anciennes pour libérer {int(valeur_achat_stock)}€ de trésorerie."
    else:
        expert_stock = f"Santé Stock : Excellente rotation. Votre stock est récent, ce qui maximise vos chances de réaliser votre profit latent de {int(profit_latent)}€ rapidement."

    return render_template('statistics.html',
                           sales=sales, revenue=total_revenue, profit=total_profit,
                           volume=volume, roi_avg=roi_avg, health_score=health_score,
                           stock_value=valeur_achat_stock, stock_qty=stock_qty,
                           period=period, start_date=start_str, end_date=end_str,
                           valeur_achat_stock=valeur_achat_stock, profit_latent=profit_latent,
                           ca_latent=ca_latent, stock_avg_age=stock_avg_age,
                           expert_proj=expert_proj, expert_stock=expert_stock,
                           current_cash=current_cash, pending_payments=pending_payments,
                           total_base_cash=total_base_cash,
                           proj_1w=proj_1w, proj_1m=proj_1m, proj_1y=proj_1y,
                           ref_rev=ref_rev, ref_prof=ref_prof, has_ref=has_ref)


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
    # Calcul du ROI Moyen (Total Profit / Total Achat)
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
@app.route('/download-report-pdf')
@login_required
def download_report_pdf():
    from weasyprint import HTML
    import datetime as dt
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io
    import base64
    from flask import make_response, render_template, request, g

    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Récupération des filtres depuis l'URL
    period = request.args.get('period', 'month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    current_cash = float(request.args.get('current_cash', 0))

    now_dt = dt.datetime.now()
    today_date = now_dt.date()

    # --- 1. Logique de filtrage de date ---
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

    # --- 2. Récupération des Ventes & KPIs ---
    cur.execute("SELECT * FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s ORDER BY sale_date ASC",
                (current_user.id, filter_start, filter_end))
    sales = cur.fetchall()

    total_revenue = sum(float(s['sale_price'] or 0) for s in sales)
    total_profit = sum(float(s['profit'] or 0) for s in sales)
    total_purchase_cost = sum(float(s['purchase_price_at_sale'] or 0) for s in sales)
    volume = len(sales)
    roi_avg = (total_profit / total_purchase_cost * 100) if total_purchase_cost > 0 else 0
    health_score = round((min(6, roi_avg / 5) if roi_avg > 0 else 0) + min(4, volume / 2), 1)

    # --- 3. Trésorerie & Stock ---
    cur.execute("SELECT COALESCE(SUM(sale_price), 0) as total FROM sales WHERE user_id = %s AND payment_status = 'en_attente'", (current_user.id,))
    pending_payments = float(cur.fetchone()['total'] or 0)

    cur.execute("SELECT SUM(purchase_price) as total_val, SUM(quantity) as total_qty FROM products WHERE user_id = %s AND quantity = 1", (current_user.id,))
    stock_info = cur.fetchone()
    valeur_achat_stock = float(stock_info['total_val'] or 0)
    stock_qty = stock_info['total_qty'] or 0
    total_base_cash = current_cash + valeur_achat_stock + pending_payments

    # --- 4. Projections & Flux ---
    cur.execute("SELECT MIN(sale_date) as first_sale, SUM(sale_price) as total_ca_all FROM sales WHERE user_id = %s", (current_user.id,))
    all_stats = cur.fetchone()
    first_date = (all_stats['first_sale'].date() if isinstance(all_stats['first_sale'], dt.datetime) else all_stats['first_sale']) if all_stats['first_sale'] else today_date
    weeks_active = max(1, (today_date - first_date).days / 7)
    avg_ca_weekly = float(all_stats['total_ca_all'] or 0) / weeks_active
    net_flow_weekly = avg_ca_weekly * 0.25
    proj_1w, proj_1m, proj_1y = total_base_cash + net_flow_weekly, total_base_cash + (net_flow_weekly * 4.3), total_base_cash + (net_flow_weekly * 52)

    # --- 5. Stock Management (Latent) ---
    cur.execute("SELECT AVG((profit / NULLIF(purchase_price_at_sale, 0)) * 100) as avg_roi_all FROM sales WHERE user_id = %s", (current_user.id,))
    avg_roi_all_time = float(cur.fetchone()['avg_roi_all'] or 20.0)
    profit_latent = valeur_achat_stock * (avg_roi_all_time / 100)
    ca_latent = valeur_achat_stock + profit_latent

    cur.execute("SELECT date_added FROM products WHERE user_id = %s AND quantity = 1", (current_user.id,))
    stock_items = cur.fetchall()
    ages = [(today_date - (i['date_added'].date() if isinstance(i['date_added'], dt.datetime) else i['date_added'])).days for i in stock_items if i['date_added']]
    stock_avg_age = int(sum(ages) / len(ages)) if ages else 0

    # --- 6. Objectifs (Calcul de référence) ---
    delta_year = dt.timedelta(days=365)
    cur.execute("SELECT SUM(sale_price) as rev, SUM(profit) as prof FROM sales WHERE user_id = %s AND sale_date >= %s AND sale_date <= %s",
                (current_user.id, filter_start - delta_year, filter_end - delta_year))
    ref_data = cur.fetchone()
    ref_rev = float(ref_data['rev'] or 0)
    ref_prof = float(ref_data['prof'] or 0)

    # --- 7. Graphique (Matplotlib) ---
    chart_url = None
    if sales:
        plt.figure(figsize=(10, 4))
        plt.style.use('dark_background')
        dates_chart = [s['sale_date'].strftime('%d/%m') for s in sales]
        revs_chart = [float(s['sale_price']) for s in sales]
        plt.plot(dates_chart, revs_chart, color='#007bff', linewidth=3, marker='o')
        plt.fill_between(dates_chart, revs_chart, alpha=0.2, color='#007bff')
        plt.axis('off') # Pour un look épuré
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', transparent=True)
        img.seek(0)
        chart_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

    # --- 8. Conseils Experts ---
    expert_proj = f"Analyse Flux : Profit net hebdomadaire estimé à {int(net_flow_weekly)}€. Capital cible à 30j : {int(proj_1m)}€."
    expert_stock = f"Rotation : Age moyen {stock_avg_age}j. Potentiel latent de {int(profit_latent)}€."

    # --- GÉNÉRATION DU PDF ---
    rendered = render_template('pdf_report_template.html',
                               today_date=today_date.strftime('%d/%m/%Y'),
                               sales=sales, revenue=total_revenue, profit=total_profit,
                               volume=volume, roi_avg=roi_avg, health_score=health_score,
                               stock_value=valeur_achat_stock, stock_qty=stock_qty,
                               period=period, profit_latent=profit_latent,
                               ca_latent=ca_latent, stock_avg_age=stock_avg_age,
                               expert_proj=expert_proj, expert_stock=expert_stock,
                               current_cash=current_cash, pending_payments=pending_payments,
                               total_base_cash=total_base_cash,
                               proj_1w=proj_1w, proj_1m=proj_1m, proj_1y=proj_1y,
                               ref_rev=ref_rev, ref_prof=ref_prof, chart_url=chart_url)

    pdf_file = HTML(string=rendered).write_pdf()
    response = make_response(pdf_file)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Rapport_{period}_{today_date}.pdf'
    return response
@app.route('/sales/<int:id>/delete', methods=('POST',))
@login_required

def delete_sale(id):
    conn = g.db
    cur = None # Initialisation du curseur

    try:
        # 1. Récupérer TOUS les détails de la vente à supprimer (y compris user_id, sale_price, et profit)
        # C'est crucial de le faire AVANT de la supprimer.
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            'SELECT user_id, product_id, quantity, sale_price, profit FROM sales WHERE id = %s AND user_id = %s',
            (id, current_user.id)
        )
        sale_details = cur.fetchone()
        cur.close()

        if sale_details is None:
            # Si la vente n'existe pas ou n'appartient pas à l'utilisateur actuel, on arrête ici.
            abort(404)

        # Stocker les valeurs nécessaires pour les mises à jour futures
        sale_user_id = sale_details['user_id']
        sale_product_id = sale_details['product_id']
        sale_quantity = sale_details['quantity']
        sale_price_to_deduct = sale_details['sale_price'] # CA de la vente à déduire
        profit_to_deduct = sale_details['profit']       # Bénéfice de la vente à déduire

        # Remettre la quantité en stock si la vente était liée à un produit
        if sale_product_id:
            cur = conn.cursor() # Nouveau curseur pour l'UPDATE product
            cur.execute('UPDATE products SET quantity = quantity + %s WHERE id = %s', (sale_quantity, sale_product_id))
            cur.close()

        # Supprimer la vente de la table 'sales'
        cur = conn.cursor() # Nouveau curseur pour le DELETE sale
        cur.execute('DELETE FROM sales WHERE id = %s AND user_id = %s', (id, current_user.id))
        cur.close()

        # 2. Mettre à jour (décrémenter) les totaux dans la table classement_utilisateurs
        cur = conn.cursor() # Nouveau curseur pour l'UPDATE classement_utilisateurs
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
        cur.close() # Ferme le curseur après l'opération

        conn.commit() # Valide toutes les modifications dans la base de données
        flash('Vente supprimée avec succès et classement mis à jour !', 'success')
        return redirect(url_for('sales'))

    except Exception as e:
        conn.rollback() # Annuler toutes les modifications en cas d'erreur
        flash(f"Une erreur est survenue lors de la suppression de la vente : {e}", 'danger')
        print(f"Erreur suppression vente: {e}")
        return redirect(url_for('sales'))
    finally:
        # Le finally n'a plus besoin de fermer le curseur si chaque curseur est fermé juste après son usage,
        # comme c'est le cas dans cette révision.
        pass
@app.route('/supplementary_operations', methods=('GET',))
@login_required
def supplementary_operations():
    conn = g.db
    operations = []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # La requête est maintenant correcte, elle utilise les colonnes de votre table.
        cur.execute(
            'SELECT id, type, amount, description, operation_date FROM supplementary_operations WHERE user_id = %s ORDER BY operation_date DESC LIMIT 10',
            (current_user.id,)
        )
        operations = cur.fetchall()
        cur.close()
    except Exception as e:
        flash(f"Erreur lors du chargement des opérations supplémentaires : {e}", "danger")
        print(f"DEBUG: Erreur de chargement opérations supplémentaires : {e}")

    return render_template('supplementary_operations.html', operations=operations)


@app.route('/add_supplementary_operation', methods=('GET', 'POST'))
@login_required
def add_supplementary_operation():
    # La ligne ci-dessous est corrigée pour récupérer 'type' des données POST du formulaire.
    operation_type = request.form.get('type')

    if operation_type not in ['charge', 'bonus']:
        flash("Type d'opération non valide.", "danger")
        return redirect(url_for('supplementary_operations'))

    amount = request.form.get('amount', '').replace(',', '.')
    description = request.form.get('description', '').strip()
    operation_date = request.form.get('operation_date', datetime.now().strftime('%Y-%m-%d'))

    if request.method == 'POST':
        error = None

        if not amount or not amount.replace('.', '', 1).isdigit() or float(amount) <= 0:
            error = 'Le montant est obligatoire et doit être un nombre positif !'
        elif not operation_date:
            error = 'La date de l\'opération est obligatoire !'

        if error is None:
            conn = g.db
            try:
                amount_float = float(amount)

                cur = conn.cursor()
                cur.execute(
                    'INSERT INTO supplementary_operations (user_id, type, amount, description, operation_date) VALUES (%s, %s, %s, %s, %s)',
                    (current_user.id, operation_type, amount_float, description, operation_date)
                )
                conn.commit()
                flash(f'Opération ({operation_type}) enregistrée avec succès !', 'success')
                return redirect(url_for('supplementary_operations'))

            except Exception as e:
                conn.rollback()
                flash(f'Une erreur est survenue lors de l\'enregistrement de l\'opération : {e}', "danger")
                print(f"DEBUG: Erreur d'enregistrement opération supplémentaire : {e}")
            finally:
                if cur and not cur.closed:
                    cur.close()
        else:
            flash(error, 'danger')

    # Si c'est un GET ou qu'il y a une erreur POST, afficher le formulaire
    return render_template('add_supplementary_operation.html',
                           operation_type=operation_type,
                           amount=amount,
                           description=description,
                           operation_date=operation_date)
# --- Route Flask /generate_test_report (Modifiée pour la semaine actuelle) ---
@app.route('/generate_test_report', methods=['POST'])
@login_required
def generate_test_report():
    report_type = request.form.get('report_type')
    period_value = request.form.get('period_value') # Utilisé pour les rapports actuels (weekly/monthly)
    current_request_time = datetime.now() # Utiliser l'heure de la requête comme référence
    start_date = None
    end_date = None
    period_label = ""

    if report_type == 'weekly': # Pour la semaine COURANTE (si vous avez un bouton pour ça)
        # La semaine commence un lundi (weekday() = 0)
        days_since_monday = current_request_time.weekday()
        start_date = datetime(current_request_time.year, current_request_time.month, current_request_time.day, 0, 0, 0) - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        period_label = f"Semaine du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
    elif report_type == 'monthly': # Pour le mois COURANT (si vous avez un bouton pour ça)
        start_date = datetime(current_request_time.year, current_request_time.month, 1, 0, 0, 0)
        last_day = monthrange(current_request_time.year, current_request_time.month)[1]
        end_date = datetime(current_request_time.year, current_request_time.month, last_day, 23, 59, 59, 999999)
        period_label = f"Mois de {current_request_time.strftime('%B %Y')}"
    elif report_type == 'custom':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
            period_label = f"Période personnalisée du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
        except ValueError:
            flash("Dates invalides pour le rapport personnalisé.", 'danger')
            return redirect(url_for('report_preferences'))
    elif report_type == 'previous_weekly': # NOUVEAU : rapport pour la SEMAINE PRÉCÉDENTE
        # Calcule le dimanche de la semaine précédente
        # today.weekday() : Lundi=0, Mardi=1, ..., Dimanche=6
        # Si on est Jeudi (3), today.weekday()+1 = 4. today - timedelta(days=4) = Dimanche dernier
        # Si on est Dimanche (6), today.weekday()+1 = 7. today - timedelta(days=7) = Dimanche de la semaine d'avant
        end_date_prev_week_day = current_request_time - timedelta(days=current_request_time.weekday() + 1)
        end_date = datetime(end_date_prev_week_day.year, end_date_prev_week_day.month, end_date_prev_week_day.day, 23, 59, 59, 999999)
        start_date = datetime(end_date.year, end_date.month, end_date.day, 0, 0, 0) - timedelta(days=6) # 6 jours avant pour avoir le Lundi
        period_label = f"Semaine précédente du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
    elif report_type == 'previous_monthly': # NOUVEAU : rapport pour le MOIS PRÉCÉDENT
        # Commence par le premier jour du mois actuel
        first_day_current_month = datetime(current_request_time.year, current_request_time.month, 1)
        # Recule d'un jour pour obtenir le dernier jour du mois précédent
        end_date_prev_month_day = first_day_current_month - timedelta(days=1)
        end_date = datetime(end_date_prev_month_day.year, end_date_prev_month_day.month, end_date_prev_month_day.day, 23, 59, 59, 999999)
        # Le premier jour du mois précédent
        start_date = datetime(end_date_prev_month_day.year, end_date_prev_month_day.month, 1, 0, 0, 0)
        period_label = f"Mois précédent de {start_date.strftime('%B %Y')}"
    else:
        flash("Type de rapport non valide.", 'danger')
        return redirect(url_for('report_preferences'))

    conn = g.db
    try:
        report_id = _save_report_metadata(conn, current_user.id, report_type, period_label, start_date, end_date)
        if report_id:
            flash(f"Bilan '{period_label}' généré avec succès !", 'success')
            return redirect(url_for('view_report', report_id=report_id))
        else:
            flash("Impossible de générer le bilan.", 'danger')
            return redirect(url_for('report_preferences'))
    except Exception as e:
        flash(f"Erreur lors de la génération du bilan: {e}", 'danger')
        return redirect(url_for('report_preferences'))
@app.route('/report_preferences')
@login_required
def report_preferences():
    conn = g.db
    cur = None
    reports = [] # Initialise la liste des rapports

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Requête pour récupérer tous les rapports générés pour l'utilisateur actuel
        cur.execute("""
            SELECT id, report_type, period_label, report_start_date, report_end_date, generation_date, file_path
            FROM generated_reports
            WHERE user_id = %s
            ORDER BY generation_date DESC; -- Tri par date de génération descendante (les plus récents en premier)
        """, (current_user.id,))
        reports = cur.fetchall() # Récupère tous les résultats
    except Exception as e:
        print(f"Erreur lors de la récupération des bilans passés: {e}")
        flash("Une erreur est survenue lors du chargement des bilans passés.", 'danger')
    finally:
        if cur:
            cur.close()

    # Passe la liste des rapports au template
    return render_template('report_preferences.html', reports=reports)


@app.route('/delete_report/<int:report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    conn = g.db
    cur = None
    try:
        cur = conn.cursor()

        # Vérifier d'abord si le rapport appartient bien à l'utilisateur connecté
        cur.execute("SELECT user_id FROM generated_reports WHERE id = %s;", (report_id,))
        report_owner_result = cur.fetchone()

        if report_owner_result and report_owner_result[0] == current_user.id:
            # Si le rapport existe et appartient à l'utilisateur, on le supprime
            cur.execute("DELETE FROM generated_reports WHERE id = %s;", (report_id,))
            conn.commit()
            flash("Le bilan a été supprimé avec succès.", 'success')
        else:
            # Si le rapport n'existe pas ou n'appartient pas à l'utilisateur
            flash("Vous n'êtes pas autorisé à supprimer ce bilan ou il n'existe pas.", 'danger')
            conn.rollback()  # Annuler toute opération si non autorisé/non trouvé
    except Exception as e:
        print(f"Erreur lors de la suppression du bilan {report_id}: {e}")
        flash("Une erreur est survenue lors de la suppression du bilan.", 'danger')
        if conn:
            conn.rollback()  # Annuler la transaction en cas d'erreur
    finally:
        if cur:
            cur.close()
    return redirect(url_for('report_preferences'))  # Redirige vers la page des préférences

@app.route('/view_report/<int:report_id>')
@login_required
def view_report(report_id):
    conn = g.db
    user_id = current_user.id
    cur = None

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # 1. Fetch report metadata
        cur.execute("""
            SELECT id, report_type, period_label, report_start_date, report_end_date, generation_date, file_path
            FROM generated_reports
            WHERE id = %s AND user_id = %s;
        """, (report_id, user_id))
        report_meta = cur.fetchone()

        if not report_meta:
            flash("Bilan introuvable ou vous n'avez pas l'autorisation d'y accéder.", 'danger')
            print(f"DEBUG view_report: Bilan introuvable pour ID {report_id} ou User ID {user_id}")
            return redirect(url_for('report_preferences'))

        report_type = report_meta['report_type']
        start_date = report_meta['report_start_date']
        end_date = report_meta['report_end_date']
        period_label = report_meta['period_label']

        if not start_date or not end_date:
            flash("Impossible de déterminer la période du bilan. Les dates de début ou de fin sont manquantes.", 'danger')
            print(f"DEBUG view_report: Dates manquantes pour le rapport ID {report_id}")
            return redirect(url_for('report_preferences'))

        # 3. Get actual report data
        report_data = get_report_data(conn, user_id, start_date, end_date, report_type)

        if not report_data:
            flash("Impossible de charger les données du bilan. Il se peut qu'il n'y ait pas de données de ventes pour cette période.", 'danger')
            print(f"DEBUG view_report: get_report_data a renvoyé None pour le rapport ID {report_id}")
            return redirect(url_for('report_preferences'))

        # 4. Generate plots
        plot_sales_overview = None
        plot_stock_by_size = None
        plot_daily_sales_count = None       # NOUVEAU
        plot_daily_purchases_count = None   # NOUVEAU

        # Générer une plage de dates continues pour l'axe des X pour tous les graphiques quotidiens
        all_dates = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Préparation du graphique combiné Chiffre d'Affaires et Bénéfice
        if report_data['sales_history']:
            revenue_map = {item['period'].date(): item['revenue'] for item in report_data['sales_history']}
            profit_map = {item['period'].date(): item['profit'] for item in report_data['sales_history']}

            full_revenues = [revenue_map.get(d, decimal.Decimal(0)) for d in all_dates]
            full_profits = [profit_map.get(d, decimal.Decimal(0)) for d in all_dates]

            try:
                plot_sales_overview = create_combined_sales_plot(all_dates, full_revenues, full_profits, 'Chiffre d\'Affaires et Bénéfice par Jour')
            except Exception as plot_e:
                print(f"ERREUR LORS DE LA CRÉATION DU GRAPHIQUE COMBINÉ DES VENTES: {plot_e}")
                flash(f"Impossible de générer le graphique combiné des ventes : {plot_e}", 'warning')
        else:
             print(f"DEBUG view_report: Aucune donnée sales_history trouvée pour le rapport {report_id}.")

        # Générer le graphique en camembert pour le stock par taille
        if report_data['stock_by_size']:
            sizes = [item['size'] for item in report_data['stock_by_size']]
            counts = [item['product_count'] for item in report_data['stock_by_size']]
            try:
                plot_stock_by_size = create_pie_chart(sizes, counts, "Répartition du Stock par Taille")
            except Exception as pie_e:
                print(f"ERREUR LORS DE LA CRÉATION DU GRAPHIQUE CAMEMBERT: {pie_e}")
                flash(f"Impossible de générer le graphique de répartition du stock : {pie_e}", 'warning')
        else:
            print(f"DEBUG view_report: Aucune donnée stock_by_size trouvée pour le rapport {report_id}.")


        # NOUVEAU : Préparation des données pour le nombre de ventes (transactions) par jour
        if report_data['daily_sales_count']:
            sales_count_map = {item['period'].date(): item['sales_count'] for item in report_data['daily_sales_count']}
            full_sales_counts = [sales_count_map.get(d, 0) for d in all_dates]
            try:
                plot_daily_sales_count = create_bar_chart(all_dates, full_sales_counts, "Nombre de Ventes par Jour", "Nombre de Ventes")
            except Exception as e:
                print(f"ERREUR GRAPHIQUE VENTES QUOTIDIENNES: {e}")
                flash(f"Impossible de générer le graphique des ventes quotidiennes : {e}", 'warning')
        else:
            print(f"DEBUG view_report: Aucune donnée daily_sales_count trouvée pour le rapport {report_id}.")


        # NOUVEAU : Préparation des données pour le nombre de produits achetés (entrées en stock) par jour
        if report_data['daily_purchases_count']:
            purchases_count_map = {item['period'].date(): item['products_bought_count'] for item in report_data['daily_purchases_count']}
            full_purchases_counts = [purchases_count_map.get(d, 0) for d in all_dates]
            try:
                plot_daily_purchases_count = create_bar_chart(all_dates, full_purchases_counts, "Nombre de Produits Achetés par Jour", "Nombre de Produits")
            except Exception as e:
                print(f"ERREUR GRAPHIQUE ACHATS QUOTIDIENS: {e}")
                flash(f"Impossible de générer le graphique des achats quotidiens : {e}", 'warning')
        else:
            print(f"DEBUG view_report: Aucune donnée daily_purchases_count trouvée pour le rapport {report_id}.")


        # 5. Render template
        print(f"DEBUG view_report: Atteint le rendu du template pour le rapport ID {report_id}")
        return render_template('report_display.html',
                               report_meta=report_meta,
                               report_data=report_data,
                               plot_sales_overview=plot_sales_overview,
                               plot_stock_by_size=plot_stock_by_size,
                               plot_daily_sales_count=plot_daily_sales_count,      # NOUVEAU
                               plot_daily_purchases_count=plot_daily_purchases_count) # NOUVEAU

    except Exception as e:
        flash(f"Erreur lors de l'affichage du bilan : {e}", 'danger')
        print(f"ERREUR DANS view_report (bloc except général): {e}")
        return redirect(url_for('report_preferences'))
    finally:
        if cur and not cur.closed:
            cur.close()

from flask import Flask, render_template, send_from_directory

@app.route('/manifest.json')
def serve_manifest():
    """
    Sert le fichier manifest.json depuis la racine du projet.
    """
    return send_from_directory(app.root_path, 'manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def serve_service_worker():
    """
    Sert le fichier service-worker.js depuis la racine du projet.
    """
    return send_from_directory(app.root_path, 'service-worker.js', mimetype='application/javascript')


@app.route('/add_listing', methods=['GET', 'POST'])
@login_required
def add_listing():
    if request.method == 'POST':
        # Vérification si des fichiers ont été uploadés
        if 'photos' not in request.files:
            flash('Aucun fichier photo n\'a été sélectionné.', 'danger')
            return redirect(request.url)

        files = request.files.getlist('photos')
        image_urls = []

        if len(files) > 10:
            flash('Vous ne pouvez télécharger que 10 photos maximum.', 'danger')
            return redirect(request.url)

        for file in files:
            if file and allowed_file(file.filename):
                # Générer un nom de fichier unique pour éviter les conflits
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + '_' + filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                image_urls.append(url_for('static', filename='uploads/listings/' + unique_filename))
            elif file.filename != '':  # S'il y a un fichier mais qu'il n'est pas autorisé
                flash(f'Le fichier {file.filename} n\'est pas une image autorisée (png, jpg, jpeg, gif).', 'danger')
                return redirect(request.url)

        # Récupération des autres données du formulaire
        sku = request.form.get('sku')
        name = request.form.get('name')
        brand = request.form.get('brand')  # Récupération de la marque
        sizes = request.form.get('sizes')
        description = request.form.get('description')
        price = request.form.get('price')

        # Convertir la liste d'URLs en une chaîne séparée par des virgules pour la base de données
        image_urls_str = ','.join(image_urls)

        conn = get_db()
        cur = conn.cursor()

        try:
            # Insertion dans la nouvelle table marketplace_listings
            cur.execute("""
                INSERT INTO marketplace_listings (seller_id, sku, name, brand, sizes, description, price, image_urls)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (current_user.id, sku, name, brand, sizes, description, float(price), image_urls_str))
            conn.commit()
            flash('Votre annonce a été publiée avec succès !', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            conn.rollback()
            flash(f'Une erreur est survenue lors de la publication : {e}', 'danger')
            return redirect(url_for('add_listing'))

        finally:
            cur.close()

    return render_template('add_listing.html')


#MARKETPLACE

@app.route('/marketplace')
def marketplace():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM marketplace_listings ORDER BY date_posted DESC")
    listings = cur.fetchall()
    cur.close()

    # Convertir les données pour le rendu dans le template
    listings_list = []
    for l in listings:
        listing = dict(l)
        if isinstance(listing.get('price'), decimal.Decimal):
            listing['price'] = float(listing['price'])
        listings_list.append(listing)

    return render_template('marketplace.html', listings=listings_list)


@app.route('/listing/<int:listing_id>')
def listing_details(listing_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM marketplace_listings WHERE id = %s", (listing_id,))
    listing = cur.fetchone()
    cur.close()

    if listing:
        # Assurez-vous que le prix est un float
        if isinstance(listing.get('price'), decimal.Decimal):
            listing['price'] = float(listing['price'])

        return render_template('listing_details.html', listing=listing)
    else:
        flash("Cette annonce n'existe pas.", "danger")
        return redirect(url_for('marketplace'))


@app.route('/my_listings')
@login_required
def my_listings():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Récupérer toutes les annonces de l'utilisateur actuellement connecté
    cur.execute("SELECT * FROM marketplace_listings WHERE seller_id = %s ORDER BY date_posted DESC", (current_user.id,))
    listings = cur.fetchall()
    cur.close()

    return render_template('my_listings.html', listings=listings)
@app.route('/user_profile')
@login_required
def user_profile():
    return "<h1>Page de profil utilisateur en cours de développement...</h1>"


@app.route('/closed_requests')
@login_required
def closed_requests():
    return "<h1>Page des demandes closes en cours de construction...</h1>"

# Route pour la page "Ventes conclues"
@app.route('/sales_history')
@login_required
def sales_history():
    return "<h1>Page de l'historique des ventes en cours de construction...</h1>"


@app.route('/send_request', methods=['POST'])
def send_request():
    try:
        # Récupérer les données du formulaire
        listing_id = request.form.get('listing_id')
        client_name = request.form.get('name')
        client_email = request.form.get('email')
        client_phone = request.form.get('phone_number', '')
        offer_price_str = request.form.get('offer_price', '')
        client_message = request.form.get('message')

        # Récupérer les informations de l'annonce et du vendeur
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT seller_id FROM marketplace_listings WHERE id = %s", (listing_id,))
        listing = cur.fetchone()

        if not listing:
            cur.close()
            flash('Annonce non trouvée.', 'danger')
            return redirect(url_for('marketplace'))

        seller_id = listing['seller_id']

        # Gérer l'offre de prix
        offer_price = None
        if offer_price_str:
            try:
                offer_price = float(offer_price_str)
            except ValueError:
                pass  # Laisse le prix à None si la conversion échoue

        # Insertion de la demande dans la nouvelle table
        cur.execute("""
            INSERT INTO marketplace_requests 
            (listing_id, seller_id, client_name, client_email, client_phone, offer_price, client_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (listing_id, seller_id, client_name, client_email, client_phone, offer_price, client_message))

        conn.commit()
        cur.close()

        # Redirige le client vers la page de succès au lieu de l'annonce
        return redirect(url_for('request_success'))

    except Exception as e:
        conn.rollback()
        flash('Erreur lors de l\'envoi de votre demande. Veuillez réessayer plus tard.', 'danger')
        print(f"Erreur d'enregistrement de demande: {e}")

        # En cas d'erreur, on redirige toujours vers la page de l'annonce
        return redirect(url_for('listing_details', listing_id=listing_id))

# Route pour afficher toutes les demandes en cours du vendeur connecté
@app.route('/pending_requests')
@login_required
def pending_requests():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT mr.*, ml.name as listing_name
        FROM marketplace_requests mr
        JOIN marketplace_listings ml ON mr.listing_id = ml.id
        WHERE mr.seller_id = %s AND mr.status = 'en_attente'
        ORDER BY mr.request_date DESC
    """, (current_user.id,))
    requests = cur.fetchall()
    cur.close()
    return render_template('pending_requests.html', requests=requests)


@app.route('/request/<int:request_id>')
@login_required
def request_details_json(request_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT mr.*, ml.name as listing_name, ml.brand as listing_brand, ml.price as listing_price
        FROM marketplace_requests mr
        JOIN marketplace_listings ml ON mr.listing_id = ml.id
        WHERE mr.id = %s AND mr.seller_id = %s
    """, (request_id, current_user.id))
    request_data = cur.fetchone()
    cur.close()

    if not request_data:
        # Retourne une erreur 404 si la demande n'existe pas ou n'appartient pas à l'utilisateur
        return jsonify({"error": "Demande non trouvée ou non autorisée"}), 404

    # Convertir les objets Decimal et datetime en types serialisables
    request_data['offer_price'] = float(request_data['offer_price']) if request_data[
                                                                            'offer_price'] is not None else None
    request_data['request_date'] = request_data['request_date'].isoformat()

    return jsonify(request_data)

@app.route('/request_success')
def request_success():
    return render_template('request_success.html')

# Route pour afficher toutes les annonces d'un seul vendeur
@app.route('/seller_profile/<int:seller_id>')
def seller_profile(seller_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Récupérer les informations du vendeur
    cur.execute("SELECT name FROM users WHERE id = %s", (seller_id,))
    seller = cur.fetchone()

    if not seller:
        cur.close()
        flash("Vendeur non trouvé.", "danger")
        return redirect(url_for('marketplace'))

    # Récupérer toutes les annonces du vendeur
    cur.execute("SELECT * FROM marketplace_listings WHERE seller_id = %s ORDER BY date_posted DESC", (seller_id,))
    listings = cur.fetchall()
    cur.close()

    # Rendre le template avec le nom du vendeur et ses annonces
    return render_template('seller_profile.html', seller=seller, listings=listings)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Route pour supprimer une annonce
@app.route('/delete_listing/<int:listing_id>', methods=['POST'])
@login_required
def delete_listing(listing_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # Vérifier si l'utilisateur est le propriétaire de l'annonce
        cur.execute("SELECT seller_id FROM marketplace_listings WHERE id = %s", (listing_id,))
        listing = cur.fetchone()

        if not listing:
            cur.close()
            return jsonify({'success': False, 'message': 'Annonce non trouvée.'})

        if listing[0] != current_user.id:
            cur.close()
            return jsonify({'success': False, 'message': 'Action non autorisée.'}), 403

        # Supprimer l'annonce de la base de données
        cur.execute("DELETE FROM marketplace_listings WHERE id = %s", (listing_id,))
        conn.commit()
        cur.close()

        return jsonify({'success': True, 'message': 'Annonce supprimée avec succès.'})

    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de la suppression de l'annonce : {e}")
        return jsonify({'success': False, 'message': 'Erreur interne du serveur.'}), 500

@app.route('/offline.html')
def offline_page():
    # Si offline.html est dans le dossier 'templates':
    return render_template('offline.html')
    # Si offline.html est à la racine de votre projet Flask:
    # return send_from_directory(app.root_path, 'offline.html')

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
    # --- MODIFICATIONS NÉCESSAIRES ICI ---

    # 1. Supprimez ou commentez cette section qui vérifie le fichier SQLite
    # db_path = os.path.join(PROJECT_ROOT, 'database.db')
    # if not os.path.exists(db_path):
    #     print(f"Base de données '{db_path}' non trouvée. Initialisation...")
    #     with app.app_context():
    #         init_db()
    # else:
    #     print(f"Base de données '{db_path}' trouvée. Utilisation de la base existante.")


    # 2. Appelez toujours init_db() dans le contexte de l'application
    #    Cela va créer les tables PostgreSQL si elles n'existent pas
    #    (grâce à 'CREATE TABLE IF NOT EXISTS' dans init_db)
    #    Vous pouvez le laisser comme ça pour le développement.
    #    Pour la production, la commande 'flask init-db' est préférable.
    with app.app_context():
        print("Initialisation/Vérification du schéma PostgreSQL...")
        init_db()

    # 3. Assurez-vous d'avoir bien enlevé toutes les références à 'sqlite3'
    #    et que votre fonction 'get_db()' utilise bien 'psycopg2' et 'DATABASE_URL'.
    #    (Comme discuté précédemment)

    app.run(debug=False, port=8000)