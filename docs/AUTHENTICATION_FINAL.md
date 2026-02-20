# Authentification avec Caddy + AuthCrunch (Configuration proxy)

## Architecture

```
User → Caddy (AuthCrunch) → kidsearch-all (Streamlit Dashboard)
              ↓
    inject headers with claims
              ↓
    X-Token-User-Email
    X-Token-User-Name
```

## Principe

Caddy + AuthCrunch gère l'authentification en amont. Une fois l'utilisateur authentifié, AuthCrunch injecte les claims JWT sous forme de headers HTTP vers le dashboard Streamlit. KidSearch lit ces headers pour identifier l'utilisateur sans gérer d'authentification propre.

## Configuration

### 1. Réseau Docker

Le container `kidsearch-all` doit être sur le **même réseau Docker** que Caddy pour permettre la résolution DNS directe :

```yaml
# compose.yaml
services:
  kidsearch-all:
    networks:
      - kidsearch-network
      - caddy-network   # ← ajouter le réseau Caddy

networks:
  caddy-network:
    external: true      # ← réseau créé par le stack Caddy
```

### 2. Streamlit config.toml

Obligatoire pour fonctionner derrière un reverse proxy. Créer `.streamlit/config.toml` (monté dans le container via `./streamlit:/app/.streamlit`) :

```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
```

Sans ce fichier, Streamlit génère des URLs incorrectes pour ses endpoints internes (`/_stcore/health`, `/_stcore/host-config`) et retourne des erreurs 404.

### 3. Variables d'environnement (.env)

```env
# Désactiver l'auth interne (Caddy gère l'authentification)
AUTH_DISABLED=false

# Activer uniquement le mode proxy
AUTH_PROVIDERS=proxy
AUTH_PROXY_ENABLED=true

# Headers injectés par AuthCrunch (inject headers with claims)
AUTH_PROXY_EMAIL_HEADER=X-Token-User-Email
AUTH_PROXY_NAME_HEADER=X-Token-User-Name

# URL de déconnexion → portail AuthCrunch
AUTH_PROXY_LOGOUT_URL=https://auth.example.com/logout
```

### 4. Caddyfile

Le fichier complet est dans `docs/Caddyfile`. Points clés :

```caddy
security {
    authorization policy admin_policy {
        crypto key verify {env.JWT_SHARED_KEY}

        # Injecter les claims JWT comme headers HTTP
        inject headers with claims

        acl rule {
            match role authp/user
            allow stop log info
        }
    }
}

*.internal.example.com {
    @kidsearch-admin host kidsearch-admin.internal.example.com
    handle @kidsearch-admin {
        authorize with admin_policy
        reverse_proxy http://kidsearch-all:8501 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-Proto https
        }
    }
}
```

**Headers injectés automatiquement par `inject headers with claims` :**
- `X-Token-User-Email` → Email de l'utilisateur
- `X-Token-User-Name` → Nom d'affichage
- `X-Token-Subject` → Identifiant (subject)
- `X-Token-User-Roles` → Rôles

Documentation AuthCrunch : https://docs.authcrunch.com/docs/authorize/headers

## Flux d'authentification

### Première connexion

```
1. User → https://kidsearch-admin.internal.example.com
2. Caddy vérifie le cookie AuthCrunch → absent
3. Caddy redirige vers le portail d'authentification
4. User s'authentifie (OIDC, OAuth, etc.)
5. AuthCrunch génère un cookie de session signé
6. Caddy injecte les headers : X-Token-User-Email, X-Token-User-Name
7. Dashboard Streamlit lit les headers → utilisateur identifié
```

### Visites suivantes

```
1. User → https://kidsearch-admin.internal.example.com
2. Caddy vérifie le cookie AuthCrunch → valide
3. Caddy injecte les headers
4. Dashboard affiche l'interface directement
```

## Dépannage

### Erreurs 404 sur `/_stcore/health` et `/_stcore/host-config`

**Cause :** Fichier `.streamlit/config.toml` manquant.  
**Solution :** Créer le fichier avec `headless = true`, `enableCORS = false`, `enableXsrfProtection = false`.

### Erreur DNS `no such host` dans les logs Caddy

**Cause :** Le container `kidsearch-all` n'est pas sur le même réseau Docker que Caddy.  
**Solution :** Ajouter `caddy-network` aux réseaux de `kidsearch-all` dans `compose.yaml`.

### Headers non reçus par le dashboard

Vérifier que `inject headers with claims` est présent dans la politique d'autorisation AuthCrunch.

### Déconnexion ne fonctionne pas

Vérifier que `AUTH_PROXY_LOGOUT_URL` pointe vers l'endpoint de déconnexion du portail AuthCrunch (ex: `https://auth.example.com/logout`).

## Ressources

- [AuthCrunch - HTTP Headers](https://docs.authcrunch.com/docs/authorize/headers)
- [AuthCrunch - Authorization Policy](https://docs.authcrunch.com/docs/authorize/policy)
- [Streamlit - Behind a reverse proxy](https://docs.streamlit.io/deploy/tutorials/docker)
