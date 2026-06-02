#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh — Quiz Applet v1.2
# Ubuntu 22.04 / 24.04 / 26.04  —  GNOME
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUIZ_PY="$SCRIPT_DIR/quiz.py"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
CYN='\033[0;36m'; BLD='\033[1m';    NC='\033[0m'

info()    { echo -e "${CYN}ℹ  $*${NC}"; }
success() { echo -e "${GRN}✔  $*${NC}"; }
warn()    { echo -e "${YLW}⚠  $*${NC}"; }
error()   { echo -e "${RED}✘  $*${NC}"; exit 1; }
title()   { echo -e "\n${BLD}${CYN}── $* ${NC}"; }

echo ""
echo -e "${CYN}╔════════════════════════════════════════════╗${NC}"
echo -e "${CYN}║      Quiz Applet v1.2 — Installation      ║${NC}"
echo -e "${CYN}╚════════════════════════════════════════════╝${NC}"
echo ""

# ── Vérifications ─────────────────────────────────────────────────────────────

[[ -f "$QUIZ_PY" ]] || error "quiz.py introuvable dans $SCRIPT_DIR"
command -v apt-get  &>/dev/null || error "apt-get requis (Ubuntu/Debian)"
command -v python3  &>/dev/null || error "python3 introuvable"
info "Python  : $(python3 --version)"
info "Système : $(lsb_release -ds 2>/dev/null || echo 'Ubuntu/Debian')"

# ── Dépendances APT ───────────────────────────────────────────────────────────

title "Dépendances système (APT)"
sudo apt-get update -qq

PKGS=(python3-pip python3-gi python3-gi-cairo
      gir1.2-gtk-3.0 gir1.2-gdk-3.0 libgtk-3-0)
sudo apt-get install -y "${PKGS[@]}" -qq
success "GTK3 installé"

# WebKit2 : 4.1 (Ubuntu 24/26) ou 4.0 (Ubuntu 22)
WK_PKG=""
for pkg in gir1.2-webkit2-4.1 gir1.2-webkit2-4.0; do
    apt-cache show "$pkg" &>/dev/null && WK_PKG="$pkg" && break
done
[[ -n "$WK_PKG" ]] || error "WebKit2 introuvable dans les dépôts."
sudo apt-get install -y "$WK_PKG" -qq
success "WebKit2 installé ($WK_PKG)"

for rt in libwebkit2gtk-4.1-0 libwebkit2gtk-4.0-37; do
    apt-cache show "$rt" &>/dev/null && sudo apt-get install -y "$rt" -qq && break
done

# AppIndicator (tray Wayland/GNOME)
for pkg in gir1.2-ayatanaappindicator3-0.1 gir1.2-appindicator3-0.1; do
    if apt-cache show "$pkg" &>/dev/null; then
        sudo apt-get install -y "$pkg" -qq
        success "AppIndicator installé ($pkg)"
        break
    fi
done

# ── Dépendances Python ────────────────────────────────────────────────────────

title "Paquets Python (pip)"
python3 -m pip install pystray Pillow --quiet 2>/dev/null \
    || python3 -m pip install pystray Pillow --quiet --break-system-packages 2>/dev/null \
    || warn "pip échoué — tentative via apt…" \
    && sudo apt-get install -y python3-pil -qq 2>/dev/null || true
success "pystray + Pillow installés"

# ── Icône (freedesktop hicolor) ───────────────────────────────────────────────

title "Icône GNOME (hicolor)"

ICON_NAME="quiz-applet"
HICOLOR_BASE="$HOME/.local/share/icons/hicolor"

# Créer l'arborescence hicolor standard
mkdir -p \
    "$HICOLOR_BASE/scalable/apps" \
    "$HICOLOR_BASE/48x48/apps"    \
    "$HICOLOR_BASE/64x64/apps"    \
    "$HICOLOR_BASE/128x128/apps"

# 1) SVG scalable (aucune dépendance requise)
SVG_PATH="$HICOLOR_BASE/scalable/apps/${ICON_NAME}.svg"
cat > "$SVG_PATH" << 'SVGEOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <!-- Fond vert foncé -->
  <circle cx="32" cy="32" r="30" fill="#1e8449"/>
  <!-- Fond vert clair -->
  <circle cx="32" cy="32" r="26" fill="#27ae60"/>
  <!-- Reflet -->
  <ellipse cx="24" cy="20" rx="10" ry="6"
           fill="white" opacity="0.15" transform="rotate(-30 24 20)"/>
  <!-- Lettre Q -->
  <text x="32" y="44"
        text-anchor="middle"
        font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif"
        font-weight="bold"
        font-size="34"
        fill="white">Q</text>
  <!-- Petite barre du Q -->
  <line x1="40" y1="42" x2="46" y2="50"
        stroke="white" stroke-width="3.5" stroke-linecap="round"/>
