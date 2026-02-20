# Streamlit + authcrunch : Gestion des endpoints `/_stcore/*`

## 🔍 Le problème

Lorsque vous utilisez Streamlit derrière authcrunch (Caddy), vous verrez ces erreurs dans les logs :

```
2025/11/11 21:00:56.298 ERROR   http.handlers.authentication    auth provider returned error
{"provider": "authorizer", "error": "user authorization failed: src_ip=10.0.0.5,
 src_conn_ip=192.168.240.1, reason: no token found"}

not authenticated {"uri": "/_stcore/health"}
not authenticated {"uri": "/_stcore/host-config"}
```

## 🎯 Pourquoi ça arrive ?

### Architecture Streamlit

Streamlit utilise des **endpoints internes** pour son fonctionnement :

| Endpoint | Rôle | Contenu |
|----------|------|---------|
| `/_stcore/health` | Healthcheck de l'application | `{"ok": true}` |
| `/_stcore/host-config` | Configuration client | Paramètres JS du client |
| `/_stcore/stream` | WebSocket pour les updates | Données d'interface |
| `/_stcore/allowed-message-origins` | CORS | Liste des origines autorisées |
| `/_stcore/static/*` | Assets statiques | CSS, JS, images |

### Le conflit avec authcrunch

1. **Streamlit** fait des requêtes AJAX/fetch vers ces endpoints
2. Ces requêtes sont faites depuis le **JavaScript côté client**
3. Elles ne transmettent **pas toujours** les cookies de session de manière fiable
4. **authcrunch** bloque → 401 Unauthorized
5. Les logs se remplissent d'erreurs `"no token found"`

**Impact:**
- ❌ Logs pollués avec des faux positifs
- ❌ Possibles problèmes d'affichage (Streamlit pense que l'app est down)
- ❌ Requêtes inutiles vers le portail d'authentification

## ⚠️ Limitation avec authcrunch

**IMPORTANT**: La solution avec `handle` séparés **ne fonctionne pas correctement** avec authcrunch car les headers ne sont pas injectés dans le bon contexte.

**Recommandation**: Acceptez les erreurs `/_stcore/*` dans les logs - elles sont **bénignes** et n'affectent pas le fonctionnement de l'application.

## ✅ La solution (si vraiment nécessaire)

### Principe

~~Utiliser les **matchers et routes** de Caddy pour :
- Exclure `/_stcore/*` de l'authentification
- Garder tout le reste protégé~~

**Note**: Cette approche ne fonctionne pas bien avec authcrunch. Voir "Recommandation" ci-dessus.

### Configuration Caddyfile

```caddy
https://kidsearch-admin.gandulf78.synology.me {
    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    # ========================================
    # Matcher pour les endpoints internes Streamlit
    # ========================================
    @streamlit_internal {
        path /_stcore/*
    }

    # ========================================
    # Route 1: Healthchecks Streamlit (SANS authentification)
    # ========================================
    # Ces endpoints sont techniques et ne contiennent pas de données sensibles
    # Streamlit les appelle via AJAX qui peut ne pas inclure les cookies
    handle @streamlit_internal {
        reverse_proxy kidsearch-all:8501 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}

            # Support WebSocket
            header_up Connection {>Connection}
            header_up Upgrade {>Upgrade}
        }
    }

    # ========================================
    # Route 2: Tout le reste (AVEC authentification)
    # ========================================
    # Le contenu réel de l'application reste protégé
    handle {
        authorize with admin_only

        reverse_proxy kidsearch-all:8501 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}

            # Support WebSocket
            header_up Connection {>Connection}
            header_up Upgrade {>Upgrade}
        }
    }
}
```

### Avec vos snippets existants

Si vous utilisez des snippets comme `common_reverse_proxy` et `websocket_support`:

```caddy
http://kidsearch-admin.gandulf78.synology.me {
    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    @streamlit_internal {
        path /_stcore/*
    }

    # Healthchecks sans auth
    handle @streamlit_internal {
        reverse_proxy kidsearch-all:8501 {
            import common_reverse_proxy
            import websocket_support
        }
    }

    # Tout le reste avec auth
    handle {
        authorize with admin_only

        reverse_proxy kidsearch-all:8501 {
            import common_reverse_proxy
            import websocket_support
        }
    }
}
```

## 🎯 Configuration recommandée (SIMPLE avec filtrage de logs)

**Solution propre** : Configuration simple avec `log_skip` pour filtrer les endpoints `/_stcore/*` :

