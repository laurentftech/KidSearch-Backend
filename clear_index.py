import requests
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

TYPESENSE_URL = os.getenv("TYPESENSE_URL")
API_KEY = os.getenv("TYPESENSE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME", "kidsearch")  # Utilise 'kidsearch' par défaut

if not TYPESENSE_URL or not API_KEY:
    print(
        "Erreur: TYPESENSE_URL et TYPESENSE_API_KEY doivent être définis dans le fichier .env"
    )
    exit(1)

headers = {"X-TYPESENSE-API-KEY": f"{API_KEY}"}

print(f"Tentative de vider l'index '{INDEX_NAME}' sur {TYPESENSE_URL}...")

# Demander confirmation
confirm = input(
    "Êtes-vous sûr de vouloir supprimer tous les documents de cet index ? (oui/non): "
)

if confirm.lower() == "oui":
    try:
        # In Typesense, you delete documents by using a filter that matches all documents.
        # The `delete` operation on a collection would delete the collection itself.
        delete_params = {"filter_by": "id:>=0", "batch_size": 500}
        r = requests.delete(
            f"{TYPESENSE_URL}/collections/{INDEX_NAME}/documents",
            headers=headers,
            params=delete_params,
            timeout=30,  # Increased timeout for potentially long operations
        )
        r.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP

        print("\nRéponse de Typesense :")
        print(f"  Status: {r.status_code}")
        print(f"  Contenu: {r.json()}")
        print("\n✅ L'index a été vidé avec succès.")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Erreur de connexion à Typesense: {e}")
else:
    print("\nOpération annulée.")
