#!/usr/bin/env python3
"""Create Typesense collection with schema"""

import os
import sys
from dotenv import load_dotenv
import typesense

# Load environment variables
load_dotenv()

TYPESENSE_URL = os.getenv("TYPESENSE_URL", "http://localhost:8108")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "masterKey")
INDEX_NAME = os.getenv("INDEX_NAME", "kidsearch")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "none").lower()
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

print("Configuration:")
print(f"  URL: {TYPESENSE_URL}")
print(f"  Collection: {INDEX_NAME}")
print(f"  Embeddings: {EMBEDDING_PROVIDER}")
if EMBEDDING_PROVIDER in ["gemini", "huggingface", "sentence_transformer"]:
    print(f"  Dimensions: {EMBEDDING_DIMENSIONS}")

# Parse URL
url_parts = TYPESENSE_URL.replace("http://", "").replace("https://", "").split(":")
host = url_parts[0]
port = int(url_parts[1]) if len(url_parts) > 1 else 8108
protocol = "https" if "https://" in TYPESENSE_URL else "http"

# Create client
print(f"\nConnexion à Typesense ({host}:{port})...")
client = typesense.Client(
    {
        "nodes": [{"host": host, "port": str(port), "protocol": protocol}],
        "api_key": TYPESENSE_API_KEY,
        "connection_timeout_seconds": 10,
    }
)

# Define schema
schema = {
    "name": INDEX_NAME,
    "enable_nested_fields": True,
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "site", "type": "string", "facet": True},
        {"name": "url", "type": "string"},
        {"name": "title", "type": "string"},
        {"name": "excerpt", "type": "string"},
        {"name": "content", "type": "string"},
        {"name": "images", "type": "object[]"},
        {"name": "lang", "type": "string", "facet": True},
        {"name": "timestamp", "type": "int64"},
        {"name": "indexed_at", "type": "string"},
        {"name": "last_crawled_at", "type": "string"},
        {"name": "content_hash", "type": "string"},
    ],
}

# Add vector fields if embeddings enabled
if EMBEDDING_PROVIDER in ["gemini", "huggingface", "sentence_transformer"]:
    schema["fields"].extend(
        [
            {
                "name": "embedding_vec",
                "type": "float[]",
                "num_dim": EMBEDDING_DIMENSIONS,
            },
            {"name": "embedding_provider", "type": "string", "optional": True},
            {"name": "embedding_model", "type": "string", "optional": True},
            {"name": "embedding_dimensions", "type": "int32", "optional": True},
        ]
    )
    print(f"✨ Support des embeddings activé ({EMBEDDING_DIMENSIONS} dimensions)")

try:
    # Check if collection exists
    print(f"\nVérification de l'existence de la collection '{INDEX_NAME}'...")
    try:
        existing = client.collections[INDEX_NAME].retrieve()
        print(f"✅ La collection '{INDEX_NAME}' existe déjà.")
        print(f"   Documents: {existing.get('num_documents', 0)}")
        print(f"   Champs: {len(existing.get('fields', []))}")
        sys.exit(0)
    except Exception:
        pass  # Collection doesn't exist, create it

    # Create collection
    print(f"\nCréation de la collection '{INDEX_NAME}'...")
    result = client.collections.create(schema)
    print(f"✅ Collection '{INDEX_NAME}' créée avec succès!")
    print(f"   Champs: {len(schema['fields'])}")

    if EMBEDDING_PROVIDER in ["gemini", "huggingface", "sentence_transformer"]:
        print(f"   Vector search: Activé ({EMBEDDING_DIMENSIONS}D)")
    else:
        print("   Vector search: Désactivé (recherche par mots-clés uniquement)")

except Exception as e:
    print(f"\n❌ Erreur: {e}")
    sys.exit(1)
