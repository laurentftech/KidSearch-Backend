# Authentification avec Caddy + authcrunch (Solution finale)

## Architecture

```
User → Caddy (authcrunch) → Dashboard → API (JWT)
         ↓
    X-Token-User-Email
    X-Token-User-Name
```

## Solution officielle authcrunch

AuthCrunch fournit une directive **`inject headers with claims`** qui injecte automatiquement les headers HTTP suivants :

- `X-Token-User-Email` → Email de l'utilisateur
- `X-Token-User-Name` → Nom de l'utilisateur
- `X-Token-Subject` → Subject (identifiant)
- `X-Token-User-Roles` → Rôles de l'utilisateur

Documentation : https://docs.authcrunch.com/docs/authorize/headers

## Configuration

### 1. Caddyfile

Le fichier complet est dans `docs/Caddyfile` :

```caddy
{
    security {
        authorization policy admin_only {
            set auth url https://auth.gandulf78.synology.me
            allow roles authp/admin authp/user
            crypto key verify {env.JWT_SECRET_KEY}

            # CLEF : Injecter les claims JWT dans les headers HTTP
            inject headers with claims

            allow email @gandulf78.synology.me
            allow email laurent@example.com
        }
    }
}

https://kidsearch-admin.gandulf78.synology.me {
    authorize with admin_only

    reverse_proxy kidsearch-all:8501 {
        # authcrunch injecte automatiquement:
        # - X-Token-User-Email
        # - X-Token-User-Name
        # - X-Token-Subject
        # - X-Token-User-Roles

        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}

        # Support WebSocket pour Streamlit
        header_up Connection {>Connection}
        header_up Upgrade {>Upgrade}
    }
}
```

### 2. Variables d'environnement (.env)

```env
# Proxy authentication
AUTH_PROXY_ENABLED=true
AUTH_PROVIDERS=proxy

# JWT pour l'API
JWT_SECRET_KEY=<généré avec python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# API URL
API_URL=http://kidsearch-all:8080/api

# OIDC (pour authcrunch)
OIDC_ISSUER=https://pocket-id.gandulf78.synology.me
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret

# Emails autorisés
ALLOWED_EMAILS=laurent@example.com,user@example.com
```

### 3. Variables d'environnement Caddy

```bash
export JWT_SECRET_KEY=<même valeur que dans .env>
export OIDC_CLIENT_ID=your_client_id
export OIDC_CLIENT_SECRET=your_client_secret
export OIDC_ISSUER=https://pocket-id.gandulf78.synology.me
```

## Flux d'authentification

### 1. Première connexion

```
1. User → https://kidsearch-admin.gandulf78.synology.me
2. Caddy → authorize with admin_only
3. Caddy → Redirige vers https://auth.gandulf78.synology.me
4. User → S'authentifie via OIDC (Pocket ID, Authentik, etc.)
5. authcrunch → Génère JWT et cookie
6. Caddy → Injecte headers: X-Token-User-Email, X-Token-User-Name
7. Dashboard → Lit les headers
8. Dashboard → Appelle API POST /auth/token/headers
9. API → Génère JWT application
10. Dashboard → Stocke JWT dans localStorage
11. Dashboard → Affiche l'interface
```

### 2. Visites suivantes

```
1. User → https://kidsearch-admin.gandulf78.synology.me
2. Caddy → Vérifie cookie authcrunch → OK
3. Caddy → Injecte headers
4. Dashboard → Lit JWT depuis localStorage → OK
5. Dashboard → Affiche l'interface directement
```

### 3. Requêtes API

```
1. Dashboard → Appelle API avec header: Authorization: Bearer <jwt>
2. API → Vérifie JWT
3. API → Retourne les données
```

## Sécurité

### Protection réseau

La route `/auth/token/headers` doit être **protégée** :

**Option 1** : Firewall (recommandé)
```bash
# Bloquer l'accès direct à l'API depuis Internet
# Autoriser seulement Caddy (réseau interne)
```

**Option 2** : Restriction IP dans l'API
```python
ALLOWED_PROXY_IPS = ["172.18.0.0/16"]  # Réseau Docker
```

### Secrets

- `JWT_SECRET_KEY` : Secret pour signer les JWT de l'API (généré avec `secrets.token_hex(32)`)
- Pas de `AUTH_PROXY_SHARED_SECRET` nécessaire (géré par authcrunch)

## Dépannage

### Headers non reçus

Vérifiez que `inject headers with claims` est bien dans la policy d'autorisation.

### JWT invalide

Vérifiez que `JWT_SECRET_KEY` est identique partout.

### Logs

```bash
# Dashboard
docker-compose logs -f kidsearch-all | grep auth

# Vérifier les headers reçus
tail -f data/logs/auth.log
```

## Ressources

- [AuthCrunch - HTTP Headers](https://docs.authcrunch.com/docs/authorize/headers)
- [AuthCrunch - Token Verification](https://docs.authcrunch.com/docs/authorize/token-verification)
- [AuthCrunch - Identity](https://docs.authcrunch.com/docs/authorize/identity)
