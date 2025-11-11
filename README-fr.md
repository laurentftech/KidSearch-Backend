# API KidSearch & Meilisearch Crawler

Ce projet fournit une solution backend complète pour un moteur de recherche sécurisé comme [KidSearch](https://github.com/laurentftech/kidsearch). Il se compose de deux éléments principaux :

1.  Un **Serveur API KidSearch** : Un serveur basé sur FastAPI qui effectue des recherches fédérées sur plusieurs sources (Meilisearch local, Google, Wikipedia) et utilise un modèle local pour reclasser sémantiquement les résultats.
2.  Un **Crawler Meilisearch** : Un crawler web asynchrone et performant qui peuple l'instance Meilisearch locale avec du contenu provenant de sites web, d'API JSON et de sites MediaWiki.

Cette combinaison crée un backend de recherche puissant et flexible, capable de fournir des résultats pertinents et sûrs.

## ✨ Fonctionnalités

### Serveur API KidSearch
- **Backend FastAPI**: Un serveur d'API léger et performant pour exposer les fonctionnalités de recherche.
- **Recherche Fédérée**: Agrège en temps réel les résultats de plusieurs sources : l'index Meilisearch local, Google Custom Search (GSE) et les API Wikipedia/Vikidia.
- **Reclassement Hybride Optimisé**: Récupère les résultats de toutes les sources, calcule les embeddings manquants à la volée, puis utilise un modèle *cross-encoder* local pour reclasser intelligemment la liste combinée en fonction de la pertinence sémantique. Cette approche garantit que le meilleur contenu est toujours priorisé avec une latence minimale.
- **Prêt pour la Production**: Peut être facilement déployé en tant que conteneur Docker.

### Cœur du Crawler
- **Asynchrone & Parallèle**: Conçu avec `asyncio` et `aiohttp` pour un crawl simultané à haute vitesse.
- **Sources Flexibles**: Prend en charge nativement le crawl de sites web HTML, d'API JSON et de sites sous MediaWiki (comme Wikipedia ou Vikidia).
- **Crawl Incrémentiel**: Utilise un cache local pour ne réindexer que les pages qui ont changé depuis le dernier crawl, économisant temps et ressources.
- **Reprise du Crawl**: Si un crawl est interrompu, il peut être repris sans effort.
- **Extraction de Contenu Intelligente**: Utilise `trafilatura` pour une détection robuste du contenu principal depuis le HTML.
- **Respect de `robots.txt`**: Suit les protocoles d'exclusion standards.
- **Exploration en Profondeur (Depth-First)**: Priorise l'exploration des liens nouvellement découverts pour explorer plus profondément la structure d'un site.

### Recherche & Indexation
- **Prêt pour la Recherche Sémantique**: Peut générer et indexer des vecteurs d'embeddings en utilisant Google Gemini ou un modèle HuggingFace local.
- **Gestion de Quota Intelligente**: Détecte automatiquement lorsque le quota de l'API Gemini est dépassé et arrête le crawl proprement.

### Supervision & Contrôle
- **Tableau de Bord Interactif**: Une interface web basée sur Streamlit pour surveiller, contrôler et configurer le crawler en temps réel.
- **CLI Avancée**: Options de ligne de commande puissantes pour un contrôle précis.

![screenshot_dashboard.png](media/screenshot_dashboard_fr.png)

## Prérequis

- Python 3.8+
- Une instance Meilisearch en cours d'exécution (v1.0 ou supérieure).
- Une clé API Google Gemini (si vous utilisez la fonction d'embeddings).

## 1. Configuration de Meilisearch

Ce crawler a besoin d'une instance Meilisearch pour y envoyer ses données. La manière la plus simple d'en obtenir une est avec Docker.

1.  **Installez Meilisearch**: Suivez le [guide de démarrage rapide officiel de Meilisearch](https://www.meilisearch.com/docs/learn/getting_started/quick_start).
2.  **Lancez Meilisearch avec une clé principale**:
    ```bash
    docker run -it --rm \
      -p 7700:7700 \
      -e MEILI_MASTER_KEY='une_cle_maitre_longue_et_securisee' \
      -v $(pwd)/meili_data:/meili_data \
      ghcr.io/meilisearch/meilisearch:latest
    ```
3.  **Obtenez votre URL et votre clé API**:
    -   **URL**: `http://localhost:7700`
    -   **Clé API**: La `MEILI_MASTER_KEY` que vous avez définie.

## 2. Configuration du Crawler

1.  **Clonez le dépôt**:
    ```bash
    git clone https://github.com/laurentftech/MeilisearchCrawler.git
    cd MeilisearchCrawler
    ```

2.  **Créez et activez un environnement virtuel**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Installez les dépendances**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurez les variables d'environnement**:
    Copiez le fichier d'exemple et modifiez-le avec vos informations.
    ```bash
    cp .env.example .env
    ```
    Maintenant, ouvrez `.env` et remplissez :
    - `MEILI_URL`: L'URL de votre instance Meilisearch.
    - `MEILI_KEY`: Votre clé principale Meilisearch.
    - `GEMINI_API_KEY`: Votre clé API Google Gemini (optionnelle, mais requise pour l'option `--embeddings`).

5.  **Configurez les sites à crawler**:
    Copiez le fichier d'exemple des sites.
    ```bash
    cp config/sites.yml.example config/sites.yml
    ```
    Vous pouvez maintenant modifier `config/sites.yml` pour ajouter les sites que vous souhaitez indexer.

## 3. Lancer l'Application

Le projet peut être exécuté selon différents modes : crawler, serveur API ou tableau de bord.

> 📖 **Documentation complète de l'API disponible ici :** [API_README_FR.md](API_README_FR.md)

### Crawler (Ligne de Commande)

Exécutez le script `crawler.py` pour démarrer l'indexation du contenu.

```sh
python crawler.py # Lance un crawl incrémentiel sur tous les sites
```

**Options courantes:**

-   `--force`: Force une réindexation complète de toutes les pages, en ignorant le cache.
-   `--site "Nom du Site"`: N'explore que le site spécifié.
-   `--embeddings`: Active la génération d'embeddings Gemini pour la recherche sémantique.
-   `--workers N`: Définit le nombre de requêtes parallèles (ex: `--workers 10`).
-   `--stats-only`: Affiche les statistiques du cache sans lancer de crawl.

**Exemple:**
```sh
# Force une réindexation de "Vikidia" avec les embeddings activés
python crawler.py --force --site "Vikidia" --embeddings
```

### Serveur API KidSearch

Exécutez le script `api.py` pour démarrer le serveur FastAPI, qui expose le point de terminaison de recherche.

```sh
python api.py
```
L'API sera disponible à l'adresse `http://localhost:8000`. Vous pouvez accéder à la documentation interactive à l'adresse `http://localhost:8000/docs`.

### Tableau de Bord Interactif

Le projet inclut un tableau de bord web pour surveiller et contrôler le crawler en temps réel.

**Comment le lancer:**

1.  Depuis la racine du projet, exécutez la commande suivante:
    ```bash
    streamlit run dashboard/dashboard.py
    ```
2.  Ouvrez votre navigateur web à l'URL locale fournie par Streamlit (généralement `http://localhost:8501`).

**Fonctionnalités:**

-   **🏠 Vue d'ensemble**: Un résumé en temps réel du crawl en cours.
-   **🔧 Contrôles**: Démarrez ou arrêtez le crawler, sélectionnez des sites, forcez une réindexation et gérez les embeddings.
-   **🔍 Recherche**: Une interface pour tester des requêtes directement sur votre index Meilisearch.
-   **📊 Statistiques**: Des statistiques détaillées sur votre index Meilisearch.
-   **🌳 Arbre des Pages**: Une visualisation interactive de la structure de votre site.
-   **⚙️ Configuration**: Un éditeur interactif pour le fichier `sites.yml`.
-   **🪵 Logs**: Une vue en direct du fichier de log du crawler.
-   **📈 Métriques de l'API**: Un tableau de bord pour surveiller les performances et les métriques de l'API.

## 4. Configuration de `sites.yml`

Le fichier `config/sites.yml` vous permet de définir une liste de sites à crawler. Chaque site est un objet avec les propriétés suivantes:

- `name`: (String) Le nom du site, utilisé pour le filtrage dans Meilisearch.
- `crawl`: (String) L'URL de départ pour le crawl.
- `type`: (String) Le type de contenu. Peut être `html`, `json`, ou `mediawiki`.
- `max_pages`: (Integer) Le nombre maximum de pages à crawler. Mettre `0` ou omettre pour ne pas avoir de limite.
- `depth`: (Integer) Pour les sites `html`, la profondeur maximale pour suivre les liens.
- `delay`: (Float, optionnel) Un délai spécifique en secondes entre les requêtes pour ce site, ignorant le délai par défaut. Utile pour les serveurs sensibles.
- `selector`: (String, optionnel) Pour les sites `html`, un sélecteur CSS spécifique (ex: `.main-article`) pour cibler le contenu principal.
- `lang`: (String, optionnel) Pour les sources `json`, spécifie la langue du contenu (ex: "fr").
- `exclude`: (Liste de chaînes) Une liste de motifs d'URL à ignorer complètement.
- `no_index`: (Liste de chaînes) Une liste de motifs d'URL à visiter pour découvrir des liens mais à ne pas indexer.

### Type `html`
C'est le type standard pour crawler des sites web classiques. Le crawler commencera à l'URL `crawl` et suivra les liens jusqu'à la `depth` spécifiée.

### Type `json`
Pour ce type, vous devez fournir un objet `json` avec le mappage suivant:
- `root`: La clé dans la réponse JSON qui contient la liste des éléments.
- `title`: La clé du titre de l'élément.
- `url`: Un modèle pour l'URL de l'élément. Vous pouvez utiliser `{{nom_de_la_cle}}` pour substituer une valeur de l'élément.
- `content`: Une liste de clés séparées par des virgules pour le contenu.
- `image`: La clé de l'URL de l'image principale.

### Type `mediawiki`
Ce type est optimisé pour les sites utilisant le logiciel MediaWiki (comme Wikipedia, Vikidia). Il utilise l'API MediaWiki pour récupérer efficacement toutes les pages, évitant un crawl lien par lien.
- L'URL `crawl` doit être l'URL de base du wiki (ex: `https://fr.vikidia.org`).
- `depth` et `selector` ne sont pas utilisés pour ce type.

## 5. Authentification du Tableau de Bord

Le tableau de bord prend en charge plusieurs méthodes d'authentification. Vous pouvez en activer une ou plusieurs.

### Choix des Fournisseurs d'Authentification

La variable d'environnement `AUTH_PROVIDERS` contrôle les méthodes d'authentification activées.

-   **Configuration Explicite (Recommandé)** : Pour éviter toute ambiguïté, listez explicitement les fournisseurs que vous souhaitez utiliser.
    ```bash
    # Exemple : Activer le Proxy et le Mot de passe simple
    AUTH_PROVIDERS=proxy,simple
    ```
    -   Pour n'utiliser **qu'une seule méthode** (comme le proxy), définissez-la comme unique fournisseur :
        ```bash
        # Forcer UNIQUEMENT l'authentification par proxy
        AUTH_PROVIDERS=proxy
        ```

-   **Détection Automatique** : Si `AUTH_PROVIDERS` est laissé vide, l'application activera automatiquement tout fournisseur dont les variables d'environnement correspondantes sont définies. C'est utile pour les tests mais déconseillé en production, car cela pourrait activer plus de méthodes que prévu.

### 🛡️ Authentification par Proxy (Recommandé pour la Production)

C'est la méthode la plus sécurisée et flexible. Elle délègue l'authentification à un reverse proxy (comme Caddy avec AuthCrunch) qui gère l'authentification des utilisateurs.

**Comment ça marche :**
1. Le proxy (Caddy avec AuthCrunch) authentifie l'utilisateur via OIDC.
2. AuthCrunch injecte automatiquement les informations utilisateur dans les en-têtes HTTP via la directive `inject headers with claims`.
3. Le tableau de bord lit ces en-têtes pour identifier l'utilisateur authentifié.
4. Le tableau de bord appelle l'API pour générer un token JWT pour les requêtes API ultérieures.

Cette méthode est hautement sécurisée car elle empêche l'accès direct au tableau de bord et s'appuie sur les mécanismes d'authentification du proxy.

**Configuration (`.env`):**
```bash
# Forcer le proxy comme seule méthode d'authentification
AUTH_PROVIDERS=proxy

# Activer l'authentification par proxy
AUTH_PROXY_ENABLED=true

# URL de redirection lors de la déconnexion (par ex. le point de terminaison de déconnexion du proxy)
AUTH_PROXY_LOGOUT_URL=/

# Secret JWT pour l'authentification API (générer avec la commande ci-dessous)
JWT_SECRET_KEY=votre_secret_jwt_ici

# URL de l'API pour la communication Dashboard vers API
API_URL=http://kidsearch-all:8080/api
```

**Comment Générer le Secret JWT :**
```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Ou utilisez le script fourni :
```sh
python scripts/generate_secrets.py
```

**Exemple avec Caddy & AuthCrunch:**
```caddy
{
    security {
        authorization policy admin_only {
            set auth url https://auth.example.com
            allow roles authp/admin
            crypto key verify {env.JWT_SECRET_KEY}

            # IMPORTANT: Cette directive injecte les claims utilisateur dans les en-têtes HTTP
            inject headers with claims
        }
    }
}

# === TABLEAU DE BORD KIDSEARCH ===
https://kidsearch-admin.example.com {
    # 1. Autoriser l'utilisateur avec AuthCrunch
    authorize with admin_only

    # 2. Configurer la journalisation
    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    # 3. Reverse proxy vers le tableau de bord
    # AuthCrunch injecte automatiquement ces en-têtes :
    # - X-Token-User-Email
    # - X-Token-User-Name
    # - X-Token-Subject
    # - X-Token-User-Roles
    reverse_proxy kidsearch-all:8501 {
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

**Documentation:**
- Exemple complet de Caddyfile : `docs/Caddyfile`
- Guide complet : `docs/AUTHENTICATION_FINAL.md`
- Checklist de déploiement : `docs/DEPLOYMENT_CHECKLIST.md`

### 🧩 OIDC, Google, GitHub & Mot de Passe Simple

Vous pouvez également activer d'autres fournisseurs. Si plusieurs sont activés via `AUTH_PROVIDERS`, les utilisateurs verront un écran de sélection.

- **OIDC** : `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`
- **Google** : `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
- **GitHub** : `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`
- **Mot de passe simple** : `DASHBOARD_PASSWORD`

### Liste d'Emails Autorisés

La variable `ALLOWED_EMAILS` restreint l'accès pour les méthodes OAuth et Proxy :
- Si vide : tous les utilisateurs authentifiés peuvent accéder.
- Si définie : seuls les emails listés peuvent accéder au tableau de bord.
```bash
ALLOWED_EMAILS=utilisateur1@gmail.com,utilisateur2@exemple.com
```

### Diagnostic des Problèmes d'Authentification

Si vous rencontrez des difficultés avec la connexion, utilisez les outils de diagnostic :

**1. Vérifiez votre configuration :**
```bash
python3 check_auth_config.py
```

**2. Testez un email spécifique :**
```bash
python3 check_auth_config.py utilisateur@exemple.com
```

**3. Surveillez les logs d'authentification :**
```bash
tail -f data/logs/auth.log
```
Les logs afficheront les connexions réussies ✅ et échouées ❌ avec des raisons détaillées.

## 6. Lancer les Tests

Pour exécuter la suite de tests, installez d'abord les dépendances de développement:

```bash
pip install pytest
```

Ensuite, lancez les tests:
```bash
pytest
```
