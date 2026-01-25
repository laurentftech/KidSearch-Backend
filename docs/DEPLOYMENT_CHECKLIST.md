# Checklist de déploiement - Authentification Proxy

Cette checklist vous guide pas à pas pour déployer KidSearch avec l'authentification via Caddy + authcrunch.

> 📖 **Documentation complète**: Voir [AUTHENTICATION_FINAL.md](./AUTHENTICATION_FINAL.md)

---

## ✅ Étape 1: Générer le secret JWT

```bash
cd /path/to/KidSearch
python scripts/generate_secrets.py
```

Ce script génère:
- `JWT_SECRET_KEY` - Secret pour signer les JWT de l'API

**Important**: Notez ce secret, vous en aurez besoin dans Caddy ET dans l'application !

**Alternative manuelle**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## ✅ Étape 2: Configurer les variables d'environnement

### Dans votre `.env`

```env
# === AUTHENTIFICATION PROXY ===
AUTH_PROXY_ENABLED=true
AUTH_PROVIDERS=proxy
AUTH_PROXY_LOGOUT_URL=/

# === JWT (IMPORTANT: doit être identique dans Caddy) ===
JWT_SECRET_KEY=<votre_secret_genere>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# === API ===
API_URL=http://kidsearch-all:8080/api
API_ENABLED=true
API_WORKERS=2

# === OIDC (pour authcrunch dans Caddy) ===
OIDC_ISSUER=https://pocket-id.gandulf78.synology.me
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret

# === EMAILS AUTORISÉS (optionnel) ===
ALLOWED_EMAILS=laurent@example.com,user@example.com

# === MEILISEARCH ===
TYPESENSE_URL=http://meilisearch:8108
TYPESENSE_API_KEY=masterKey
INDEX_NAME=kidsearch
```

### Vérification du .env

- [ ] `JWT_SECRET_KEY` est renseigné (64 caractères hex)
- [ ] `AUTH_PROXY_ENABLED=true`
- [ ] `AUTH_PROVIDERS=proxy`
- [ ] `OIDC_ISSUER` pointe vers votre provider OIDC
- [ ] `OIDC_CLIENT_ID` et `OIDC_CLIENT_SECRET` sont configurés (pour Caddy)
- [ ] `ALLOWED_EMAILS` contient les emails autorisés (optionnel)
- [ ] `API_URL` est correct (`http://kidsearch-all:8080/api` en Docker)

---

## ✅ Étape 3: Configurer Caddy

### Utiliser le Caddyfile d'exemple

Le fichier complet est dans `docs/Caddyfile`. Adaptez-le à votre configuration.

### Adapter le Caddyfile

Modifiez les domaines:
- `auth.gandulf78.synology.me` → votre domaine auth
- `kidsearch-admin.gandulf78.synology.me` → votre domaine dashboard
- `kidsearch-api.gandulf78.synology.me` → votre domaine API (optionnel)

### Configurer les variables d'environnement de Caddy

**IMPORTANT**: Caddy authcrunch a besoin de `OIDC_CLIENT_SECRET` (configuré dans Pocket ID) pour signer/vérifier ses cookies.

Dans votre docker-compose pour Caddy ou en variables d'environnement système:

```yaml
environment:
  - OIDC_CLIENT_ID=<votre client ID>
  - OIDC_CLIENT_SECRET=<votre client secret de Pocket ID>
  - OIDC_ISSUER=https://pocket-id.gandulf78.synology.me
```

**Note**: `JWT_SECRET_KEY` est utilisé UNIQUEMENT par l'API KidSearch (dans `.env`), **PAS par Caddy**.

### Point clé du Caddyfile

Assurez-vous que votre policy d'autorisation contient:

```caddy
authorization policy admin_only {
    set auth url https://auth.gandulf78.synology.me
    allow roles authp/admin authp/user
    crypto key verify {env.OIDC_CLIENT_SECRET}

    # CLEF: Injecter les claims JWT dans les headers HTTP
    inject headers with claims
}
```

### Vérification Caddy

- [ ] `OIDC_CLIENT_SECRET` est configuré (depuis Pocket ID)
- [ ] Les domaines sont corrects
- [ ] OIDC est configuré (client_id, client_secret, issuer)
- [ ] La directive `inject headers with claims` est présente
- [ ] Les emails/rôles autorisés sont configurés dans la policy

---

## ✅ Étape 4: Vérifier les fichiers du projet

### Backend API

