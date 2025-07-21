import os
import sqlite3
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


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session dure 7 jours

bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.needs_refresh_message = "Votre session a expiré, veuillez vous reconnecter."
login_manager.needs_refresh_message_category = "info"

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

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
        conn = get_db_connection()
        user_data = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
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


# --- Configuration de la base de données ---
DATABASE_PATH = 'database.db'


# --- Fonction de connexion à la base de données ---
def get_db_connection():
    # MODIFICATION ICI : Utilisez PROJECT_ROOT et le nom 'database.db'
    db = sqlite3.connect(
        os.path.join(PROJECT_ROOT, 'database.db'), # <-- Changement ici
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    db.row_factory = sqlite3.Row
    return db


# --- Initialisation de la base de données ---
def init_db():
    db = get_db_connection()
    # CETTE LIGNE EST CRUCIALE ! Assurez-vous d'avoir 'mode='r', encoding='utf-8''
    with current_app.open_resource('schema.sql', mode='r', encoding='utf-8') as f:
        db.cursor().executescript(f.read())
    db.commit() # Très important : assurez-vous que cette ligne est présente pour sauvegarder les changements
    db.close() # Fermer la connexion
    print("Base de données initialisée à partir de schema.sql.")







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
SKU_FILE_PATH = r'C:\Users\bidar\PycharmProjects\resell notion stat\sku_img_with_name.json' # Utilisez r'' pour les chemins Windows

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

        # Vérification si l'utilisateur existe déjà
        conn = get_db_connection()
        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if existing_user:
            flash("Cet email est déjà enregistré. Veuillez en utiliser un autre ou vous connecter.", "danger")
            return render_template('register.html', email=email, username=username)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        conn.execute("INSERT INTO users (email, password_hash, username) VALUES (?, ?, ?)",
                     (email, hashed_password, username))
        conn.commit()
        conn.close()
        flash("Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for('login'))
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

        conn = get_db_connection()
        user_data = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

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

@app.route('/')
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def dashboard():
    conn = get_db_connection()

    # Calcul du nombre de produits en stock
    products_in_stock_query = conn.execute("SELECT SUM(quantity) FROM products WHERE user_id = ?",
                                           (current_user.id,)).fetchone()
    products_in_stock = products_in_stock_query[0] if products_in_stock_query and products_in_stock_query[0] is not None else 0

    # Calcul de la valeur totale du stock (Prix d'achat * Quantité pour tous les produits)
    total_stock_value_query = conn.execute("SELECT SUM(purchase_price * quantity) FROM products WHERE user_id = ?",
                                          (current_user.id,)).fetchone()
    total_stock_value = total_stock_value_query[0] if total_stock_value_query and total_stock_value_query[0] is not None else 0.0

    # Calcul du bénéfice total des ventes
    total_sales_profit_query = conn.execute(
        "SELECT SUM(profit) FROM sales WHERE user_id = ?",
        (current_user.id,)).fetchone()
    total_sales_profit = total_sales_profit_query[0] if total_sales_profit_query and total_sales_profit_query[0] is not None else 0.0

    # Calcul du chiffre d'affaires total (Somme de tous les prix de vente)
    total_revenue_query = conn.execute("SELECT SUM(sale_price) FROM sales WHERE user_id = ?",
                                       (current_user.id,)).fetchone()
    total_revenue = total_revenue_query[0] if total_revenue_query and total_revenue_query[0] is not None else 0.0

    # Récupération des 5 dernières ventes avec toutes les données nécessaires
    latest_sales_raw = conn.execute('''
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
        WHERE s.user_id = ?
        ORDER BY s.sale_date DESC
        LIMIT 5
    ''', (current_user.id,)).fetchall()

    latest_sales_for_template = []
    for sale in latest_sales_raw:
        sale_dict = dict(sale)

        sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
        sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'

        sale_dict['sale_price_formatted'] = '{:.2f} €'.format(sale_dict['sale_price'] or 0.0)
        sale_dict['purchase_price_at_sale_formatted'] = '{:.2f} €'.format(sale_dict['purchase_price_at_sale'] or 0.0)
        sale_dict['shipping_cost_formatted'] = '{:.2f} €'.format(sale_dict['shipping_cost'] or 0.0)
        sale_dict['fees_formatted'] = '{:.2f} €'.format(sale_dict['fees'] or 0.0)
        sale_dict['profit_formatted'] = '{:.2f} €'.format(sale_dict['profit'] or 0.0)

        latest_sales_for_template.append(sale_dict)

    conn.close()
    return render_template('dashboard.html',
                           products_in_stock=products_in_stock,
                           total_stock_value=total_stock_value,  # Passer la nouvelle variable
                           total_sales_profit=total_sales_profit,
                           total_revenue=total_revenue,        # Passer la nouvelle variable
                           latest_sales=latest_sales_for_template)
@app.route('/profile', methods=('GET', 'POST'))
# NOUVELLE ROUTE : Page de profil utilisateur pour gérer l'ID Discord
@app.route('/profile', methods=['GET', 'POST'])
@login_required  # L'utilisateur doit être connecté pour accéder à cette page
def profile():
    conn = get_db_connection()
    # Nous allons récupérer les données directement depuis current_user pour le template
    # et pour l'update, nous utiliserons l'ID de current_user.

    if request.method == 'POST':
        # Récupérer les données du formulaire
        new_username = request.form.get('username')
        new_discord_id = request.form.get('discord_id')

        # Validation basique (ajoutez-en plus si nécessaire)
        if not new_username:
            flash("Le nom d'utilisateur ne peut pas être vide.", "danger")
            conn.close()
            return render_template('profile.html', user=current_user)

        try:
            # Mettre à jour les détails de l'utilisateur dans la base de données
            conn.execute(
                "UPDATE users SET username = ?, discord_id = ? WHERE id = ?",
                (new_username, new_discord_id, current_user.id)
            )
            conn.commit()
            conn.close()

            # Mettre à jour l'objet current_user en session pour refléter immédiatement les changements
            # Flask-Login rechargera l'utilisateur depuis la DB sur les requêtes suivantes,
            # mais c'est bien d'avoir la donnée à jour tout de suite.
            current_user.username = new_username
            current_user.discord_id = new_discord_id

            flash("Votre profil a été mis à jour avec succès !", "success")
            return redirect(url_for('profile'))  # Rediriger vers la requête GET pour afficher les données mises à jour
        except sqlite3.IntegrityError as e:
            conn.close()
            # Gérer l'erreur si l'ID Discord est déjà utilisé (car il est UNIQUE)
            if "UNIQUE constraint failed: users.discord_id" in str(e):
                flash("Cet ID Discord est déjà utilisé par un autre compte.", "danger")
            else:
                flash("Une erreur est survenue lors de la mise à jour de votre profil.", "danger")
            print(f"Database error on profile update: {e}")
            return render_template('profile.html', user=current_user)
        except Exception as e:
            conn.close()
            flash(f"Une erreur inattendue est survenue : {e}", "danger")
            print(f"Error updating profile: {e}")
            return render_template('profile.html', user=current_user)

    conn.close()
    # Pour la requête GET, passez l'objet current_user au template
    return render_template('profile.html', user=current_user)
@app.route('/products')
@login_required
def products():
    conn = get_db_connection()
    # MODIFICATION ICI : Ajouter 'date_added' à la liste des colonnes sélectionnées
    products_data = conn.execute('SELECT id, sku, name, size, purchase_price, quantity, price, image_url, date_added FROM products WHERE user_id = ? AND quantity > 0 ORDER BY date_added DESC',
                                 (current_user.id,)).fetchall()
    conn.close()
    return render_template('products.html', products=products_data)

# --- Votre route existante add_product ---
# --- Votre route existante add_product ---
@app.route('/products/add', methods=('GET', 'POST'))
@login_required
def add_product():
    # --- Débogage de l'utilisateur actuel ---
    # Ces lignes s'afficheront dans votre console Flask
    print(f"DEBUG: Accès à /products/add. Utilisateur authentifié : {current_user.is_authenticated}")
    if current_user.is_authenticated:
        print(f"DEBUG: ID de l'utilisateur : {current_user.id}, Nom d'utilisateur : {current_user.username}")
    else:
        print("DEBUG: current_user n'est PAS authentifié malgré @login_required.")
        # Si cette ligne s'affiche souvent, il y a un problème plus profond avec votre configuration Flask-Login ou la gestion des sessions.
        # Dans un cas extrême, vous pourriez vouloir rediriger manuellement ici:
        # flash("Vous devez être connecté pour ajouter un produit.", "danger")
        # return redirect(url_for('login'))


    error = None
    form_data = {
        'sku': request.form.get('sku', ''),
        'name': request.form.get('name', ''),
        'size': request.form.get('size', ''),
        'purchase_price': request.form.get('purchase_price', ''),
        'quantity': request.form.get('quantity', ''),
        'image_url': request.form.get('image_url', ''), # Récupérer image_url
        'description': request.form.get('description', '') # Récupérer description
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
            conn = get_db_connection()
            try:
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                purchase_price_float = float(form_data['purchase_price'])
                quantity_int = int(form_data['quantity'])
                selling_price_float = purchase_price_float # Par défaut, le prix de vente est le prix d'achat

                # --- MODIFICATION ICI : Utilisation de current_user.id directement ---
                conn.execute(
                    'INSERT INTO products (user_id, sku, name, size, purchase_price, quantity, price, description, image_url, date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (current_user.id, # <-- C'est ici que la modification est faite
                     form_data['sku'], form_data['name'], form_data['size'],
                     purchase_price_float, quantity_int, selling_price_float, form_data['description'],
                     form_data['image_url'],
                     current_date)
                )
                conn.commit()
                flash('Produit ajouté avec succès !', 'success')
                # IMPORTANT: Fermer la connexion avant la redirection
                conn.close()
                return redirect(url_for('products'))
            except ValueError:
                error = "Erreur de format pour le prix ou la quantité. Veuillez entrer des nombres valides."
                flash(error, 'danger')
            except Exception as e:
                # Capturez l'erreur complète pour un meilleur diagnostic
                error = f'Une erreur est survenue lors de l\'ajout du produit : {e}'
                print(f"DEBUG: Erreur détaillée dans le bloc try/except : {e}") # Pour voir l'erreur dans la console
                flash(error, 'danger')
            finally:
                if conn: # Assurez-vous que la connexion est fermée même en cas d'erreur
                    conn.close()

    # Formater purchase_price pour l'affichage si c'est un nombre valide
    display_purchase_price = form_data['purchase_price']
    if display_purchase_price:
        try:
            display_purchase_price = float(display_purchase_price)
        except ValueError:
            display_purchase_price = '' # Ou une autre valeur par défaut si non valide


    return render_template('add_product.html',
                           sku=form_data['sku'],
                           name=form_data['name'],
                           size=form_data['size'],
                           purchase_price=display_purchase_price,
                           quantity=form_data['quantity'],
                           image_url=form_data['image_url'],
                           description=form_data['description'],
                           error=error)
# ... (reste de votre code) ...
@app.route('/products/<int:id>/edit', methods=('GET', 'POST'))
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def edit_product(id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ? AND user_id = ?',
                           (id, current_user.id)).fetchone()

    if product is None:
        conn.close()
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
            conn.close()  # Important : fermer la connexion
            return render_template('edit_product.html', product=product)

        try:
            purchase_price = float(purchase_price)
            quantity = int(quantity)
        except ValueError:
            flash('Le prix d\'achat et la quantité doivent être des nombres valides.', 'danger')
            conn.close()
            return render_template('edit_product.html', product=product)

        try:
            conn.execute(
                "UPDATE products SET sku = ?, name = ?, size = ?, purchase_price = ?, quantity = ?, image_url = ? WHERE id = ? AND user_id = ?",
                (sku, name, size, purchase_price, quantity, image_url, id, current_user.id))
            conn.commit()
            flash('Produit mis à jour avec succès !', 'success')
            return redirect(url_for('products'))
        except sqlite3.IntegrityError:
            flash('Un produit avec ce SKU existe déjà. Veuillez utiliser une référence unique.', 'danger')
        finally:
            conn.close()

    conn.close()  # Fermer la connexion pour la requête GET
    return render_template('edit_product.html', product=product)


@app.route('/products/<int:id>/delete', methods=('POST',))
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def delete_product(id):
    conn = get_db_connection()
    product = conn.execute('SELECT id FROM products WHERE id = ? AND user_id = ?',
                           (id, current_user.id)).fetchone()

    if product is None:
        conn.close()
        abort(404)

    conn.execute('DELETE FROM products WHERE id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    flash('Produit supprimé avec succès !', 'success')
    return redirect(url_for('products'))


# --- Gestion des ventes ---
# ... (votre code existant) ...

@app.route('/sales/add', methods=('GET', 'POST'))
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def add_sale():
    conn = get_db_connection()
    products_for_dropdown = conn.execute(
        'SELECT id, name, sku, size, quantity, purchase_price FROM products WHERE user_id = ? AND quantity > 0 ORDER BY name',
        (current_user.id,)).fetchall()
    conn.close()

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
            conn = get_db_connection()
            try:
                quantity_sold = int(quantity_sold_str)
                sale_price_float = float(sale_price_str)
                shipping_cost_float = float(shipping_cost_str) if shipping_cost_str else 0.0
                fees_float = float(fees_str) if fees_str else 0.0

                purchase_price_at_sale = 0.0
                if product_id:
                    product_data_for_sale = conn.execute(
                        'SELECT purchase_price FROM products WHERE id = ? AND user_id = ?',
                        (product_id, current_user.id)).fetchone()
                    if product_data_for_sale:
                        purchase_price_at_sale = product_data_for_sale['purchase_price']

                # --- LIGNE CORRIGÉE POUR LE CALCUL DU PROFIT ---
                profit = sale_price_float - purchase_price_at_sale - shipping_cost_float - fees_float
                # --- FIN DE LA LIGNE CORRIGÉE ---

                conn.execute(
                    'INSERT INTO sales (user_id, product_id, item_name, quantity, sale_price, purchase_price_at_sale, sale_date, notes, sale_channel, shipping_cost, fees, profit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (current_user.id, product_id, item_name, quantity_sold, sale_price_float, purchase_price_at_sale,
                     sale_date, notes, platform, shipping_cost_float, fees_float, profit)
                )

                if product_id:
                    product_data = conn.execute('SELECT quantity FROM products WHERE id = ? AND user_id = ?',
                                                (product_id, current_user.id)).fetchone()
                    if product_data:
                        current_product_quantity = product_data['quantity']
                        new_quantity = current_product_quantity - quantity_sold
                        conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (new_quantity, product_id))
                        flash(f'Quantité du produit "{item_name}" mise à jour (ancien: {current_product_quantity}, nouveau: {new_quantity}).', 'info')
                        if new_quantity < 0:
                            flash('Attention: La quantité vendue dépasse le stock disponible. Le stock est devenu négatif.', 'warning')
                        elif new_quantity == 0:
                            flash(f'Le produit "{item_name}" est maintenant en rupture de stock.', 'info')
                    else:
                        flash('Avertissement: Le produit lié à la vente n\'a pas été trouvé pour la mise à jour du stock.', 'warning')

                conn.commit()
                flash('Vente enregistrée avec succès !', 'success')
                conn.close()
                return redirect(url_for('sales'))

            except ValueError:
                error = "Erreur de format pour les montants ou la quantité. Veuillez entrer des nombres valides."
                flash(error, 'danger')
            except Exception as e:
                error = f'Une erreur est survenue lors de l\'enregistrement de la vente : {e}'
                print(f"DEBUG: Erreur détaillée lors de l'enregistrement de la vente : {e}")
                flash(error, 'danger')
            finally:
                if conn:
                    conn.close()
        else:
            flash(error, 'danger')

    display_sale_price = '{:.2f}'.format(float(form_data['sale_price'])) if form_data['sale_price'] and form_data['sale_price'].replace('.', '', 1).isdigit() else ''
    display_shipping_cost = '{:.2f}'.format(float(form_data['shipping_cost'])) if form_data['shipping_cost'] and form_data['shipping_cost'].replace('.', '', 1).isdigit() else ''
    display_fees = '{:.2f}'.format(float(form_data['fees'])) if form_data['fees'] and form_data['fees'].replace('.', '', 1).isdigit() else ''

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



# --- Gestion des ventes (Route /sales) ---
@app.route('/sales')
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def sales():
    conn = get_db_connection()
    # Utiliser une LEFT JOIN pour récupérer les informations SKU et Taille du produit lié
    # SÉLECTIONNER MAINTENANT shipping_cost, fees et profit de la base de données
    sales_data_raw = conn.execute('''
        SELECT
            s.id,
            s.item_name,
            s.quantity,
            s.sale_price,
            s.purchase_price_at_sale, -- Récupérer le prix d'achat enregistré au moment de la vente
            s.sale_date,
            s.notes,
            s.sale_channel, -- Récupérer le canal de vente
            s.shipping_cost, -- AJOUTÉ
            s.fees,          -- AJOUTÉ
            s.profit,        -- AJOUTÉ
            p.sku,
            p.size
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.id
        WHERE s.user_id = ?
        ORDER BY s.sale_date DESC
    ''', (current_user.id,)).fetchall()
    conn.close()

    sales_for_template = []
    for sale in sales_data_raw:
        # Convertir sqlite3.Row en dict pour pouvoir ajouter de nouvelles clés et formater
        sale_dict = dict(sale)

        # Assurer que SKU et Taille affichent "N/A" si pas de produit lié
        sale_dict['sku'] = sale['sku'] if sale['sku'] else 'N/A'
        sale_dict['size'] = sale['size'] if sale['size'] else 'N/A'

        # Formater les montants pour l'affichage (s'assure qu'ils sont des nombres ou 0.0 pour éviter les erreurs)
        sale_dict['sale_price_formatted'] = '{:.2f} €'.format(sale_dict['sale_price'] or 0.0)
        sale_dict['purchase_price_at_sale_formatted'] = '{:.2f} €'.format(sale_dict['purchase_price_at_sale'] or 0.0)
        sale_dict['shipping_cost_formatted'] = '{:.2f} €'.format(sale_dict['shipping_cost'] or 0.0) # AJOUTÉ
        sale_dict['fees_formatted'] = '{:.2f} €'.format(sale_dict['fees'] or 0.0)                   # AJOUTÉ
        sale_dict['profit_formatted'] = '{:.2f} €'.format(sale_dict['profit'] or 0.0)               # AJOUTÉ

        sales_for_template.append(sale_dict)

    return render_template('sales.html', sales=sales_for_template)
@app.route('/sales/<int:id>/edit', methods=('GET', 'POST'))
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def edit_sale(id):
    conn = get_db_connection()
    sale = conn.execute('SELECT * FROM sales WHERE id = ? AND user_id = ?',
                        (id, current_user.id)).fetchone()

    if sale is None:
        conn.close()
        abort(404)

    # Récupérer les produits de l'utilisateur pour le menu déroulant
    products_for_dropdown = conn.execute('SELECT id, name, sku FROM products WHERE user_id = ? ORDER BY name',
                                         (current_user.id,)).fetchall()
    conn.close()

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

        conn = get_db_connection()
        # Logique de mise à jour de la quantité en stock si le produit lié change ou si la quantité vendue change
        if sale['product_id'] != product_id or sale['quantity'] != quantity:
            # Remettre l'ancienne quantité en stock si un produit était lié
            if sale['product_id']:
                conn.execute('UPDATE products SET quantity = quantity + ? WHERE id = ?',
                             (sale['quantity'], sale['product_id']))
            # Déduire la nouvelle quantité si un nouveau produit est lié
            if product_id:
                current_product = conn.execute('SELECT quantity FROM products WHERE id = ? AND user_id = ?',
                                               (product_id, current_user.id)).fetchone()
                if current_product:
                    new_stock = current_product['quantity'] - quantity
                    if new_stock < 0:
                        flash(
                            f"Quantité insuffisante en stock pour '{item_name}'. Stock actuel : {current_product['quantity']}",
                            "danger")
                        conn.rollback()  # Annuler les changements précédents si stock insuffisant
                        conn.close()
                        return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)
                    conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (new_stock, product_id))

        conn.execute(
            "UPDATE sales SET product_id = ?, item_name = ?, quantity = ?, sale_price = ?, sale_date = ?, notes = ? WHERE id = ? AND user_id = ?",
            (product_id, item_name, quantity, sale_price, sale_date, notes, id, current_user.id))
        conn.commit()
        conn.close()
        flash('Vente mise à jour avec succès !', 'success')
        return redirect(url_for('sales'))

    return render_template('edit_sale.html', sale=sale, products=products_for_dropdown)


