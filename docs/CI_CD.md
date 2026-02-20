# CI/CD Documentation

Ce document explique comment utiliser le système CI/CD de KidSearch.

## Vue d'ensemble

Le projet utilise GitHub Actions pour:
1. **Tests automatiques** sur chaque commit et PR
2. **Build et publication** d'images Docker
3. **Releases versionnées** avec tags Git

## Workflows GitHub Actions

### 1. Tests (`tests.yml`)

**Déclenché automatiquement sur:**
- Commits sur `main` ou `develop`
- Pull Requests vers `main` ou `develop`

**Actions effectuées:**
- Tests sur Python 3.10, 3.11, et 3.12
- Linting avec `ruff`
- Vérification de types avec `mypy`
- Calcul de la couverture de code
- Upload des résultats vers Codecov (optionnel)

**Durée moyenne:** ~2-3 minutes

### 2. Docker Build & Publish (`docker-build.yml`)

**Déclenché automatiquement sur:**
- Push sur `main` ou `develop`
- Tags `v*` (ex: `v1.0.0`)
- Pull Requests (build uniquement, pas de push)

**Actions effectuées:**
1. Run tous les tests
2. Build image Docker multi-architecture (amd64 + arm64)
3. Push vers GitHub Container Registry (`ghcr.io`)
4. Création de tags automatiques

**Durée moyenne:** ~5-8 minutes

## Schéma de tags Docker

L'image Docker est taguée automatiquement selon la source:

| Source | Tags créés | Exemple |
|--------|-----------|---------|
| Branch `main` | `latest`, `main`, `main-<sha>` | `latest`, `main`, `main-abc1234` |
| Branch `develop` | `develop`, `develop-<sha>` | `develop`, `develop-xyz5678` |
| Tag `v1.2.3` | `v1.2.3`, `v1.2`, `v1`, `latest`* | `v1.2.3`, `v1.2`, `v1` |
| Pull Request #42 | `pr-42` | `pr-42` |

*`latest` uniquement si le tag est sur la branche `main`

## Comment créer une release

### Méthode 1: Script automatique (recommandé)

```bash
# Créer et publier une release v1.0.0
./scripts/release.sh v1.0.0
```

Le script va:
1. Vérifier que le working directory est propre
2. Valider le format de version
3. Créer le tag Git
4. Pusher vers GitHub
5. Déclencher automatiquement le workflow de build

### Méthode 2: Manuelle

```bash
# 1. S'assurer d'être sur la bonne branche
git checkout main
git pull

# 2. Créer le tag
git tag -a v1.0.0 -m "Release v1.0.0"

# 3. Pusher le tag
git push origin v1.0.0
```

## Utiliser les images Docker

### Depuis GitHub Container Registry

```bash
# Dernière version stable
docker pull ghcr.io/laurentftech/meilisearchcrawler:latest

# Version spécifique
docker pull ghcr.io/laurentftech/meilisearchcrawler:v1.0.0

# Dernière version de develop
docker pull ghcr.io/laurentftech/meilisearchcrawler:develop
```

### Dans docker-compose.yml

```yaml
services:
  kidsearch-all:
    image: ghcr.io/laurentftech/meilisearchcrawler:latest
    # ... reste de la config
```

## Configuration GitHub

### Permissions nécessaires

Le repository doit avoir ces permissions activées (normalement par défaut):
- **Settings → Actions → General:**
  - ✅ "Allow all actions and reusable workflows"
  - ✅ "Read and write permissions"
  - ✅ "Allow GitHub Actions to create and approve pull requests"

### Rendre le package public

Par défaut, les packages GitHub sont privés. Pour les rendre publics:

1. Aller sur **Packages** dans votre profil GitHub
2. Cliquer sur le package `meilisearchcrawler`
3. **Package settings → Danger Zone**
4. Cliquer sur "Change visibility"
5. Sélectionner "Public"

## Secrets (optionnels)

### CODECOV_TOKEN

Pour activer l'upload vers Codecov:

1. Créer un compte sur [codecov.io](https://codecov.io)
2. Lier votre repository GitHub
3. Copier le token
4. Aller dans **Settings → Secrets → Actions**
5. Créer un nouveau secret `CODECOV_TOKEN`

## Monitoring des builds

### Voir l'état des workflows

1. **Badge dans le README**: Indique le statut du dernier build
2. **Actions tab**: Historique complet de tous les runs
3. **Commit checks**: ✅ ou ❌ sur chaque commit

### Notifications

GitHub envoie automatiquement des notifications par email si un workflow échoue sur votre branche.

## Troubleshooting

### Les tests échouent

```bash
# Run les tests localement
python -m pytest tests/ -v

# Avec coverage
python -m pytest tests/ --cov=kidsearch
```

### Le build Docker échoue

```bash
# Tester le build localement
docker build -t test-kidsearch .

# Avec verbose
docker build --progress=plain -t test-kidsearch .
```

### Impossible de pull l'image

```bash
# Si le package est privé, s'authentifier d'abord
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Puis pull
docker pull ghcr.io/laurentftech/meilisearchcrawler:latest
```

### Le workflow ne se déclenche pas

Vérifications:
1. Le fichier workflow est dans `.github/workflows/`
2. La syntaxe YAML est valide
3. Les permissions Actions sont activées dans Settings
4. Le push contient bien les changements

## Bonnes pratiques

### Commits

```bash
# Format recommandé
git commit -m "fix: correction du bug de recherche"
git commit -m "feat: ajout recherche hybride"
git commit -m "docs: mise à jour documentation"
```

### Branches

- `main` - Production, toujours stable
- `develop` - Développement actif
- `feature/*` - Nouvelles fonctionnalités
- `fix/*` - Corrections de bugs

### Releases

- Version sémantique: `vMAJOR.MINOR.PATCH`
- MAJOR: Breaking changes
- MINOR: Nouvelles fonctionnalités
- PATCH: Bug fixes

Exemples:
- `v1.0.0` - Première release stable
- `v1.1.0` - Ajout de fonctionnalités
- `v1.1.1` - Corrections de bugs
- `v2.0.0` - Breaking changes

### Pull Requests

1. Créer une branche depuis `develop`
2. Faire vos changements
3. Push et créer une PR vers `develop`
4. Attendre que les tests passent (✅)
5. Demander une review
6. Merge quand approuvé

## Performance

### Cache

Les workflows utilisent plusieurs niveaux de cache:

1. **Python dependencies** - Cache pip entre runs (~30s économisés)
2. **Docker layers** - Cache entre builds (~2-3min économisés)
3. **GitHub Actions cache** - Réutilisé entre workflows

### Optimisations

- Build multi-stage Docker pour réduire la taille finale
- `.dockerignore` pour exclure fichiers inutiles
- Buildx pour builds parallèles multi-architecture
- Cache des layers Docker avec GitHub Actions cache

## Support multi-architecture

Les images sont buildées pour:
- **linux/amd64** - Serveurs Intel/AMD classiques
- **linux/arm64** - Apple Silicon (M1/M2), Raspberry Pi 4, AWS Graviton

Docker sélectionne automatiquement la bonne architecture lors du `pull`.

## Ressources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