- [x] `meilisearchcrawler/api/routes/auth.py` - Route POST `/auth/token/headers`
- [x] `meilisearchcrawler/api/auth.py` - JWT handler
- [x] `meilisearchcrawler/auth_config.py` - Configuration proxy
- [x] `meilisearchcrawler/session_manager.py` - Gestionnaire de sessions

### Dashboard

- [x] `dashboard/src/auth.py` - Lecture des headers + JWT
- [x] `dashboard/src/api_client.py` - Client API avec JWT

### Configuration

- [x] `.env.example` - Documentation
- [x] `docker-compose.yml` - Variables d'environnement

---

## ✅ Étape 5: Build et déploiement Docker

### Build l'image

```bash
docker-compose build kidsearch-all
```

### Test en local (sans Caddy)

Pour tester sans Caddy:

```bash
# Désactiver le proxy auth temporairement
export AUTH_PROXY_ENABLED=false
export AUTH_PROVIDERS=simple
export DASHBOARD_PASSWORD=test123

docker-compose up -d
```

Accédez à `http://localhost:8501` et testez l'authentification simple.

### Déploiement complet (avec Caddy)

```bash
# Réactiver le proxy auth
export AUTH_PROXY_ENABLED=true
export AUTH_PROVIDERS=proxy

# Démarrer tous les services
docker-compose up -d

# Démarrer Caddy (selon votre setup)
# Si Caddy est dans le même docker-compose:
# Les services devraient démarrer ensemble
```

### Vérification des logs

```bash
# Logs Dashboard
docker-compose logs -f kidsearch-all | grep -i auth

# Logs Caddy
docker-compose logs -f caddy | grep -i auth

# Logs fichiers
tail -f data/logs/auth.log
tail -f /data/logs/kidsearch-dashboard-access.log  # selon config Caddy
```

---

## ✅ Étape 6: Test de l'authentification

### Test du flux complet

1. **Accéder au Dashboard via Caddy**
   - Ouvrez `https://kidsearch-admin.gandulf78.synology.me`
   - Vous devriez être redirigé vers `https://auth.gandulf78.synology.me`

2. **S'authentifier**
   - Connectez-vous via votre provider OIDC
   - Vous devriez être redirigé vers le dashboard
   - **Pas de query parameters** dans l'URL (grâce à `inject headers with claims`)

3. **Vérifier l'authentification**
   - Le dashboard doit afficher votre nom et email
   - Vérifiez localStorage: doit contenir `auth_token` (JWT)
   - L'URL doit être propre (juste `/`)

4. **Tester l'API**
   ```bash
   # Récupérer le JWT depuis localStorage (dans le navigateur)
   # Ouvrir Console développeur > Application > Local Storage
   # puis tester:
   curl -H "Authorization: Bearer <votre_jwt>" \
        https://kidsearch-api.gandulf78.synology.me/health
   ```

5. **Rafraîchir la page**
   - Le JWT doit être persisté
   - Pas de nouvelle authentification nécessaire

6. **Se déconnecter**
   - Cliquer sur "Déconnexion"
   - Vous devriez être redirigé vers la page d'authentification

### Vérifications dans les logs

```bash
# Le Dashboard doit logger:
grep "Authenticated via proxy" data/logs/auth.log

# L'API doit logger:
grep "JWT token issued" data/logs/auth.log
```

---

## ✅ Étape 7: Sécurité finale

### Checklist sécurité

- [ ] `JWT_SECRET_KEY` est un secret fort (64+ caractères hex) - pour l'API KidSearch
- [ ] `OIDC_CLIENT_SECRET` est configuré (depuis Pocket ID) - pour Caddy authcrunch
- [ ] Les secrets ne sont PAS committés dans Git
- [ ] `.env` et `.env.secrets` sont dans `.gitignore`
- [ ] HTTPS est activé (Caddy le fait automatiquement)
- [ ] `ALLOWED_EMAILS` est configuré pour restreindre l'accès
- [ ] Les logs sont en place pour l'audit
- [ ] Le réseau Docker empêche l'accès direct à l'API depuis Internet

### Recommandations

- **Rotation des secrets**: Changez le secret régulièrement (tous les 3-6 mois)
- **Monitoring**: Surveillez les logs pour détecter les tentatives d'accès non autorisées
- **Backup**: Sauvegardez votre secret de manière sécurisée (gestionnaire de mots de passe)

---

## 🔧 Dépannage

### Problème: Headers non reçus

**Cause**: La directive `inject headers with claims` n'est pas configurée

**Solution**:
1. Vérifiez que votre policy d'autorisation contient `inject headers with claims`
2. Redémarrez Caddy
3. Vérifiez les logs: `data/logs/auth.log`