@app.route('/statistics')
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def statistics():
    conn = get_db_connection()
    user_id = current_user.id

    selected_period = request.args.get('period', 'this_month') # Default to 'this_month'

    today = datetime.now()

    current_start_date = None
    current_end_date = None
    previous_start_date = None
    previous_end_date = None
    graph_granularity = 'month' # Default graph granularity

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
    else: # Fallback to 'this_month'
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

    total_sales_count_query = conn.execute("SELECT COUNT(id) FROM sales WHERE user_id = ? AND sale_date BETWEEN ? AND ?",
                                           (user_id, current_start_date_str, current_end_date_str)).fetchone()
    total_sales_count = total_sales_count_query[0] if total_sales_count_query and total_sales_count_query[0] is not None else 0

    total_sales_profit_query = conn.execute(
        "SELECT SUM((s.sale_price - s.purchase_price_at_sale) * s.quantity) FROM sales s WHERE s.user_id = ? AND s.sale_date BETWEEN ? AND ?",
        (user_id, current_start_date_str, current_end_date_str)).fetchone()
    total_sales_profit = total_sales_profit_query[0] if total_sales_profit_query and total_sales_profit_query[0] is not None else 0.0

    total_sales_revenue_query = conn.execute(
        "SELECT SUM(s.sale_price * s.quantity) FROM sales s WHERE s.user_id = ? AND s.sale_date BETWEEN ? AND ?",
        (user_id, current_start_date_str, current_end_date_str)).fetchone()
    total_sales_revenue = total_sales_revenue_query[0] if total_sales_revenue_query and total_sales_revenue_query[0] is not None else 0.0

    total_cogs_for_sold_items_query = conn.execute(
        "SELECT SUM(s.purchase_price_at_sale * s.quantity) FROM sales s WHERE s.user_id = ? AND s.sale_date BETWEEN ? AND ?",
        (user_id, current_start_date_str, current_end_date_str)).fetchone()
    total_cogs_for_sold_items = total_cogs_for_sold_items_query[0] if total_cogs_for_sold_items_query and total_cogs_for_sold_items_query[0] is not None else 0.0

    margin_rate = 0.0
    if total_sales_revenue > 0:
        margin_rate = (total_sales_profit / total_sales_revenue) * 100

    average_days_to_sell_query = conn.execute('''
        SELECT AVG(JULIANDAY(s.sale_date) - JULIANDAY(p.date_added)) AS avg_days
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.user_id = ?
          AND s.product_id IS NOT NULL
          AND p.date_added IS NOT NULL
          AND s.sale_date BETWEEN ? AND ?
    ''', (user_id, current_start_date_str, current_end_date_str)).fetchone()
    average_days_to_sell = average_days_to_sell_query[0] if average_days_to_sell_query and average_days_to_sell_query[0] is not None else 0.0
    average_days_to_sell = round(average_days_to_sell, 2)

    graph_labels = []
    graph_revenue_values = []
    graph_cogs_values = []
    graph_profit_values = []

    if graph_granularity == 'day':
        graph_query = '''
            SELECT
                STRFTIME('%Y-%m-%d', sale_date) AS period_label,
                SUM(sale_price * quantity) AS revenue,
                SUM(purchase_price_at_sale * quantity) AS cogs,
                SUM((sale_price - purchase_price_at_sale) * quantity) AS profit
            FROM sales
            WHERE user_id = ? AND sale_date BETWEEN ? AND ?
            GROUP BY period_label
            ORDER BY period_label
        '''
        graph_data = conn.execute(graph_query, (user_id, current_start_date_str, current_end_date_str)).fetchall()

        current_day_iter = current_start_date
        while current_day_iter <= current_end_date:
            day_str = current_day_iter.strftime('%Y-%m-%d')
            found_data = next((row for row in graph_data if row['period_label'] == day_str), None)

            graph_labels.append(day_str)
            graph_revenue_values.append(found_data['revenue'] if found_data else 0)
            graph_cogs_values.append(found_data['cogs'] if found_data else 0)
            graph_profit_values.append(found_data['profit'] if found_data else 0)
            current_day_iter += timedelta(days=1)
    else: # graph_granularity == 'month'
        graph_query = '''
            SELECT
                STRFTIME('%Y-%m', sale_date) AS period_label,
                SUM(sale_price * quantity) AS revenue,
                SUM(purchase_price_at_sale * quantity) AS cogs,
                SUM((sale_price - purchase_price_at_sale) * quantity) AS profit
            FROM sales
            WHERE user_id = ? AND sale_date BETWEEN ? AND ?
            GROUP BY period_label
            ORDER BY period_label
        '''
        graph_data = conn.execute(graph_query, (user_id, current_start_date_str, current_end_date_str)).fetchall()

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


    previous_period_totals = conn.execute(
        "SELECT SUM(s.sale_price * s.quantity) AS prev_revenue, "
        "SUM(s.purchase_price_at_sale * s.quantity) AS prev_cogs, "
        "SUM((s.sale_price - s.purchase_price_at_sale) * s.quantity) AS prev_profit "
        "FROM sales s "
        "WHERE s.user_id = ? AND s.sale_date BETWEEN ? AND ?",
        (user_id, previous_start_date_str, previous_end_date_str)
    ).fetchone()

    prev_total_revenue = previous_period_totals['prev_revenue'] if previous_period_totals and previous_period_totals['prev_revenue'] is not None else 0.0
    prev_total_cogs = previous_period_totals['prev_cogs'] if previous_period_totals and previous_period_totals['prev_cogs'] is not None else 0.0
    prev_total_profit = previous_period_totals['prev_profit'] if previous_period_totals and previous_period_totals['prev_profit'] is not None else 0.0

    def calculate_evolution_rate(current_value, previous_value):
        if previous_value == 0:
            if current_value > 0:
                return 'infinity' # Return string literal for infinity
            else:
                return 0.0 # Return 0.0 (float) if both are zero
        return ((current_value - previous_value) / previous_value) * 100

    evolution_rate_cogs = calculate_evolution_rate(total_cogs_for_sold_items, prev_total_cogs)
    evolution_rate_revenue = calculate_evolution_rate(total_sales_revenue, prev_total_revenue)
    evolution_rate_profit = calculate_evolution_rate(total_sales_profit, prev_total_profit)

    conn.close()

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
                           evolution_rate_profit=evolution_rate_profit
                           )