</svg>
SVGEOF
success "SVG créé : $SVG_PATH"

# 2) PNG multi-tailles via Python/Pillow (optionnel, améliore la qualité dans certains contextes)
python3 - << PYEOF 2>/dev/null && success "PNG 48/64/128px générés" || warn "Pillow absent, seul le SVG sera utilisé"
from PIL import Image, ImageDraw, ImageFont
import os

hicolor = os.path.expanduser("~/.local/share/icons/hicolor")
name    = "quiz-applet"

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    pad = max(2, size // 32)
    d.ellipse([pad, pad, size-pad, size-pad], fill=(30, 132, 73))
    inner = max(4, size // 16)
    d.ellipse([inner, inner, size-inner, size-inner], fill=(39, 174, 96))
    try:
        fs   = int(size * 0.52)
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
    except Exception:
        font = ImageFont.load_default()
    bb = d.textbbox((0, 0), "Q", font=font)
    tx = (size - (bb[2]-bb[0])) / 2 - bb[0]
    ty = (size - (bb[3]-bb[1])) / 2 - bb[1] - size*0.04
    d.text((tx, ty), "Q", fill="white", font=font)
    return img

for sz in (48, 64, 128):
    dst = os.path.join(hicolor, f"{sz}x{sz}", "apps", f"{name}.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    make_icon(sz).save(dst)
PYEOF

# 3) Mise à jour du cache d'icônes GNOME
gtk-update-icon-cache -f -t "$HICOLOR_BASE" 2>/dev/null \
    || update-icon-caches "$HICOLOR_BASE" 2>/dev/null   \
    || true
success "Cache d'icônes mis à jour"

# ── Fichier .desktop (menu GNOME) ─────────────────────────────────────────────

title "Entrée menu Applications"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/${ICON_NAME}.desktop"
mkdir -p "$APPS_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Version=1.2
Name=Quiz Applet
GenericName=Widget Web Bureau
Comment=Affiche des pages web sur le bureau GNOME (fenêtres ou onglets)
Exec=python3 $QUIZ_PY
Icon=$ICON_NAME
Terminal=false
Categories=Utility;GTK;Network;WebBrowser;
Keywords=web;widget;dashboard;quiz;browser;
StartupNotify=false
StartupWMClass=quiz-applet
EOF

# Forcer les permissions (requis sur certaines configs Ubuntu)
chmod 644 "$DESKTOP_FILE"

# Valider le .desktop
if command -v desktop-file-validate &>/dev/null; then
    desktop-file-validate "$DESKTOP_FILE" \
        && success ".desktop valide" \
        || warn ".desktop créé avec avertissements"
fi

# Mettre à jour la base des .desktop
update-desktop-database "$APPS_DIR" 2>/dev/null || true
success "Menu créé : $DESKTOP_FILE"

# ── Extension GNOME AppIndicator ──────────────────────────────────────────────

title "Extension GNOME (tray icon)"
if apt-cache show gnome-shell-extension-appindicator &>/dev/null; then
    sudo apt-get install -y gnome-shell-extension-appindicator -qq
fi
if command -v gnome-extensions &>/dev/null; then
    for ext in ubuntu-appindicators@ubuntu.com appindicatorsupport@rgcjonas.gmail.com; do
        gnome-extensions enable "$ext" 2>/dev/null && {
            success "Extension activée : $ext"; break
        }
    done
else
    warn "gnome-extensions absent — activez AppIndicator manuellement"
fi

# ── Rendre quiz.py exécutable ─────────────────────────────────────────────────

chmod +x "$QUIZ_PY"

# ── Résumé ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GRN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GRN}║         Installation terminée ✔           ║${NC}"
echo -e "${GRN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLD}Via le menu GNOME :${NC}"
echo -e "    Applications → Quiz Applet"
echo ""
echo -e "  ${BLD}Via le terminal :${NC}"
echo -e "    ${CYN}python3 $QUIZ_PY${NC}"
echo ""
echo -e "  ${BLD}Config :${NC}"
echo -e "    ${CYN}~/.config/quiz-applet/default.json${NC}"
echo ""
echo -e "  ${YLW}ℹ  Si l'icône n'apparaît pas dans le menu :${NC}"
echo -e "    ${CYN}gtk-update-icon-cache -f ~/.local/share/icons/hicolor${NC}"
echo -e "    puis déconnectez/reconnectez votre session GNOME."
echo ""
