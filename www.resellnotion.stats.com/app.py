import os
import decimal
import psycopg2 # Importez psycopg2
import psycopg2.extras # Pour RealDictCursor
from urllib.parse import urlparse # Pour parser l'URL de la DB
from datetime import datetime, timedelta
from functools import wraps
from flask_login import login_required, current_user
from flask import Flask, render_template, request, url_for, flash, redirect, session, current_app, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import calendar
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, g # Importez jsonify ici
from functools import wraps # Importez wraps pour le décorateur
from decimal import Decimal
import matplotlib
import matplotlib.dates as mdates # Assurez-vous d'avoir cet import
matplotlib.use('Agg') # Important: Utilisez le backend 'Agg' pour la génération d'images non-interactives
import matplotlib.pyplot as plt
import io
import base64
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta

from dateutil.relativedelta import relativedelta
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

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, '..', 'www.resellnotion.stats.com', 'assets')

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
@login_required # Ajoutez cette ligne si vous voulez que les suggestions soient disponibles uniquement pour les utilisateurs connectés
def get_sku_suggestions():
    query = request.args.get('query', '').upper()
    suggestions = []
    if query:
        count = 0
        for item in SKU_DATA:
            # Vérifie si le query est contenu dans le SKU (insensible à la casse)
            # ou dans le nom du produit (insensible à la casse)
            if query in item['sku'].upper() or query in item['product_name'].upper(): #
                suggestions.append({
                    'sku': item['sku'],
                    'image_url': item['image_url'],
                    'product_name': item['product_name'] # Ajout du nom du produit
                })
                count += 1
                if count >= 10: # Limite à 10 suggestions pour de meilleures performances
                    break
    return jsonify(suggestions)


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
@key_active_required
def dashboard():
    conn = g.db
    cur = None

    try:
        # Calcul du nombre de produits en stock
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(quantity) FROM products WHERE user_id = %s",
                               (current_user.id,))
        products_in_stock_query = cur.fetchone()
        products_in_stock = products_in_stock_query['sum'] if products_in_stock_query and products_in_stock_query['sum'] is not None else 0
        cur.close()

        # Calcul de la valeur totale du stock (Prix d'achat * Quantité pour tous les produits)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(purchase_price * quantity) FROM products WHERE user_id = %s",
                                      (current_user.id,))
        total_stock_value_query = cur.fetchone()
        # MODIFICATION ICI : Utiliser Decimal('0.00') au lieu de 0.0
        total_stock_value = total_stock_value_query['sum'] if total_stock_value_query and total_stock_value_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # Calcul du bénéfice total des ventes
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT SUM(profit) FROM sales WHERE user_id = %s",
            (current_user.id,))
        total_sales_profit_query = cur.fetchone()
        # MODIFICATION ICI : Utiliser Decimal('0.00') au lieu de 0.0
        total_sales_profit = total_sales_profit_query['sum'] if total_sales_profit_query and total_sales_profit_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # Calcul du chiffre d'affaires total (Somme de tous les prix de vente)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT SUM(sale_price) FROM sales WHERE user_id = %s",
                                   (current_user.id,))
        total_revenue_query = cur.fetchone()
        # MODIFICATION ICI : Utiliser Decimal('0.00') au lieu de 0.0
        total_revenue = total_revenue_query['sum'] if total_revenue_query and total_revenue_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # --- Calcul des 'charges' et 'bonus' depuis supplementary_operations ---
        # Total des bonus
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT SUM(amount) FROM supplementary_operations WHERE user_id = %s AND type = 'bonus'",
            (current_user.id,)
        )
        total_bonus_operations_query = cur.fetchone()
        # MODIFICATION ICI : Utiliser Decimal('0.00') au lieu de 0.0
        total_bonus_operations = total_bonus_operations_query['sum'] if total_bonus_operations_query and total_bonus_operations_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # Total des charges
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT SUM(amount) FROM supplementary_operations WHERE user_id = %s AND type = 'charge'",
            (current_user.id,)
        )
        total_charge_operations_query = cur.fetchone()
        # MODIFICATION ICI : Utiliser Decimal('0.00') au lieu de 0.0
        total_charge_operations = total_charge_operations_query['sum'] if total_charge_operations_query and total_charge_operations_query['sum'] is not None else Decimal('0.00')
        cur.close()

        # --- Calcul du Résultat Net ---
        net_result = total_sales_profit + total_bonus_operations - total_charge_operations


        # Récupération des 5 dernières ventes avec toutes les données nécessaires
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''
            SELECT
                s.item_name,
                s.quantity,
                s.sale_price,
                s.sale_date,
                s.purchase_price_at_sale,
                s.shipping_cost,
                s.fees,
                s.profit,
                p.sku,
                p.size
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.id
            WHERE s.user_id = %s
            ORDER BY s.sale_date DESC
            LIMIT 5
        ''', (current_user.id,))
        latest_sales_raw = cur.fetchall()
        cur.close()

        latest_sales_for_template = []
        for sale in latest_sales_raw:
            sale_dict = dict(sale)

            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'

            # Assurez-vous que les valeurs sont des Decimals avant de les formater, ou qu'elles peuvent être converties en float pour le formatage
            # Si 'sale.profit' est déjà un Decimal, pas besoin de le modifier ici, juste s'assurer que c'est bien formatable
            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(float(sale_dict['sale_price'] or 0.0))
            sale_dict['purchase_price_at_sale_formatted'] = '{:.2f} €'.format(float(sale_dict['purchase_price_at_sale'] or 0.0))
            sale_dict['shipping_cost_formatted'] = '{:.2f} €'.format(float(sale_dict['shipping_cost'] or 0.0))
            sale_dict['fees_formatted'] = '{:.2f} €'.format(float(sale_dict['fees'] or 0.0))
            sale_dict['profit_formatted'] = '{:.2f} €'.format(float(sale_dict['profit'] or 0.0))

            latest_sales_for_template.append(sale_dict)

        return render_template('dashboard.html',
                               products_in_stock=products_in_stock,
                               total_stock_value=total_stock_value,
                               total_sales_profit=total_sales_profit,
                               total_revenue=total_revenue,
                               net_result=net_result,
                               latest_sales=latest_sales_for_template,
                               total_monthly_charges=total_charge_operations) # <-- This is the only change
    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement du tableau de bord: {e}", 'danger')
        print(f"Erreur tableau de bord: {e}")
        return redirect(url_for('login'))
    finally:
        if cur is not None and not cur.closed:
            cur.close()
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

@app.route('/products/add', methods=('GET', 'POST'))
@login_required
def add_product():
    print(f"DEBUG: Accès à /products/add. Utilisateur authentifié : {current_user.is_authenticated}")
    if current_user.is_authenticated:
        print(f"DEBUG: ID de l'utilisateur : {current_user.id}, Nom d'utilisateur : {current_user.username}")
    else:
        print("DEBUG: current_user n'est PAS authentifié malgré @login_required.")

    error = None
    form_data = {
        'sku': request.form.get('sku', ''),
        'name': request.form.get('name', ''),
        'size': request.form.get('size', ''),
        'purchase_price': request.form.get('purchase_price', ''),
        'quantity': request.form.get('quantity', ''),
        'image_url': request.form.get('image_url', ''),
        'description': request.form.get('description', '')
    }

    if request.method == 'POST':
        if not form_data['sku']:
            error = 'La référence SKU est requise !'
        elif not form_data['name']:
            error = 'Le nom est requis !'
        elif not form_data['purchase_price'] or not (form_data['purchase_price'].replace('.', '', 1).isdigit()):
            error = 'Le prix d\'achat est requis et doit être un nombre valide !'
        elif not form_data['quantity'] or not form_data['quantity'].isdigit() or int(form_data['quantity']) <= 0:
            error = 'La quantité doit être un nombre entier positif !'

        if error is None:
            conn = g.db
            cur = None # Initialisation du curseur

            try:
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                purchase_price_float = float(form_data['purchase_price'])
                quantity_int = int(form_data['quantity'])
                selling_price_float = purchase_price_float

                cur = conn.cursor() # Crée un curseur pour l'insertion
                cur.execute(
                    'INSERT INTO products (user_id, sku, name, size, purchase_price, quantity, price, description, image_url, date_added) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', # Placeholders %s
                    (current_user.id,
                     form_data['sku'], form_data['name'], form_data['size'],
                     purchase_price_float, quantity_int, selling_price_float, form_data['description'],
                     form_data['image_url'],
                     current_date)
                )
                conn.commit()
                flash('Produit ajouté avec succès !', 'success')
                return redirect(url_for('products'))
            except ValueError:
                conn.rollback() # Annuler la transaction en cas d'erreur de valeur
                error = "Erreur de format pour le prix ou la quantité. Veuillez entrer des nombres valides."
                flash(error, 'danger')
            except Exception as e:
                conn.rollback() # Annuler la transaction pour toute autre erreur
                error = f'Une erreur est survenue lors de l\'ajout du produit : {e}'
                print(f"DEBUG: Erreur détaillée dans le bloc try/except : {e}")
                flash(error, 'danger')
            finally:
                if cur and not cur.closed: # S'assurer que le curseur est fermé
                    cur.close()

    display_purchase_price = form_data['purchase_price']
    if display_purchase_price:
        try:
            display_purchase_price = float(display_purchase_price)
        except ValueError:
            display_purchase_price = ''

    return render_template('add_product.html',
                           sku=form_data['sku'],
                           name=form_data['name'],
                           size=form_data['size'],
                           purchase_price=display_purchase_price,
                           quantity=form_data['quantity'],
                           image_url=form_data['image_url'],
                           description=form_data['description'],
                           error=error)

@app.route('/products/<int:id>/edit', methods=('GET', 'POST'))
@login_required
@key_active_required
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
@key_active_required
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


@app.route('/sales/add', methods=('GET', 'POST'))
@login_required
@key_active_required
def add_sale():
    conn = g.db
    cur = None

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            'SELECT id, name, sku, size, quantity, purchase_price FROM products WHERE user_id = %s AND quantity > 0 ORDER BY name',
            (current_user.id,))
        products_for_dropdown = cur.fetchall()
        cur.close()
    except Exception as e:
        flash(f"Erreur lors du chargement des produits pour la vente : {e}", "danger")
        print(f"DEBUG: Erreur de chargement produits_for_dropdown : {e}")
        products_for_dropdown = []

    form_data = {
        'product_id': request.form.get('product_id', ''),
        'item_name': request.form.get('item_name', '').strip(),
        'quantity': request.form.get('quantity', 1),
        'sale_price': request.form.get('sale_price', '').replace(',', '.'),
        'sale_date': request.form.get('sale_date', datetime.now().strftime('%Y-%m-%d')),
        'platform': request.form.get('platform', '').strip(),
        'shipping_cost': request.form.get('shipping_cost', '').replace(',', '.'),
        'fees': request.form.get('fees', '').replace(',', '.'),
        'notes': request.form.get('notes', '').strip()
    }

    if request.method == 'POST':
        product_id = form_data['product_id'] if form_data['product_id'] else None
        item_name = form_data['item_name']
        quantity_sold_str = str(form_data['quantity'])
        sale_price_str = form_data['sale_price']
        sale_date = form_data['sale_date']
        notes = form_data['notes']
        platform = form_data['platform']
        shipping_cost_str = form_data['shipping_cost']
        fees_str = form_data['fees']

        error = None

        if not item_name and not product_id:
            error = 'Veuillez saisir le nom de l\'article vendu ou sélectionner un produit existant.'
        elif not quantity_sold_str.isdigit() or int(quantity_sold_str) <= 0:
            error = 'La quantité vendue est requise et doit être un nombre entier positif !'
        elif not sale_price_str or not (sale_price_str.replace('.', '', 1).isdigit()):
            error = 'Le prix de vente est requis et doit être un nombre valide !'
        elif not sale_date:
            error = 'La date de vente est requise !'
        if shipping_cost_str and not shipping_cost_str.replace('.', '', 1).isdigit():
            error = 'Les frais de port doivent être un nombre valide.'
        if fees_str and not fees_str.replace('.', '', 1).isdigit():
            error = 'Les frais de plateforme/commission doivent être un nombre valide.'

        if error is None:
            conn = g.db
            try:
                quantity_sold = int(quantity_sold_str)
                sale_price_float = float(sale_price_str)
                shipping_cost_float = float(shipping_cost_str) if shipping_cost_str else 0.0
                fees_float = float(fees_str) if fees_str else 0.0

                purchase_price_at_sale = 0.0
                if product_id:
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute(
                        'SELECT purchase_price FROM products WHERE id = %s AND user_id = %s',
                        (product_id, current_user.id))
                    product_data_for_sale = cur.fetchone()
                    cur.close()
                    if product_data_for_sale:
                        purchase_price_at_sale = float(product_data_for_sale['purchase_price'])

                # Calcul du bénéfice par vente (profit) et du chiffre d'affaires (CA) de cette vente
                # Le profit est déjà calculé
                profit = sale_price_float - purchase_price_at_sale - shipping_cost_float - fees_float

                # Le CA pour cette vente est simplement le prix de vente
                # Si tu veux inclure les frais de port dans le CA, tu peux faire:
                # sale_ca = sale_price_float + shipping_cost_float
                # Pour l'instant, je considère le CA comme le prix de vente du produit
                sale_ca = sale_price_float

                cur = conn.cursor()
                # MODIFICATION ESSENTIELLE ICI : Ajout de RETURNING id pour récupérer l'ID de la nouvelle vente
                cur.execute(
                    'INSERT INTO sales (user_id, product_id, item_name, quantity, sale_price, purchase_price_at_sale, sale_date, notes, sale_channel, shipping_cost, fees, profit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                    (current_user.id, product_id, item_name, quantity_sold, sale_price_float, purchase_price_at_sale,
                     sale_date, notes, platform, shipping_cost_float, fees_float, profit)
                )
                new_sale_id = cur.fetchone()[0]  # Récupère l'ID de la vente nouvellement insérée
                cur.close()

                if product_id:
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute('SELECT quantity FROM products WHERE id = %s AND user_id = %s',
                                (product_id, current_user.id))
                    product_data = cur.fetchone()
                    cur.close()

                    if product_data:
                        current_product_quantity = product_data['quantity']
                        new_quantity = current_product_quantity - quantity_sold

                        cur = conn.cursor()
                        cur.execute('UPDATE products SET quantity = %s WHERE id = %s', (new_quantity, product_id))
                        cur.close()

                        flash(
                            f'Quantité du produit "{item_name}" mise à jour (ancien: {current_product_quantity}, nouveau: {new_quantity}).',
                            'info')
                        if new_quantity < 0:
                            flash(
                                'Attention: La quantité vendue dépasse le stock disponible. Le stock est devenu négatif.',
                                'warning')
                        elif new_quantity == 0:
                            flash(f'Le produit "{item_name}" est maintenant en rupture de stock.', 'info')
                    else:
                        flash(
                            'Avertissement: Le produit lié à la vente n\'a pas été trouvé pour la mise à jour du stock.',
                            'warning')

                # --- DÉBUT DE LA LOGIQUE D'INTÉGRATION DU CLASSEMENT ---
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO classement_utilisateurs (user_id, total_ca, total_benefice, last_updated)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        total_ca = classement_utilisateurs.total_ca + EXCLUDED.total_ca,
                        total_benefice = classement_utilisateurs.total_benefice + EXCLUDED.total_benefice,
                        last_updated = NOW();
                    """,
                    (current_user.id, sale_ca, profit)
                    # Utilise current_user.id, le CA de la vente et le profit de la vente
                )
                cur.close()
                # --- FIN DE LA LOGIQUE D'INTÉGRATION DU CLASSEMENT ---

                conn.commit()
                # MODIFICATION ESSENTIELLE ICI : Redirection vers la nouvelle page de succès
                return redirect(url_for('sale_success', sale_id=new_sale_id))

            except ValueError:
                conn.rollback()
                error = "Erreur de format pour les montants ou la quantité. Veuillez entrer des nombres valides."
                flash(error, 'danger')
            except Exception as e:
                conn.rollback()
                error = f'Une erreur est survenue lors de l\'enregistrement de la vente : {e}'
                print(f"DEBUG: Erreur détaillée lors de l'enregistrement de la vente : {e}")
                flash(error, 'danger')
            finally:
                if cur and not cur.closed:
                    cur.close()
        else:
            flash(error, 'danger')

    display_sale_price = '{:.2f}'.format(float(form_data['sale_price'])) if form_data['sale_price'] and form_data[
        'sale_price'].replace('.', '', 1).isdigit() else ''
    display_shipping_cost = '{:.2f}'.format(float(form_data['shipping_cost'])) if form_data['shipping_cost'] and \
                                                                                  form_data['shipping_cost'].replace(
                                                                                      '.', '', 1).isdigit() else ''
    display_fees = '{:.2f}'.format(float(form_data['fees'])) if form_data['fees'] and form_data['fees'].replace('.', '',
                                                                                                                1).isdigit() else ''

    return render_template('add_sale.html',
                           products=products_for_dropdown,
                           sale={
                               'product_id': form_data['product_id'],
                               'item_name': form_data['item_name'],
                               'quantity': form_data['quantity'],
                               'sale_price': display_sale_price,
                               'sale_date': form_data['sale_date'],
                               'platform': form_data['platform'],
                               'shipping_cost': display_shipping_cost,
                               'fees': display_fees,
                               'notes': form_data['notes']
                           })

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
@key_active_required
def sale_success(sale_id):
    conn = g.db
    cur = None
    sale_details = None
    product_image_url = None # Initialise à None

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Récupérer les détails de la vente et l'URL de l'image du produit si disponible
        cur.execute('''
            SELECT
                s.item_name,
                s.sale_price,
                s.purchase_price_at_sale,
                s.shipping_cost,
                s.fees,
                s.profit,
                p.image_url,
                p.sku,
                p.size
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.id
            WHERE s.id = %s AND s.user_id = %s
        ''', (sale_id, current_user.id))
        sale_details = cur.fetchone()
        cur.close()

        if sale_details:
            # Assurer que les valeurs sont au bon format pour l'affichage (float pour le formatage)
            sale_details['sale_price_formatted'] = '{:.2f}€'.format(float(sale_details['sale_price'] or 0.0))
            sale_details['purchase_price_formatted'] = '{:.2f}€'.format(float(sale_details['purchase_price_at_sale'] or 0.0))
            sale_details['profit_formatted'] = '{:+.2f}€'.format(float(sale_details['profit'] or 0.0)) # Pour afficher + ou -

            # Gérer l'URL de l'image du produit
            if sale_details['image_url']:
                product_image_url = sale_details['image_url']
            else:
                # Si pas d'image spécifique pour le produit, utiliser une image par défaut ou gérer l'absence
                product_image_url = url_for('static', filename='placeholder_product.png') # Assurez-vous d'avoir cette image par défaut

        else:
            flash("Détails de la vente introuvables.", "danger")
            return redirect(url_for('dashboard')) # Redirige si la vente n'est pas trouvée

    except Exception as e:
        flash(f"Erreur lors du chargement des détails de la vente : {e}", 'danger')
        print(f"DEBUG: Erreur de chargement sale_success : {e}")
        return redirect(url_for('dashboard'))
    finally:
        if cur is not None and not cur.closed:
            cur.close()

    return render_template('sale_success.html',
                           sale=sale_details,
                           product_image_url=product_image_url,
                           success_checkmark_url=url_for('static', filename='success_checkmark.png')) # Assurez-vous que le chemin est correct
@app.route('/sales')
@login_required
@key_active_required
def sales():
    conn = g.db
    cur = None # Initialisation du curseur

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Crée un curseur
        # Utiliser une LEFT JOIN pour récupérer les informations SKU et Taille du produit lié
        # SÉLECTIONNER MAINTENANT shipping_cost, fees et profit de la base de données
        cur.execute('''
            SELECT
                s.id,
                s.item_name,
                s.quantity,
                s.sale_price,
                s.purchase_price_at_sale,
                s.sale_date,
                s.notes,
                s.sale_channel,
                s.shipping_cost,
                s.fees,
                s.profit,
                p.sku,
                p.size
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.id
            WHERE s.user_id = %s
            ORDER BY s.sale_date DESC
        ''', (current_user.id,)) # Placeholder %s
        sales_data_raw = cur.fetchall()
        cur.close() # Ferme le curseur

        sales_for_template = []
        for sale in sales_data_raw:
            sale_dict = dict(sale)

            sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
            sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'

            sale_dict['sale_price_formatted'] = '{:.2f} €'.format(sale_dict['sale_price'] or 0.0)
            sale_dict['purchase_price_at_sale_formatted'] = '{:.2f} €'.format(sale_dict['purchase_price_at_sale'] or 0.0)
            sale_dict['shipping_cost_formatted'] = '{:.2f} €'.format(sale_dict['shipping_cost'] or 0.0)
            sale_dict['fees_formatted'] = '{:.2f} €'.format(sale_dict['fees'] or 0.0)
            sale_dict['profit_formatted'] = '{:.2f} €'.format(sale_dict['profit'] or 0.0)

            sales_for_template.append(sale_dict)

        return render_template('sales.html', sales=sales_for_template)
    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement des ventes : {e}", 'danger')
        print(f"Erreur ventes: {e}")
        return redirect(url_for('dashboard')) # Ou une page d'erreur appropriée
    finally:
        if cur and not cur.closed:
            cur.close()


@app.route('/sales/<int:id>/edit', methods=('GET', 'POST'))
@login_required
@key_active_required
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


@app.route('/statistics')
# @login_required # Décommentez si ces décorateurs sont nécessaires
# @key_active_required # Décommentez si ces décorateurs sont nécessaires
def statistics():
    conn = g.db
    user_id = current_user.id
    cur = None  # Initialisation du curseur

    selected_period = request.args.get('period', 'this_month')  # Default to 'this_month'

    today = datetime.now()

    current_start_date = None
    current_end_date = None
    previous_start_date = None
    previous_end_date = None
    graph_granularity = 'month'  # Default graph granularity

    if selected_period == 'this_week':
        current_start_date = today - timedelta(days=today.weekday())
        current_end_date = current_start_date + timedelta(days=6)
        previous_start_date = current_start_date - timedelta(days=7)
        previous_end_date = current_end_date - timedelta(days=7)
        graph_granularity = 'day'
    elif selected_period == 'last_week':
        current_start_date = today - timedelta(days=today.weekday() + 7)
        current_end_date = current_start_date + timedelta(days=6)
        previous_start_date = current_start_date - timedelta(days=7)
        previous_end_date = current_end_date - timedelta(days=7)
        graph_granularity = 'day'
    elif selected_period == 'this_month':
        current_start_date = today.replace(day=1)
        next_month_first_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        current_end_date = next_month_first_day - timedelta(days=1)
        previous_end_date = current_start_date - timedelta(days=1)
        previous_start_date = previous_end_date.replace(day=1)
        graph_granularity = 'month'
    elif selected_period == 'last_month':
        current_start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        current_end_date = today.replace(day=1) - timedelta(days=1)
        previous_end_date = current_start_date - timedelta(days=1)
        previous_start_date = previous_end_date.replace(day=1)
        graph_granularity = 'month'
    elif selected_period == 'this_year':
        current_start_date = today.replace(month=1, day=1)
        current_end_date = today.replace(month=12, day=31)
        previous_start_date = current_start_date.replace(year=current_start_date.year - 1)
        previous_end_date = current_end_date.replace(year=current_end_date.year - 1)
        graph_granularity = 'month'
    elif selected_period == 'last_year':
        current_start_date = today.replace(year=today.year - 1, month=1, day=1)
        current_end_date = today.replace(year=today.year - 1, month=12, day=31)
        previous_start_date = current_start_date.replace(year=current_start_date.year - 1)
        previous_end_date = current_end_date.replace(year=current_end_date.year - 1)
        graph_granularity = 'month'
    else:  # Fallback to 'this_month'
        current_start_date = today.replace(day=1)
        next_month_first_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        current_end_date = next_month_first_day - timedelta(days=1)
        previous_end_date = current_start_date - timedelta(days=1)
        previous_start_date = previous_end_date.replace(day=1)
        graph_granularity = 'month'

    current_start_date_str = current_start_date.strftime('%Y-%m-%d')
    current_end_date_str = current_end_date.strftime('%Y-%m-%d')
    previous_start_date_str = previous_start_date.strftime('%Y-%m-%d')
    previous_end_date_str = previous_end_date.strftime('%Y-%m-%d')

    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(id) FROM sales WHERE user_id = %s AND sale_date BETWEEN %s AND %s",
                    (user_id, current_start_date_str, current_end_date_str))
        total_sales_count_query = cur.fetchone()
        total_sales_count = total_sales_count_query[0] if total_sales_count_query and total_sales_count_query[
            0] is not None else 0
        cur.close()

        cur = conn.cursor()
        cur.execute(
            "SELECT SUM((s.sale_price - s.purchase_price_at_sale) * s.quantity) FROM sales s WHERE s.user_id = %s AND s.sale_date BETWEEN %s AND %s",
            (user_id, current_start_date_str, current_end_date_str))
        total_sales_profit_query = cur.fetchone()
        total_sales_profit = total_sales_profit_query[0] if total_sales_profit_query and total_sales_profit_query[
            0] is not None else 0.0
        cur.close()

        cur = conn.cursor()
        cur.execute(
            "SELECT SUM(s.sale_price * s.quantity) FROM sales s WHERE s.user_id = %s AND s.sale_date BETWEEN %s AND %s",
            (user_id, current_start_date_str, current_end_date_str))
        total_sales_revenue_query = cur.fetchone()
        total_sales_revenue = total_sales_revenue_query[0] if total_sales_revenue_query and total_sales_revenue_query[
            0] is not None else 0.0
        cur.close()

        cur = conn.cursor()
        cur.execute(
            "SELECT SUM(s.purchase_price_at_sale * s.quantity) FROM sales s WHERE s.user_id = %s AND s.sale_date BETWEEN %s AND %s",
            (user_id, current_start_date_str, current_end_date_str))
        total_cogs_for_sold_items_query = cur.fetchone()
        total_cogs_for_sold_items = total_cogs_for_sold_items_query[0] if total_cogs_for_sold_items_query and \
                                                                          total_cogs_for_sold_items_query[
                                                                              0] is not None else 0.0
        cur.close()

        margin_rate = 0.0
        if total_sales_revenue > 0:
            margin_rate = (total_sales_profit / total_sales_revenue) * 100

        cur = conn.cursor()
        # MODIFICATION ICI : Utilisation de (s.sale_date - p.date_added) pour PostgreSQL
        cur.execute('''
            SELECT AVG(EXTRACT(EPOCH FROM (s.sale_date - p.date_added))) / (60*60*24) AS avg_days
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE s.user_id = %s
              AND s.product_id IS NOT NULL
              AND p.date_added IS NOT NULL
              AND s.sale_date BETWEEN %s AND %s
        ''', (user_id, current_start_date_str, current_end_date_str))
        average_days_to_sell_query = cur.fetchone()
        average_days_to_sell = average_days_to_sell_query[0] if average_days_to_sell_query and \
                                                                average_days_to_sell_query[0] is not None else 0.0
        average_days_to_sell = round(average_days_to_sell, 2)
        cur.close()

        graph_labels = []
        graph_revenue_values = []
        graph_cogs_values = []
        graph_profit_values = []

        if graph_granularity == 'day':
            graph_query = '''
                SELECT
                    TO_CHAR(sale_date, 'YYYY-MM-DD') AS period_label, -- MODIFICATION ICI
                    SUM(sale_price * quantity) AS revenue,
                    SUM(purchase_price_at_sale * quantity) AS cogs,
                    SUM((sale_price - purchase_price_at_sale) * quantity) AS profit
                FROM sales
                WHERE user_id = %s AND sale_date BETWEEN %s AND %s
                GROUP BY period_label
                ORDER BY period_label
            '''
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(graph_query, (user_id, current_start_date_str, current_end_date_str))
            graph_data = cur.fetchall()
            cur.close()

            current_day_iter = current_start_date
            while current_day_iter <= current_end_date:
                day_str = current_day_iter.strftime('%Y-%m-%d')
                found_data = next((row for row in graph_data if row['period_label'] == day_str), None)

                graph_labels.append(day_str)
                graph_revenue_values.append(found_data['revenue'] if found_data else 0)
                graph_cogs_values.append(found_data['cogs'] if found_data else 0)
                graph_profit_values.append(found_data['profit'] if found_data else 0)
                current_day_iter += timedelta(days=1)
        else:  # graph_granularity == 'month'
            graph_query = '''
                SELECT
                    TO_CHAR(sale_date, 'YYYY-MM') AS period_label, -- MODIFICATION ICI
                    SUM(sale_price * quantity) AS revenue,
                    SUM(purchase_price_at_sale * quantity) AS cogs,
                    SUM((sale_price - purchase_price_at_sale) * quantity) AS profit
                FROM sales
                WHERE user_id = %s AND sale_date BETWEEN %s AND %s
                GROUP BY period_label
                ORDER BY period_label
            '''
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(graph_query, (user_id, current_start_date_str, current_end_date_str))
            graph_data = cur.fetchall()
            cur.close()

            current_month_iter = current_start_date.replace(day=1)
            while current_month_iter <= current_end_date:
                month_str = current_month_iter.strftime('%Y-%m')
                found_data = next((row for row in graph_data if row['period_label'] == month_str), None)

                month_name = calendar.month_abbr[current_month_iter.month]
                formatted_month_label = f"{month_name} {current_month_iter.year}"
                graph_labels.append(formatted_month_label)
                graph_revenue_values.append(found_data['revenue'] if found_data else 0)
                graph_cogs_values.append(found_data['cogs'] if found_data else 0)
                graph_profit_values.append(found_data['profit'] if found_data else 0)

                if current_month_iter.month == 12:
                    current_month_iter = current_month_iter.replace(year=current_month_iter.year + 1, month=1)
                else:
                    current_month_iter = current_month_iter.replace(month=current_month_iter.month + 1)

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT SUM(s.sale_price * s.quantity) AS prev_revenue, "
            "SUM(s.purchase_price_at_sale * s.quantity) AS prev_cogs, "
            "SUM((s.sale_price - s.purchase_price_at_sale) * s.quantity) AS prev_profit "
            "FROM sales s "
            "WHERE s.user_id = %s AND s.sale_date BETWEEN %s AND %s",
            (user_id, previous_start_date_str, previous_end_date_str)
        )
        previous_period_totals = cur.fetchone()
        cur.close()

        prev_total_revenue = previous_period_totals['prev_revenue'] if previous_period_totals and \
                                                                       previous_period_totals[
                                                                           'prev_revenue'] is not None else 0.0
        prev_total_cogs = previous_period_totals['prev_cogs'] if previous_period_totals and previous_period_totals[
            'prev_cogs'] is not None else 0.0
        prev_total_profit = previous_period_totals['prev_profit'] if previous_period_totals and previous_period_totals[
            'prev_profit'] is not None else 0.0

        def calculate_evolution_rate(current_value, previous_value):
            if previous_value == 0:
                if current_value > 0:
                    return 'infinity'
                else:
                    return 0.0
            return ((current_value - previous_value) / previous_value) * 100

        evolution_rate_cogs = calculate_evolution_rate(total_cogs_for_sold_items, prev_total_cogs)
        evolution_rate_revenue = calculate_evolution_rate(total_sales_revenue, prev_total_revenue)
        evolution_rate_profit = calculate_evolution_rate(total_sales_profit, prev_total_profit)

        # --- DÉBUT DU CODE MATPLOTLIB ---
        plot_base64 = None
        if total_sales_count >= 5:  # Génère le graphique uniquement s'il y a assez de données
            fig, ax = plt.subplots(figsize=(10, 6))  # Taille de la figure

            # Définir l'arrière-plan de la figure et des axes comme transparent
            fig.patch.set_alpha(0)
            ax.patch.set_alpha(0)

            # Tracé des données
            ax.plot(graph_labels, graph_cogs_values, label='Coût d\'achat', color='#FF6384', marker='o')
            ax.plot(graph_labels, graph_revenue_values, label='Prix de Vente', color='#36A2EB', marker='o')
            ax.plot(graph_labels, graph_profit_values, label='Bénéfice Net', color='#4BC0C0', marker='o')

            # Titres et étiquettes avec couleur pour le thème sombre
            ax.set_title('Évolution des Ventes et Bénéfices (Période Actuelle)', color='#f8f9fa')
            ax.set_xlabel('Jour' if graph_granularity == 'day' else 'Mois', color='#f8f9fa')
            ax.set_ylabel('Montant (€)', color='#f8f9fa')

            # Couleur des ticks des axes
            ax.tick_params(axis='x', colors='#f8f9fa')
            ax.tick_params(axis='y', colors='#f8f9fa')

            # Lignes de grille
            ax.grid(True, color='#333', linestyle='--')

            # Légende
            # facecolor='transparent' pour le fond transparent de la légende
            # edgecolor='none' pour pas de bordure
            # labelcolor='white' pour la couleur du texte de la légende
            ax.legend(facecolor='transparent', edgecolor='none', labelcolor='white')

            # Formatage de l'axe Y en monnaie
            import matplotlib.ticker as mticker
            formatter = mticker.FormatStrFormatter(
                '%d€')  # Format entier pour l'exemple, ajustez si besoin (ex: '%.2f€' pour 2 décimales)
            ax.yaxis.set_major_formatter(formatter)

            plt.tight_layout()  # Ajuster la mise en page pour éviter les chevauchements

            # Sauvegardez le graphique dans un objet BytesIO (en mémoire)
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', transparent=True)
            buffer.seek(0)  # Remettre le curseur au début du buffer

            # Encodez le contenu du buffer en base64
            plot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            plt.close(fig)  # Fermez la figure pour libérer la mémoire
        # --- FIN DU CODE MATPLOTLIB ---

        return render_template('statistics.html',
                               total_sales_count=total_sales_count,
                               total_sales_profit=total_sales_profit,
                               total_sales_revenue=total_sales_revenue,
                               margin_rate=margin_rate,
                               average_days_to_sell=average_days_to_sell,
                               selected_period=selected_period,

                               graph_labels=graph_labels,
                               graph_revenue_values=graph_revenue_values,
                               graph_cogs_values=graph_cogs_values,
                               graph_profit_values=graph_profit_values,
                               graph_granularity=graph_granularity,

                               evolution_rate_cogs=evolution_rate_cogs,
                               evolution_rate_revenue=evolution_rate_revenue,
                               evolution_rate_profit=evolution_rate_profit,
                               plot_base64=plot_base64  # Passez l'image encodée au template
                               )
    except Exception as e:
        flash(f"Une erreur est survenue lors du chargement des statistiques : {e}", 'danger')
        print(f"Erreur statistiques: {e}")
        return redirect(url_for('dashboard'))  # Redirige vers le tableau de bord ou une page d'erreur
    finally:
        if cur and not cur.closed:  # S'assurer que le curseur est fermé
            cur.close()
# --- Nouvelle fonction pour sauvegarder un rapport (utilisée par la tâche planifiée plus tard) ---
import json  # Toujours nécessaire si vous gérez d'autres JSON ailleurs, mais pas pour le rapport_json_data
from datetime import datetime, date


# Fonction utilitaire pour gérer les valeurs 'infinity'

# --- Nouvelle route (pour les tests manuels seulement) pour générer un rapport ---
# Plus tard, cette logique sera déplacée vers une tâche planifiée.


@app.route('/sales/<int:id>/delete', methods=('POST',))
@login_required
@key_active_required
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
@key_active_required
def supplementary_operations():
    conn = g.db
    operations = []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            'SELECT id, type, amount, description, operation_date FROM supplementary_operations WHERE user_id = %s ORDER BY operation_date DESC, created_at DESC LIMIT 10',
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
@key_active_required
def add_supplementary_operation():
    operation_type = request.args.get('type') # Récupère le type ('charge' ou 'bonus') de l'URL
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
                amount_float = float(amount) # Convertir en float pour l'insertion si la colonne est numeric/decimal

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
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def init_db():
    conn = get_db()
    cur = conn.cursor()
    try:
        # Suppression des tables existantes (avec CASCADE pour gérer les dépendances)
        #cur.execute("DROP TABLE IF EXISTS sales CASCADE;")
        #cur.execute("DROP TABLE IF EXISTS products CASCADE;")
        #cur.execute("DROP TABLE IF EXISTS users CASCADE;")

        # Table pour les utilisateurs
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                avatar_url TEXT,
                is_admin BOOLEAN DEFAULT FALSE, -- Converti INTEGER DEFAULT 0 en BOOLEAN
                discord_id VARCHAR(255) UNIQUE,
                key_status VARCHAR(20) DEFAULT 'inactive' NOT NULL CHECK(key_status IN ('active', 'inactive')),
                key_start_date TIMESTAMP, -- Ajout des colonnes de date pour la clé, si absentes de votre schéma d'origine mais implicites dans les fonctions
                key_end_date TIMESTAMP    -- Ajout des colonnes de date pour la clé
            );
        ''')

        # Table pour les produits
        cur.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                sku VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                size VARCHAR(255),
                purchase_price NUMERIC(10, 2) NOT NULL, -- Converti REAL en NUMERIC pour la précision
                quantity INTEGER NOT NULL,
                price NUMERIC(10, 2), -- Converti REAL en NUMERIC
                description TEXT,
                image_url TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL -- Converti TEXT en TIMESTAMP
            );
        ''')

        # Table pour les ventes
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                item_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                sale_price NUMERIC(10, 2) NOT NULL, -- Converti REAL en NUMERIC
                purchase_price_at_sale NUMERIC(10, 2), -- Converti REAL en NUMERIC
                sale_date TIMESTAMP NOT NULL, -- Converti TEXT en TIMESTAMP
                notes TEXT,
                sale_channel VARCHAR(255),
                shipping_cost NUMERIC(10, 2) DEFAULT 0.0, -- Converti REAL en NUMERIC
                fees NUMERIC(10, 2) DEFAULT 0.0,          -- Converti REAL en NUMERIC
                profit NUMERIC(10, 2) DEFAULT 0.0         -- Converti REAL en NUMERIC
            );
        ''')

        # Ajout des index pour de meilleures performances sur les clés étrangères
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users (discord_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_user_id ON products (user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales (user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_product_id ON sales (product_id);")

        conn.commit()
        print("Schéma de base de données PostgreSQL initialisé avec succès.")
    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'initialisation de la base de données PostgreSQL : {e}")
    finally:
        cur.close()

# ... (votre code app.py existant) ...

# ... (votre code app.py existant) ...

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

    app.run(debug=True, port=8000)