#!/usr/bin/env bash
# =============================================================================
# KidSearch - Setup interactif
# =============================================================================
set -euo pipefail

ENV_FILE=".env"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_step() { echo ""; echo -e "${BOLD}▶ $1${NC}"; }
print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
ask()        { echo -ne "  $1${YELLOW}${2:+ [$2]}${NC} : "; read -r REPLY; REPLY="${REPLY:-${2:-}}"; }
ask_secret() { echo -ne "  $1 : "; read -rs REPLY; echo ""; }
ask_yn()     { echo -ne "  $1 ${YELLOW}[o/N]${NC} : "; read -r REPLY; [[ "$REPLY" =~ ^[OoYy1]$ ]]; }

generate_secret() {
    python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null \
        || openssl rand -hex 32
}

# --- Prérequis ---
print_step "Vérification des prérequis"

command -v docker &>/dev/null || { echo -e "${RED}✗ Docker non trouvé.${NC} Installez Docker : https://docs.docker.com/get-docker/"; exit 1; }
print_ok "Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"

if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose &>/dev/null; then
    DC="docker-compose"
else
    echo -e "${RED}✗ Docker Compose non trouvé.${NC}"; exit 1
fi
print_ok "Docker Compose ($DC)"

if [ -f "$ENV_FILE" ]; then
    print_warn "Un fichier .env existe déjà."
    ask_yn "Le remplacer ?" && cp "$ENV_FILE" "${ENV_FILE}.backup" && print_ok "Sauvegarde : ${ENV_FILE}.backup" || { echo "  Annulé."; exit 0; }
fi

# --- Secrets (automatiques) ---
print_step "Génération des secrets"
JWT_SECRET=$(generate_secret)
TS_KEY=$(generate_secret | cut -c1-32)
print_ok "JWT_SECRET_KEY et TYPESENSE_API_KEY générés"

# --- Mot de passe dashboard ---
print_step "Accès au dashboard"
echo ""
echo "  Définissez un mot de passe pour protéger le dashboard."
echo "  Laissez vide pour désactiver l'authentification (dev uniquement)."
echo ""
ask_secret "Mot de passe (ou Entrée pour passer)"
PASSWORD="$REPLY"

if [ -n "$PASSWORD" ]; then
    AUTH_DISABLED="false"
    AUTH_PROVIDERS="simple"
    print_ok "Authentification par mot de passe activée"
else
    AUTH_DISABLED="true"
    AUTH_PROVIDERS=""
    print_warn "Aucune authentification — réservé au développement local"
fi

# --- Google CSE (optionnel) ---
print_step "Google Custom Search (optionnel)"
echo ""
echo "  Enrichit les résultats avec la recherche Google."
echo "  Laissez vide pour utiliser uniquement l'index local."
echo ""
CSE_KEY=""
CSE_ID=""
if ask_yn "Configurer Google CSE ?"; then
    ask "  GOOGLE_CSE_API_KEY"
    CSE_KEY="$REPLY"
    ask "  GOOGLE_CSE_ID"
    CSE_ID="$REPLY"
    print_ok "Google CSE configuré"
else
    print_ok "Ignoré (recherche locale uniquement)"
fi

# --- Écriture du .env ---
print_step "Création du fichier .env"

cat > "$ENV_FILE" <<EOF
# KidSearch — généré le $(date '+%Y-%m-%d %H:%M:%S')
# ⚠️  Ne pas commiter ce fichier dans git

# Typesense
TYPESENSE_URL=http://typesense:8108
TYPESENSE_API_KEY=${TS_KEY}
INDEX_NAME=kidsearch

# JWT
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Authentification
AUTH_DISABLED=${AUTH_DISABLED}
AUTH_PROVIDERS=${AUTH_PROVIDERS}
DASHBOARD_PASSWORD=${PASSWORD}
AUTH_PROXY_ENABLED=false
AUTH_PROXY_LOGOUT_URL=/
AUTH_PROXY_EMAIL_HEADER=X-Token-User-Email
AUTH_PROXY_NAME_HEADER=X-Token-User-Name
ALLOWED_EMAILS=

# API
API_URL=http://kidsearch-all:8080/api
API_ENABLED=true
API_WORKERS=2

# Embeddings (service Docker interne — ne pas modifier)
EMBEDDING_PROVIDER=huggingface
HUGGINGFACE_API_URL=http://embeddings_small:80/embed
HUGGINGFACE_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_BATCH_DELAY=2

# Reranking
RERANKING_ENABLED=true
RERANKER_API_URL=http://embeddings_small:80/embed
RERANKER_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RERANKER_BATCH_SIZE=3
RERANKER_MAX_CHARS=200
RERANKER_CACHE_SIZE=4096
RERANKER_TIMEOUT=12

# Poids de fusion
MEILISEARCH_WEIGHT=0.7
CSE_WEIGHT=0.3

# Google CSE
GOOGLE_CSE_API_KEY=${CSE_KEY}
GOOGLE_CSE_ID=${CSE_ID}

# Wiki (Vikidia par défaut)
WIKI_API_URL=https://fr.vikidia.org/w/api.php
WIKI_SITE_URL=https://fr.vikidia.org/wiki/
WIKI_SITE_NAME=Vikidia
WIKI_2_API_URL=https://en.vikidia.org/w/api.php
WIKI_2_SITE_URL=https://en.vikidia.org/wiki/
WIKI_2_SITE_NAME=Vikidia EN

# Logs
LOG_LEVEL=info

# URLs de production (optionnel)
FRONTEND_URL=
DISPLAY_HOST=
DASHBOARD_DISPLAY_HOST=
API_DISPLAY_HOST=
EOF

print_ok "Fichier .env créé"

# --- Démarrage ---
echo ""
echo -e "${CYAN}${BOLD}════════════════════════════════════════${NC}"
echo -e "${BOLD}  Prêt ! Services disponibles après démarrage :${NC}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════${NC}"
echo ""
echo "  Dashboard  →  http://localhost:8501"
echo "  API docs   →  http://localhost:8082/api/docs"
echo ""
echo -e "  ${YELLOW}Note :${NC} Le 1er démarrage télécharge le modèle (~90 MB, 2-5 min)"
echo ""

if ask_yn "Démarrer KidSearch maintenant ?"; then
    echo ""
    $DC up -d
    echo ""
    print_ok "KidSearch démarré ! Dashboard : http://localhost:8501"
    echo ""
    echo "  Logs     : ${BOLD}$DC logs -f${NC}"
    echo "  Arrêter  : ${BOLD}$DC down${NC}"
else
    echo ""
    echo "  Pour démarrer : ${BOLD}$DC up -d${NC}  ou  ${BOLD}make docker-up${NC}"
fi
echo ""
