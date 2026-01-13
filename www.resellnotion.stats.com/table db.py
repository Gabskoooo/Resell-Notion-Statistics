import psycopg2

# Ton URL complète corrigée
DATABASE_URL = "postgresql://database_resell_notion_stats_user:S93nJbBAUHQR1TimsIH4HfBHxtYCIRJy@dpg-d1v824qdbo4c73f9onog-a.oregon-postgres.render.com/database_resell_notion_stats"


def inspect_database():
    # Ajout du paramètre SSL obligatoire pour Render
    url_with_ssl = DATABASE_URL + "?sslmode=require"

    print("--- Connexion à la base de données en cours ---")
    try:
        conn = psycopg2.connect(url_with_ssl)
        cur = conn.cursor()

        # Requête pour lister tables et colonnes
        cur.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)

        rows = cur.fetchall()

        if not rows:
            print("Connexion réussie ! Mais aucune table n'existe encore dans cette base.")
        else:
            print("Structure détectée :")
            current_table = ""
            for table, column, dtype in rows:
                if table != current_table:
                    print(f"\n[TABLE] : {table}")
                    current_table = table
                print(f"  ├── {column} ({dtype})")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Erreur : {e}")


if __name__ == "__main__":
    inspect_database()