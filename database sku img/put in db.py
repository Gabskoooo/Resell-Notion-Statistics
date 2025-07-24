import json
import psycopg2
from psycopg2 import errors as pg_errors
import datetime
import os  # Pour vérifier la taille du fichier

# --- Configuration du fichier JSON d'entrée ---
JSON_FILE_PATH = "sku_img_with_name.json"  # Assurez-vous que ce chemin est correct

# --- Configuration PostgreSQL (vos identifiants Render) ---
DB_HOST = "dpg-d1v824qdbo4c73f9onog-a.oregon-postgres.render.com"
DB_NAME = "database_resell_notion_stats"
DB_USER = "database_resell_notion_stats_user"
DB_PASSWORD = "S93nJbBAUHQR1TimsIH4HfBHxtYCIRJy"
DB_PORT = "5432"

TABLE_NAME = "sku_database"  # Le nom de la table où importer les données


def get_db_connection():
    """
    Établit une connexion à la base de données PostgreSQL.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        print("Connexion à la base de données PostgreSQL établie avec succès.")
        return conn
    except Exception as e:
        print(f"ERREUR : Connexion à la base de données impossible : {e}")
        return None


def create_table_if_not_exists(conn):
    """
    Vérifie si la table sku_database existe et la crée si ce n'est pas le cas.
    """
    try:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(255) UNIQUE NOT NULL,
                image_url TEXT,
                product_name VARCHAR(512),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print(f"Table '{TABLE_NAME}' vérifiée/créée avec succès.")
        cur.close()
        return True
    except Exception as e:
        print(f"ERREUR : Impossible de créer ou vérifier la table '{TABLE_NAME}' : {e}")
        conn.rollback()
        return False


def import_data_to_db():
    """
    Charge les données du fichier JSON et les importe dans la base de données.
    """
    conn = None
    try:
        print(f"Tentative de chargement du fichier JSON : '{JSON_FILE_PATH}'")

        # --- LOGS DE DÉBOGAGE POUR LA LECTURE DU FICHIER JSON ---
        if not os.path.exists(JSON_FILE_PATH):
            print(f"ERREUR : Le fichier '{JSON_FILE_PATH}' n'existe PAS à l'emplacement spécifié.")
            print(f"Vérifiez le chemin du fichier et le répertoire d'exécution du script.")
            return

        file_size_bytes = os.path.getsize(JSON_FILE_PATH)
        print(f"DEBUG : Taille du fichier '{JSON_FILE_PATH}' : {file_size_bytes / (1024 * 1024):.2f} MB")

        # Lecture du fichier comme texte brut pour inspecter le début
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f_raw:
                first_chars = f_raw.read(100)  # Lire les 100 premiers caractères
                print(f"DEBUG : 100 premiers caractères du fichier : '{first_chars}'")
                # Si le fichier commence par un BOM UTF-8 (souvent invisible), on pourrait le voir ici comme '\ufeff'
                if first_chars.startswith('\ufeff'):
                    print(
                        "ATTENTION : Le fichier semble commencer par un BOM UTF-8. Cela peut parfois causer des problèmes, mais Python devrait le gérer.")
        except UnicodeDecodeError as e:
            print(f"ERREUR DE DÉCODAGE BRUT : Impossible de lire les premiers caractères en UTF-8. Cause : {e}")
            print(
                "Le fichier pourrait ne pas être en UTF-8. Essayez de l'ouvrir dans un éditeur de texte et de le sauvegarder en UTF-8.")
            return
        # --- FIN DES LOGS DE DÉBOGAGE POUR LA LECTURE DU FICHIER JSON ---

        # 1. Charger les données depuis le fichier JSON
        # Spécifier l'encodage pour éviter les problèmes
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data_to_import = json.load(f)

        print(f"Chargement de {len(data_to_import)} entrées depuis '{JSON_FILE_PATH}' effectué avec succès.")

        # 2. Établir la connexion à la base de données
        conn = get_db_connection()
        if not conn:
            return

        # 3. S'assurer que la table existe
        if not create_table_if_not_exists(conn):
            conn.close()
            return

        # 4. Importer les données
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        total_items = len(data_to_import)

        cur = conn.cursor()  # Ouvrir un seul curseur pour toutes les insertions

        for i, item in enumerate(data_to_import):
            # Mappage des clés du nouveau format JSON
            sku = item.get("sku")
            product_name = item.get("product_name")
            image_url = item.get("image_url")

            # Validation basique
            if not sku or not isinstance(sku, str) or sku.strip() == "":
                print(f"  [SKIPPED] Ligne {i + 1}/{total_items}: SKU invalide ou manquant ('{sku}'). Ignoré.")
                skipped_count += 1
                continue

                # Assurez-vous que les valeurs sont bien des chaînes de caractères (ou None)
            sku = str(sku).strip() if sku is not None else None
            product_name = str(product_name).strip() if product_name is not None else None
            image_url = str(image_url).strip() if image_url is not None else None

            # Obtenir le timestamp actuel pour 'last_updated'
            current_timestamp = datetime.datetime.now()

            try:
                cur.execute(f"""
                    INSERT INTO {TABLE_NAME} (sku, product_name, image_url, last_updated)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (sku) DO UPDATE SET
                        product_name = EXCLUDED.product_name,
                        image_url = EXCLUDED.image_url,
                        last_updated = EXCLUDED.last_updated;
                """, (sku, product_name, image_url, current_timestamp))

                if cur.rowcount > 0:
                    if cur.statusmessage.startswith("INSERT"):
                        imported_count += 1
                    elif cur.statusmessage.startswith("UPDATE"):
                        updated_count += 1

                # Commiter par lots
                if (i + 1) % 100 == 0:
                    conn.commit()
                    print(
                        f"  Progression: {i + 1}/{total_items} traités (insérés: {imported_count}, mis à jour: {updated_count}, ignorés: {skipped_count}).")

            except pg_errors.DataError as e:
                conn.rollback()
                print(
                    f"  [ERREUR SQL GRAVE] Ligne {i + 1}/{total_items} (SKU: '{sku}'): Erreur de données - {e}. Transaction annulée.")
                print(f"  Détails de la ligne : SKU='{sku}', Nom='{product_name}', Image='{image_url}'")
                skipped_count += 1
            except Exception as e:
                conn.rollback()
                print(
                    f"  [ERREUR IMPORT INCONNUE] Ligne {i + 1}/{total_items} (SKU: '{sku}'): {e}. Transaction annulée.")
                print(f"  Détails de la ligne : SKU='{sku}', Nom='{product_name}', Image='{image_url}'")
                skipped_count += 1

        # Commiter les insertions restantes à la fin
        conn.commit()
        print("\n--- Processus d'importation terminé ---")
        print(f"Total inséré dans la DB: {imported_count}")
        print(f"Total mis à jour dans la DB: {updated_count}")
        print(f"Total ignoré (SKU invalide, erreur de ligne): {skipped_count}")
        print(f"Total d'éléments lus depuis le JSON: {total_items}")

    except FileNotFoundError:
        print(f"ERREUR FATALE : Le fichier JSON '{JSON_FILE_PATH}' n'a pas été trouvé (répétition, mais important).")
    except json.JSONDecodeError as e:
        print(f"\nERREUR FATALE DE DÉCODAGE JSON : Impossible de lire le fichier '{JSON_FILE_PATH}'.")
        print(f"Détails de l'erreur JSON : {e}")
        print(
            f"Vérifiez la syntaxe JSON du fichier à la ligne/colonne indiquée ci-dessus. Utilisez un validateur JSON en ligne.")
        print(
            f"Le problème peut être une virgule manquante, des guillemets incorrects, des crochets/accolades non balancés, ou des caractères non-JSON.")
    except Exception as e:
        print(f"ERREUR FATALE INCONNUE : Une erreur inattendue est survenue au niveau global : {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
            print("Connexion à la base de données fermée.")


if __name__ == "__main__":
    import_data_to_db()