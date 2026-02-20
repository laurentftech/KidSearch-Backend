# GitHub Actions Workflows

Ce répertoire contient les workflows GitHub Actions pour le projet KidSearch.

## Workflows disponibles

### 1. Tests (`tests.yml`)

**Déclenché par:**
- Push sur `main` ou `develop`
- Pull requests vers `main` ou `develop`
- Manuellement via workflow_dispatch

**Actions:**
- Run tests sur Python 3.10, 3.11 et 3.12
- Vérification du code avec `ruff` (linter)
- Vérification de types avec `mypy`
- Génération de rapports de couverture
- Upload des résultats vers Codecov

**Badge de statut:**
```markdown
![Tests](https://github.com/VOTRE_USERNAME/KidSearch-Backend/actions/workflows/tests.yml/badge.svg)
```

### 2. Docker Build and Publish (`docker-build.yml`)

**Déclenché par:**
- Push sur `main` ou `develop`
- Tags `v*` (ex: `v1.0.0`)
- Pull requests
- Manuellement via workflow_dispatch

**Actions:**
1. **Test Job:**
   - Run tous les tests
   - Upload rapport de couverture

2. **Build and Push Job:**
   - Build l'image Docker multi-architecture (amd64, arm64)
   - Push vers GitHub Container Registry (ghcr.io)
   - Génération automatique de tags:
     - `latest` (branche main uniquement)
     - `main`, `develop` (selon la branche)
     - `v1.0.0`, `v1.0`, `v1` (pour les tags semver)
     - `main-abc123` (SHA du commit)

**Badge de statut:**
```markdown
![Docker](https://github.com/VOTRE_USERNAME/KidSearch-Backend/actions/workflows/docker-build.yml/badge.svg)
```

## Configuration requise

### Secrets GitHub

Aucun secret requis pour les fonctionnalités de base. Les secrets suivants sont optionnels:

- `CODECOV_TOKEN`: Pour uploader les rapports de couverture vers Codecov (optionnel)

### Permissions

Le workflow Docker nécessite les permissions suivantes (automatiquement configurées):
- `contents: read` - Lire le code
- `packages: write` - Publier sur GitHub Container Registry

## Utilisation

### Publier une nouvelle version

1. **Via Tag Git:**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

   Cela va créer les images:
   - `ghcr.io/VOTRE_USERNAME/meilisearchcrawler:v1.0.0`
   - `ghcr.io/VOTRE_USERNAME/meilisearchcrawler:v1.0`
   - `ghcr.io/VOTRE_USERNAME/meilisearchcrawler:v1`
   - `ghcr.io/VOTRE_USERNAME/meilisearchcrawler:latest` (si sur main)

2. **Build manuel:**
   - Aller sur Actions → Docker Build and Publish
   - Cliquer sur "Run workflow"
   - Sélectionner la branche
   - Cliquer sur "Run workflow"

### Utiliser l'image publiée

```yaml
# docker-compose.yml
services:
  kidsearch-all:
    image: ghcr.io/VOTRE_USERNAME/meilisearchcrawler:latest
    # ... reste de la configuration
```

Ou avec une version spécifique:
```yaml
services:
  kidsearch-all:
    image: ghcr.io/VOTRE_USERNAME/meilisearchcrawler:v1.0.0
```

### Pull l'image

```bash
# Dernière version
docker pull ghcr.io/VOTRE_USERNAME/meilisearchcrawler:latest

# Version spécifique
docker pull ghcr.io/VOTRE_USERNAME/meilisearchcrawler:v1.0.0
```

## Cache Docker

Le workflow utilise GitHub Actions cache pour accélérer les builds:
- Cache des layers Docker entre les builds
- Réutilisation des dépendances pip installées

## Multi-architecture

Les images sont buildées pour:
- `linux/amd64` (Intel/AMD 64-bit)
- `linux/arm64` (ARM 64-bit, ex: Apple Silicon, Raspberry Pi 4)

Docker sélectionne automatiquement la bonne architecture lors du pull.

## Troubleshooting

### Les tests échouent

1. Vérifier les logs du workflow
2. Exécuter les tests localement:
   ```bash
   python -m pytest tests/ -v
   ```

### L'image Docker ne se build pas

1. Vérifier que le Dockerfile est valide
2. Tester le build localement:
   ```bash
   docker build -t test .
   ```

### Impossible de pull l'image

1. Vérifier que le package est public (Settings → Packages)
2. S'authentifier si le package est privé:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```
