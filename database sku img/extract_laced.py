import json

# Nom du fichier JSON à re-formater (celui qui a été nettoyé)
input_filename = "chaussures_whentocop_data_cleaned.json"  # Ou "chaussures_whentocop_data_html_fast.json" si vous n'avez pas encore nettoyé les noms
# Nom du nouveau fichier JSON avec la structure désirée
output_filename = "chaussures_whentocop_data_final_format.json"

try:
    # Charger les données depuis le fichier JSON d'entrée
    with open(input_filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Chargement de {len(data)} entrées depuis '{input_filename}'...")

    reformatted_data = []
    # Parcourir chaque entrée et re-formater les clés
    for item in data:
        new_item = {}
        # Vérifier si les clés existent avant de les renommer pour éviter les erreurs
        if "SKU" in item:
            new_item["sku"] = item["SKU"]
        if "Lien_image" in item:
            new_item["image_url"] = item["Lien_image"]
        if "Nom" in item:
            new_item["product_name"] = item["Nom"]

        reformatted_data.append(new_item)

    # Enregistrer les données reformatées dans un nouveau fichier JSON
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(reformatted_data, f, ensure_ascii=False, indent=4)  # Utilisez indent=4 pour une meilleure lisibilité

    print(f"\nReformatage terminé. {len(reformatted_data)} entrées ont été reformatées.")
    print(f"Les données reformatées ont été enregistrées dans '{output_filename}'")

except FileNotFoundError:
    print(
        f"Erreur : Le fichier '{input_filename}' n'a pas été trouvé. Assurez-vous qu'il se trouve dans le même répertoire que ce script.")
except json.JSONDecodeError:
    print(f"Erreur : Impossible de décoder le fichier '{input_filename}'. Vérifiez qu'il s'agit d'un JSON valide.")
except Exception as e:
    print(f"Une erreur inattendue est survenue : {e}")