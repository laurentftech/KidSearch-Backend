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
    print("Secret pour signer les JWT de l'API:")
    print()
    print(f"   JWT_SECRET_KEY={jwt_secret}")
    print()
    print("   ⚠️  Ce secret doit être configuré dans .env:")
    print()
    print("-" * 70)
    print()

    # Générer un fichier .env.secrets
    print("Génération du fichier .env.secrets...")

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

    try:
        with open(".env.secrets", "w") as f:
            f.write(env_content)
        print("   ✓ Fichier .env.secrets créé avec succès")
        print()
        print("   Pour l'utiliser, copiez les variables dans votre .env principal")
    except Exception as e:
        print(f"   ✗ Erreur lors de la création du fichier: {e}")
        print()
        print("   Copiez manuellement le secret ci-dessus dans votre .env")

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