```caddy
http://kidsearch-admin.gandulf78.synology.me {
    authorize with admin_only

    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    # Matcher pour identifier les endpoints Streamlit internes
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

**Pourquoi c'est la meilleure solution:**
- ✅ L'application fonctionne parfaitement
- ✅ authcrunch injecte correctement les headers pour tout le reste
- ✅ **Plus d'ERROR rouges dans les logs pour `/_stcore/*`**
- ✅ Configuration simple (pas de `handle` complexes)
- ✅ Les vrais problèmes restent visibles dans les logs

**Alternative sans filtrage de logs:**

Si vous préférez voir tous les logs (y compris les erreurs cosmétiques) :

```caddy
http://kidsearch-admin.gandulf78.synology.me {
    authorize with admin_only

    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    reverse_proxy kidsearch-all:8501 {
        import common_reverse_proxy
        import websocket_support
    }
}
```

Vous pourrez ensuite filtrer à la lecture :
```bash
tail -f /data/logs/kidsearch-dashboard-access.log | grep -v "_stcore"
```

## 🔒 Sécurité : Est-ce sûr ?

### ✅ OUI, parce que :

1. **Pas de données sensibles** dans `/_stcore/*`
   ```
   GET /_stcore/health
   → {"ok": true}

   GET /_stcore/host-config
   → {"allowedOrigins": [...], "useExternalAuthToken": false}
   ```

2. **Le contenu réel est protégé**
   - `/` → Page principale → **Authentification requise** ✅
   - `/api/search` → Données → **Authentification requise** ✅
   - Toutes les pages Streamlit → **Authentification requise** ✅

3. **Même principe que les assets statiques**
   - C'est équivalent à servir `/favicon.ico` ou `/robots.txt` sans auth
   - Les données dynamiques restent protégées

### ⚠️ Ce qui EST exposé (sans risque)

- Status de santé de l'application
- Configuration JavaScript côté client (pas de secrets)
- Assets statiques (CSS, JS, images)

### 🔐 Ce qui RESTE protégé

- Toutes les pages de l'application
- Les données des utilisateurs
- L'API backend
- Les endpoints sensibles

## 🧪 Vérification

Après avoir appliqué la configuration :

### 1. Redémarrez Caddy

```bash
docker-compose restart caddy
# ou
systemctl reload caddy
```

### 2. Vérifiez les endpoints

```bash
# Healthcheck SANS auth (doit fonctionner)
curl -v https://kidsearch-admin.gandulf78.synology.me/_stcore/health
# → 200 OK {"ok": true}

# Page principale AVEC auth (doit rediriger)
curl -v https://kidsearch-admin.gandulf78.synology.me/
# → 302 Found (redirige vers portail auth)
```

### 3. Surveillez les logs

```bash
# Plus d'erreurs "no token found" pour /_stcore/*
docker-compose logs -f caddy | grep -i "/_stcore"

# Devrait montrer 200 OK au lieu de 401
tail -f /data/logs/kidsearch-dashboard-access.log | grep _stcore
```

## 📊 Résultat attendu

**AVANT** (avec auth sur `/_stcore/*`):
```
2025/11/11 21:00:56.298 ERROR   no token found   {"uri": "/_stcore/health"}
2025/11/11 21:00:56.299 DEBUG   redirecting unauthorized user
2025/11/11 21:00:56.300 ERROR   no token found   {"uri": "/_stcore/host-config"}
2025/11/11 21:00:56.301 DEBUG   redirecting unauthorized user
```

**APRÈS** (sans auth sur `/_stcore/*`):
```
2025/11/11 21:10:00.100 INFO    GET /_stcore/health 200 OK
2025/11/11 21:10:00.101 INFO    GET /_stcore/host-config 200 OK
```

## 🔗 Ressources

- [Streamlit server endpoints](https://docs.streamlit.io/)
- [Caddy matchers](https://caddyserver.com/docs/caddyfile/matchers)
- [authcrunch documentation](https://docs.authcrunch.com/)

## ❓ FAQ

### Q: Pourquoi ne pas mettre une IP whitelist sur `/_stcore/*` ?

**R:** Pas nécessaire car :
- Ces endpoints ne contiennent pas de données sensibles
- Streamlit les appelle depuis le navigateur client (pas depuis le réseau Docker)
- Ça compliquerait la config sans gain de sécurité

### Q: Est-ce que `/_stcore/stream` (WebSocket) est aussi concerné ?

**R:** Oui, mais le WebSocket établit une connexion persistante après l'auth initiale. Si vous avez des problèmes, ajoutez-le au matcher :
```caddy
@streamlit_internal {
    path /_stcore/*
}
```

### Q: Peut-on limiter par User-Agent pour ne servir que Streamlit ?

**R:** Techniquement oui, mais c'est facile à contourner et n'apporte rien :
```caddy
@streamlit_internal {
    path /_stcore/*
    header User-Agent *streamlit*
}
```
Mais ce n'est pas recommandé (complexité inutile).

### Q: Et si je veux vraiment logger les accès à `/_stcore/*` ?

**R:** Les logs sont toujours écrits ! Simplement ils montrent 200 OK au lieu de 401 :
```bash
tail -f /data/logs/kidsearch-dashboard-access.log | grep _stcore
# 2025/11/11 21:00:00 GET /_stcore/health 200 OK 0.001s
```

## ✅ Checklist de déploiement

- [ ] Modifier le Caddyfile avec le matcher `@streamlit_internal`
- [ ] Ajouter le `handle @streamlit_internal` sans auth
- [ ] Garder le `handle` par défaut avec `authorize with admin_only`
- [ ] Redémarrer Caddy
- [ ] Vérifier que `/_stcore/health` retourne 200 OK
- [ ] Vérifier que `/` redirige toujours vers l'auth
- [ ] Vérifier que les logs ne montrent plus d'erreurs "no token found"
