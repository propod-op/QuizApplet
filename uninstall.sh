#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# uninstall.sh — Quiz Applet v1.2
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
CYN='\033[0;36m'; BLD='\033[1m';    NC='\033[0m'

info()    { echo -e "${CYN}ℹ  $*${NC}"; }
success() { echo -e "${GRN}✔  $*${NC}"; }
warn()    { echo -e "${YLW}⚠  $*${NC}"; }
removed() { echo -e "${RED}🗑  Supprimé : $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_NAME="quiz-applet"

echo ""
echo -e "${RED}╔════════════════════════════════════════════╗${NC}"
echo -e "${RED}║     Quiz Applet v1.2 — Désinstallation    ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
echo ""

warn "Éléments qui seront supprimés :"
echo "   • Processus quiz.py actifs"
echo "   • ~/.config/quiz-applet/              (config + fenêtres)"
echo "   • ~/.config/autostart/quiz-applet.desktop"
echo "   • ~/.local/share/applications/quiz-applet.desktop"
echo "   • ~/.local/share/icons/hicolor/*/apps/quiz-applet.*"
echo "   • $SCRIPT_DIR"
echo ""
read -rp "Confirmer la désinstallation ? [o/N] : " CONFIRM
echo ""
[[ "$CONFIRM" =~ ^[oOyY]$ ]] || { info "Annulé."; exit 0; }

# ── 1. Arrêt des processus ────────────────────────────────────────────────────

info "Arrêt des processus Quiz en cours…"
KILLED=0
while IFS= read -r pid; do
    kill "$pid" 2>/dev/null && KILLED=$((KILLED+1)) || true
done < <(pgrep -f "python3.*quiz\.py" 2>/dev/null || true)
[[ $KILLED -gt 0 ]] && success "$KILLED processus arrêté(s)." || info "Aucun processus actif."
sleep 0.5

# ── 2. Config ─────────────────────────────────────────────────────────────────

CONFIG_DIR="$HOME/.config/quiz-applet"
if [[ -d "$CONFIG_DIR" ]]; then
    WIN_COUNT=$(python3 -c "
import json, glob
total = sum(
    len(json.load(open(f)).get('windows', []))
    for f in glob.glob('$CONFIG_DIR/*.json')
    if __import__('os').path.isfile(f)
)
print(total)
" 2>/dev/null || echo "?")
    rm -rf "$CONFIG_DIR"
    removed "$CONFIG_DIR  ($WIN_COUNT fenêtre(s) configurée(s))"
else
    info "Aucune config trouvée."
fi

# ── 3. Autostart ──────────────────────────────────────────────────────────────

AUTOSTART="$HOME/.config/autostart/quiz-applet.desktop"
if [[ -f "$AUTOSTART" ]]; then
    rm -f "$AUTOSTART"
    removed "$AUTOSTART"
else
    info "Aucun autostart trouvé."
fi

# ── 4. Entrée menu .desktop ───────────────────────────────────────────────────

APPS_DIR="$HOME/.local/share/applications"
DESKTOP="$APPS_DIR/${ICON_NAME}.desktop"
if [[ -f "$DESKTOP" ]]; then
    rm -f "$DESKTOP"
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    removed "$DESKTOP"
else
    info "Aucune entrée menu trouvée."
fi

# ── 5. Icônes (hicolor toutes tailles) ───────────────────────────────────────

HICOLOR="$HOME/.local/share/icons/hicolor"
ICON_REMOVED=0
for f in \
    "$HICOLOR/scalable/apps/${ICON_NAME}.svg" \
    "$HICOLOR/48x48/apps/${ICON_NAME}.png"    \
    "$HICOLOR/64x64/apps/${ICON_NAME}.png"    \
    "$HICOLOR/128x128/apps/${ICON_NAME}.png"
do
    if [[ -f "$f" ]]; then
        rm -f "$f"
        removed "$f"
        ICON_REMOVED=$((ICON_REMOVED+1))
    fi
done

if [[ $ICON_REMOVED -gt 0 ]]; then
    # Mettre à jour le cache d'icônes
    gtk-update-icon-cache -f -t "$HICOLOR" 2>/dev/null \
        || update-icon-caches "$HICOLOR" 2>/dev/null   \
        || true
    success "Cache d'icônes mis à jour"
else
    info "Aucune icône trouvée."
fi

# ── 6. Dossier applet ─────────────────────────────────────────────────────────

echo ""
warn "Dossier applet détecté : $SCRIPT_DIR"
read -rp "Supprimer également ce dossier ? [o/N] : " DEL_DIR
echo ""
if [[ "$DEL_DIR" =~ ^[oOyY]$ ]]; then
    TMP=$(mktemp /tmp/quiz_rm_XXXXXX.sh)
    printf '#!/bin/bash\nsleep 1\nrm -rf "%s"\nrm -f "%s"\n' \
        "$SCRIPT_DIR" "$TMP" > "$TMP"
    chmod +x "$TMP"
    bash "$TMP" &
    removed "$SCRIPT_DIR  (suppression dans 1 s.)"
else
    info "Dossier conservé : $SCRIPT_DIR"
fi

# ── 7. Paquets pip (optionnel) ────────────────────────────────────────────────

echo ""
read -rp "Désinstaller pystray et Pillow (pip) ? [o/N] : " DEL_PIP
if [[ "$DEL_PIP" =~ ^[oOyY]$ ]]; then
    python3 -m pip uninstall -y pystray Pillow 2>/dev/null \
        || python3 -m pip uninstall -y --break-system-packages pystray Pillow 2>/dev/null \
        || warn "pip uninstall échoué (sudo requis peut-être)."
    success "pystray + Pillow désinstallés."
else
    info "Paquets pip conservés."
fi

# ── Résumé ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GRN}═══════════════════════════════════════════${NC}"
success "Quiz Applet désinstallé avec succès."
echo -e "${GRN}═══════════════════════════════════════════${NC}"
echo ""
