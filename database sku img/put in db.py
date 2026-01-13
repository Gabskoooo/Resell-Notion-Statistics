import json
import psycopg2
from psycopg2 import errors as pg_errors
import psycopg2.extras
import datetime
import os
import time

# --- Configuration du fichier JSON d'entrée ---
JSON_FILE_PATH = "shoes_by_whentocop.json"

# --- Configuration PostgreSQL (vos identifiants Render) ---
DB_HOST = "dpg-d1v824qdbo4c73f9onog-a.oregon-postgres.render.com"
DB_NAME = "database_resell_notion_stats"
DB_USER = "database_resell_notion_stats_user"
DB_PASSWORD = "S93nJbBAUHQR1TimsIH4HfBHxtYCIRJy"
DB_PORT = "5432"

TABLE_NAME = "sku_database"
BATCH_SIZE = 1000  # Taille du lot d'insertion.


def get_db_connection():
    """Établit une connexion à la base de données PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        # print("Connexion à la base de données PostgreSQL établie avec succès.")
        return conn
    except Exception as e:
        print(f"ERREUR : Connexion à la base de données impossible : {e}")
        return None


def create_table_if_not_exists(conn):
    """Vérifie si la table sku_database existe et la crée si ce n'est pas le cas."""
    try:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS public.{TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(255) UNIQUE NOT NULL,
                image_url TEXT,
                product_name VARCHAR(512),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print(f"Table 'public.{TABLE_NAME}' vérifiée/créée avec succès.")
        cur.close()
        return True
    except Exception as e:
        print(f"ERREUR : Impossible de créer ou vérifier la table 'public.{TABLE_NAME}' : {e}")
        conn.rollback()
        return False


def import_data_to_db():
    """
    Charge les données du fichier JSON, les déduplique globalement,
    et les importe dans la base de données en utilisant execute_values.
    """
    conn = None
    total_items_read = 0
    total_skipped = 0
    start_time = time.time()

    try:
        print(f"Tentative de chargement du fichier JSON : '{JSON_FILE_PATH}'")

        if not os.path.exists(JSON_FILE_PATH):
            print(f"ERREUR : Le fichier '{JSON_FILE_PATH}' n'existe PAS à l'emplacement spécifié.")
            return

        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data_list = json.load(f)

        total_items_read = len(data_list)
        print(f"Chargement de {total_items_read} entrées depuis '{JSON_FILE_PATH}' effectué avec succès.")

        # --- ÉTAPE CLÉ : DÉDUPLICATION GLOBALE ---
        print("Début de la déduplication du jeu de données...")
        dedup_map = {}  # Utilisé pour garantir l'unicité du SKU (le dernier SKU trouvé gagne)
        temp_skipped_count = 0

        for item in data_list:
            sku = item.get("sku")

            # Validation de base
            if not sku or not isinstance(sku, str) or sku.strip() == "":
                temp_skipped_count += 1
                continue

            # Met à jour le dictionnaire. Le SKU le plus récent écrase l'ancien.
            dedup_map[sku.strip()] = item

        # Convertir le dictionnaire dédupliqué en liste ordonnée
        deduplicated_data = list(dedup_map.values())
        total_unique_items = len(deduplicated_data)
        total_duplicates = total_items_read - total_unique_items - temp_skipped_count

        print(f"-> {total_unique_items} SKU uniques trouvés.")
        print(f"-> {total_duplicates} doublons supprimés.")
        total_skipped += temp_skipped_count

        # 2. Établir la connexion à la base de données
        conn = get_db_connection()
        if not conn:
            return

        # 3. S'assurer que la table existe
        if not create_table_if_not_exists(conn):
            conn.close()
            return

        # 4. Importer les données en bloc
        data_to_send = []
        cur = conn.cursor()

        insert_query = f"""
            INSERT INTO public.{TABLE_NAME} (sku, product_name, image_url, last_updated)
            VALUES %s
            ON CONFLICT (sku) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                image_url = EXCLUDED.image_url,
                last_updated = EXCLUDED.last_updated;
        """

        for i, item in enumerate(deduplicated_data):
            # Les données sont déjà pré-validées et dédupliquées
            sku = item["sku"].strip()
            product_name = item.get("product_name", "").strip()
            image_url = item.get("image_url", "").strip()
            current_timestamp = datetime.datetime.now()

            # Ajouter les données au lot
            data_to_send.append((sku, product_name, image_url, current_timestamp))

            # Exécuter le lot si la taille maximale est atteinte OU s'il s'agit du dernier élément
            is_last_item = (i + 1) == total_unique_items

            if len(data_to_send) >= BATCH_SIZE or (is_last_item and data_to_send):

                try:
                    # Envoi du lot au DB
                    psycopg2.extras.execute_values(
                        cur,
                        insert_query,
                        data_to_send,
                        page_size=BATCH_SIZE
                    )

                    elapsed_time = time.time() - start_time

                    print(
                        f"  Progression DB : {i + 1}/{total_unique_items} traités. Lot de {len(data_to_send)} lignes envoyé. Temps total: {elapsed_time:.2f}s."
                    )

                    conn.commit()
                    data_to_send = []  # Réinitialiser le lot

                except Exception as e:
                    conn.rollback()
                    print(
                        f"  [ERREUR LOT FATALE] Échec du traitement du lot. Cause : {e}. Les données restantes sont ignorées."
                    )
                    total_skipped += len(data_to_send)  # Ces lignes sont perdues
                    break

    except FileNotFoundError:
        print(f"ERREUR FATALE : Le fichier JSON '{JSON_FILE_PATH}' n'a pas été trouvé.")
    except json.JSONDecodeError as e:
        print(f"\nERREUR FATALE DE DÉCODAGE JSON : Impossible de lire le fichier '{JSON_FILE_PATH}'. Détails : {e}")
    except Exception as e:
        print(f"ERREUR FATALE INCONNUE : Une erreur inattendue est survenue au niveau global : {e}")
    finally:
        end_time = time.time()
        final_elapsed_time = end_time - start_time

        if conn:
            cur.close()
            conn.close()
            print("Connexion à la base de données fermée.")

        print("\n--- Processus d'importation terminé ---")
        print(f"Temps total d'exécution : {final_elapsed_time:.2f} secondes.")
        print(f"Total des lignes lues depuis le JSON: {total_items_read}")
        print(
            f"Total des lignes uniques et valides envoyées au DB: {total_unique_items if 'total_unique_items' in locals() else 0}")
        print(
            f"Total ignoré (doublons ou SKU invalides): {total_items_read - (total_unique_items if 'total_unique_items' in locals() else 0)}")


if __name__ == "__main__":
    import_data_to_db()