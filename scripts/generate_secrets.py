#!/usr/bin/env python3
"""
Script de génération du secret JWT pour l'authentification KidSearch.
Génère JWT_SECRET_KEY pour l'API backend.
"""

import secrets
import sys


def generate_secrets():
    """Génère le secret JWT nécessaire pour l'authentification."""

    print("=" * 70)
    print("Génération du secret JWT pour KidSearch")
    print("=" * 70)
    print()

    # Générer JWT_SECRET_KEY
    jwt_secret = secrets.token_hex(32)
    print("Secret JWT généré avec succès")
    print()
    print("   ⚠️  Le secret sera affiché dans la console")
    print("   ⚠️  NE PAS afficher ou logger ce secret en production")
    print()
    print("-" * 70)
    print()

    # Afficher le contenu du .env.secrets
    print("Copiez les variables suivantes dans votre fichier .env principal:")
    print()

    env_content = f"""# Secret généré le {secrets.token_urlsafe(8)}
# NE PAS COMMITER CE FICHIER DANS GIT !

# Secret pour signer les JWT de l'API
JWT_SECRET_KEY={jwt_secret}

# Configuration JWT
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Configuration d'authentification par proxy (authcrunch)
# authcrunch injecte automatiquement les headers: X-Token-User-Email, X-Token-User-Name
AUTH_PROXY_ENABLED=true
AUTH_PROVIDERS=proxy
AUTH_PROXY_LOGOUT_URL=/

# API URL (pour le Dashboard)
API_URL=http://kidsearch-all:8080/api
"""

    output_file = ".env.secrets"
    with open(output_file, "w") as f:
        f.write(env_content)
    print(f"Secrets écrits dans {output_file}")
    print("⚠️  Ne pas commiter ce fichier dans git !")

    print()
    print("=" * 70)
    print("Note: authcrunch gère l'authentification automatiquement")
    print("=" * 70)
    print()
    print("authcrunch injecte les headers avec 'inject headers with claims':")
    print("  - X-Token-User-Email")
    print("  - X-Token-User-Name")
    print()
    print("Pas besoin de secret partagé entre Caddy et l'application !")
    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    generate_secrets()
