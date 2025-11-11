# Les deux secrets expliqués

## 🔑 Résumé rapide

Votre setup utilise **DEUX secrets INDÉPENDANTS** pour deux systèmes différents:

| Secret | Utilisé par | Rôle | Où le configurer |
|--------|-------------|------|------------------|
| `OIDC_CLIENT_SECRET` | Caddy authcrunch | Signe les cookies de session authcrunch | Pocket ID + Caddy |
| `JWT_SECRET_KEY` | API KidSearch | Signe les JWT pour Dashboard ↔ API | `.env` de KidSearch uniquement |

## 🔄 Flux complet

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User accède à https://kidsearch-admin.gandulf78.synology.me │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Reverse Proxy Synology (HTTPS → HTTP)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Caddy authcrunch                                              │
│    - Vérifie cookie (signé avec OIDC_CLIENT_SECRET)             │
│    - Si pas de cookie → redirige vers Pocket ID                 │
│    - Si authentifié → inject headers with claims                │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
                  X-Token-User-Email: lfrancoise@gmail.com
                  X-Token-User-Name: Laurent Francoise
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Dashboard Streamlit                                           │
│    - Lit les headers (fait confiance à Caddy)                   │
│    - Appelle API: POST /auth/token/headers                      │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. API KidSearch                                                 │
│    - Reçoit X-Token-User-Email depuis le Dashboard              │
│    - Génère JWT (signé avec JWT_SECRET_KEY)                     │
│    - Retourne: {"access_token": "eyJhbG..."}                    │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Dashboard stocke JWT dans localStorage                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Requêtes API suivantes                                        │
│    Dashboard → API avec: Authorization: Bearer eyJhbG...         │
│    API vérifie JWT avec JWT_SECRET_KEY                          │
└─────────────────────────────────────────────────────────────────┘
```

## 🛡️ Sécurité

### Pourquoi deux secrets ?

**Séparation des responsabilités:**
- Caddy authcrunch gère l'authentification utilisateur (OIDC, cookies)
- L'API KidSearch gère l'autorisation des requêtes (JWT)

### Quel secret va où ?

#### `OIDC_CLIENT_SECRET`

```bash
# Dans Pocket ID
# Configuré lors de la création du client OIDC
Client ID: votre_client_id
Client Secret: votre_secret_ici ← Ce secret

# Dans Caddy
export OIDC_CLIENT_ID=votre_client_id
export OIDC_CLIENT_SECRET=votre_secret_ici ← Même secret
export OIDC_ISSUER=https://pocket-id.gandulf78.synology.me

# Dans Caddyfile
authentication portal admin_portal {
    crypto key sign-verify {env.OIDC_CLIENT_SECRET}
    # ...
}

authorization policy admin_only {
    crypto key verify {env.OIDC_CLIENT_SECRET}
    # ...
}
```

#### `JWT_SECRET_KEY`

```bash
# Générer le secret
python -c "import secrets; print(secrets.token_hex(32))"

# Dans .env de KidSearch
JWT_SECRET_KEY=04f1c7c39e57f439933d3116ea6d3a67633350bc08339dbf98cbede95e342f42
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440
```

**PAS dans Caddy !**

## 🔍 Vérification

### Pour vérifier que tout est bien configuré:

```bash
# 1. Vérifier OIDC_CLIENT_SECRET dans Caddy
docker-compose exec caddy env | grep OIDC_CLIENT_SECRET

# 2. Vérifier JWT_SECRET_KEY dans KidSearch
docker-compose exec kidsearch-all env | grep JWT_SECRET_KEY

# 3. S'assurer que JWT_SECRET_KEY n'est PAS dans Caddy (devrait être vide)
docker-compose exec caddy env | grep JWT_SECRET_KEY
# (devrait ne rien retourner ou être vide)
```

## ❓ FAQ

### Q: Pourquoi authcrunch ne peut-il pas utiliser JWT_SECRET_KEY ?

**R:** authcrunch n'a pas besoin de `JWT_SECRET_KEY` car:
1. Il gère ses propres cookies avec `OIDC_CLIENT_SECRET`
2. Il injecte simplement les headers (pas de signature nécessaire)
3. C'est le rôle de l'API de générer et vérifier les JWT

### Q: Est-ce que JWT_SECRET_KEY doit être partagé quelque part ?

**R:** NON. `JWT_SECRET_KEY` est uniquement connu de l'API KidSearch. Ni Caddy, ni Pocket ID ne le connaissent.

### Q: Que se passe-t-il si je change OIDC_CLIENT_SECRET ?

**R:**
1. Tous les cookies authcrunch existants deviennent invalides
2. Les utilisateurs doivent se reconnecter
3. Les JWT KidSearch continuent de fonctionner (ils sont indépendants)

### Q: Que se passe-t-il si je change JWT_SECRET_KEY ?

**R:**
1. Tous les JWT existants deviennent invalides
2. Les utilisateurs doivent se reconnecter pour obtenir un nouveau JWT
3. Les cookies authcrunch continuent de fonctionner (ils sont indépendants)

## ✅ Checklist de configuration

- [ ] `OIDC_CLIENT_SECRET` configuré dans Pocket ID
- [ ] `OIDC_CLIENT_SECRET` configuré dans Caddy (variable d'environnement)
- [ ] `JWT_SECRET_KEY` généré et configuré dans `.env` de KidSearch
- [ ] `JWT_SECRET_KEY` **N'EST PAS** dans les variables d'environnement de Caddy
- [ ] Les deux secrets sont dans `.gitignore` et ne sont PAS committés
- [ ] `inject headers with claims` est présent dans le Caddyfile