```bash
# Vérifier les logs du Dashboard
grep "X-Token-User-Email" data/logs/auth.log
```

### Problème: Erreurs "no token found" pour `/_stcore/*` dans les logs

**Symptôme**:
```
ERROR http.handlers.authentication auth provider returned error
{"provider": "authorizer", "error": "no token found"}
"uri": "/_stcore/health" ou "/_stcore/host-config"
```

**Cause**: Streamlit fait des requêtes AJAX vers ses endpoints techniques qui ne transmettent pas toujours les cookies authcrunch.

**Solution recommandée**: Utiliser `log_skip` pour filtrer ces erreurs des logs. Modifiez votre Caddyfile:

```caddy
http://kidsearch-admin.gandulf78.synology.me {
    authorize with admin_only

    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    # Matcher pour Streamlit healthchecks
    @streamlit_healthcheck {
        path /_stcore/*
    }

    # Filtrer ces requêtes des logs pour éviter les ERROR rouges
    log_skip @streamlit_healthcheck

    reverse_proxy kidsearch-all:8501 {
        import common_reverse_proxy
        import websocket_support
    }
}
```

**Avantages**:
- ✅ Pas d'ERROR rouges dans les logs pour les healthchecks bénins
- ✅ Configuration simple (pas de `handle` complexes qui cassent l'injection de headers)
- ✅ authcrunch injecte correctement les headers pour tout le reste

**Note de sécurité**: Les erreurs 401 se produisent toujours pour `/_stcore/*` (ce qui est normal), elles sont simplement filtrées des logs.

### Problème: JWT invalide (API KidSearch)

**Cause**: `JWT_SECRET_KEY` incorrect ou JWT expiré

**Solution**:
1. Vérifiez que `JWT_SECRET_KEY` est correctement configuré dans `.env`
2. Vérifiez l'expiration du JWT (défaut: 24h)
3. Effacez localStorage et reconnectez-vous

```bash
# Vérifier le secret dans l'application
docker-compose exec kidsearch-all env | grep JWT_SECRET_KEY
```

### Problème: Cookies authcrunch non acceptés

**Cause**: `OIDC_CLIENT_SECRET` incorrect dans Caddy

**Solution**:
1. Vérifiez que `OIDC_CLIENT_SECRET` dans Caddy correspond à celui de Pocket ID
2. Redémarrez Caddy après modification

```bash
# Vérifier le secret dans Caddy
docker-compose exec caddy env | grep OIDC_CLIENT_SECRET
```

### Problème: 403 Forbidden

**Cause**: Email non autorisé

**Solution**:
1. Vérifiez `ALLOWED_EMAILS` dans `.env`
2. Vérifiez la configuration `allow email` dans Caddyfile
3. Vérifiez les logs: `data/logs/auth.log`

### Problème: API retourne 401

**Cause**: JWT non envoyé ou invalide

**Solution**:
1. Vérifiez que le JWT est dans localStorage
2. Utilisez `api_client.py` pour les requêtes (ajoute automatiquement le header)
3. Testez manuellement avec curl:
   ```bash
   curl -H "Authorization: Bearer <jwt>" http://localhost:8080/api/health
   ```

### Problème: Erreur "No module named 'meilisearchcrawler.session_manager'"

**Cause**: Module manquant

**Solution**:
Le module `meilisearchcrawler/session_manager.py` doit exister. S'il est manquant, il sera créé automatiquement au premier démarrage.

---

## 📚 Ressources

- [Documentation complète](./AUTHENTICATION_FINAL.md)
- [Caddyfile d'exemple](./Caddyfile)
- [AuthCrunch - HTTP Headers](https://docs.authcrunch.com/docs/authorize/headers)
- [AuthCrunch - Token Verification](https://docs.authcrunch.com/docs/authorize/token-verification)
- [JWT.io](https://jwt.io/) - Décodeur JWT

---

## ✅ Validation finale

Avant de déployer en production:

- [ ] `JWT_SECRET_KEY` est généré et configuré (dans `.env` de l'application)
- [ ] `OIDC_CLIENT_SECRET` est configuré (dans Caddy, depuis Pocket ID)
- [ ] Les variables d'environnement sont complètes
- [ ] Caddy est configuré avec `inject headers with claims`
- [ ] L'image Docker est buildée
- [ ] Le flux d'authentification fonctionne en test
- [ ] Les logs sont propres (pas d'erreurs)
- [ ] HTTPS est activé
- [ ] La whitelist des emails est configurée
- [ ] Les secrets ne sont PAS dans Git

---

**Vous êtes prêt pour le déploiement ! 🚀**
