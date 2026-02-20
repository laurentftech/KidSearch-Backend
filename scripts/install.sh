#!/usr/bin/env bash
# =============================================================================
# KidSearch - Installateur rapide (curl | bash)
# Usage : curl -fsSL https://raw.githubusercontent.com/laurentftech/KidSearch-Backend/main/scripts/install.sh | bash
# =============================================================================
set -euo pipefail

REPO="https://raw.githubusercontent.com/laurentftech/KidSearch-Backend/main"
DEST_DIR="kidsearch"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║     KidSearch — Installation         ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# Prérequis
command -v docker &>/dev/null   || { echo -e "${RED}✗ Docker requis.${NC} → https://docs.docker.com/get-docker/"; exit 1; }
command -v curl &>/dev/null     || { echo -e "${RED}✗ curl requis.${NC}"; exit 1; }

# Répertoire d'installation
if [ -d "$DEST_DIR" ]; then
    echo -e "  Le dossier ${BOLD}${DEST_DIR}/${NC} existe déjà."
    echo -ne "  Continuer quand même ? [o/N] : "
    read -r yn
    [[ "$yn" =~ ^[OoYy1]$ ]] || { echo "  Annulé."; exit 0; }
else
    mkdir -p "$DEST_DIR"
fi

cd "$DEST_DIR"
echo -e "  ${GREEN}✓${NC} Dossier : $(pwd)"

# Téléchargement des fichiers nécessaires
echo ""
echo -e "  Téléchargement des fichiers de configuration..."
curl -fsSL "${REPO}/docker-compose.yml"  -o docker-compose.yml
curl -fsSL "${REPO}/.env.example"        -o .env.example
curl -fsSL "${REPO}/scripts/setup.sh"   -o setup.sh
chmod +x setup.sh
echo -e "  ${GREEN}✓${NC} Fichiers téléchargés"

# Lancement du setup interactif
echo ""
bash setup.sh