@app.route('/sales/<int:id>/delete', methods=('POST',))
@login_required
@key_active_required # AJOUTEZ CETTE LIGNE
def delete_sale(id):
    conn = get_db_connection()
    sale = conn.execute('SELECT product_id, quantity FROM sales WHERE id = ? AND user_id = ?',
                        (id, current_user.id)).fetchone()

    if sale is None:
        conn.close()
        abort(404)

    # Remettre la quantité en stock si la vente était liée à un produit
    if sale['product_id']:
        conn.execute('UPDATE products SET quantity = quantity + ? WHERE id = ?', (sale['quantity'], sale['product_id']))

    conn.execute('DELETE FROM sales WHERE id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    flash('Vente supprimée avec succès !', 'success')
    return redirect(url_for('sales'))


# --- Route d'erreur 404 ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    # Définissez le chemin complet vers votre fichier de base de données
    # MODIFICATION ICI : Le chemin pointe maintenant vers 'database.db' dans le PROJECT_ROOT
    db_path = os.path.join(PROJECT_ROOT, 'database.db')

    # Vérifiez si le fichier de base de données existe
    if not os.path.exists(db_path):
        print(f"Base de données '{db_path}' non trouvée. Initialisation...")
        # Exécute init_db() seulement si la base de données n'existe pas
        with app.app_context(): # Toujours nécessaire pour que init_db accède à 'current_app'
            init_db()
        print("Base de données initialisée avec succès.")
    else:
        print(f"Base de données '{db_path}' trouvée. Utilisation de la base existante.")

    # Lance l'application Flask
    app.run(debug=True)