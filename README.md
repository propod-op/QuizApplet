# Quiz Applet v1.2

Widget de bureau web configurable pour **GNOME / Ubuntu**.
Affiche une ou plusieurs pages web dans des fenêtres flottantes ou des onglets,
directement sur le bureau.

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🌐 WebView | Affiche n'importe quelle URL (WebKit2) |
| ⊟ / ⊞ Mode fenêtres / onglets | Bascule entre fenêtres séparées et onglets (`Gtk.Notebook`) |
| 🔝 Always on top | Fenêtre toujours au premier plan |
| 📌 Collé au bureau | Fenêtre fixée derrière toutes les autres |
| 🚀 Autostart | Démarrage automatique à l'ouverture de session |
| 📦 Multi-fenêtres | Plusieurs vues web indépendantes |
| 🗂 System tray | Icône dans la barre (afficher/masquer/créer/supprimer/basculer) |
| 💾 Config persistante | Position, taille, mode et URL sauvegardés automatiquement |
| 🖼 Icône GNOME | Entrée dans le menu Applications avec icône hicolor |

---

## Prérequis

- Ubuntu 22.04, 24.04 ou 26.04
- Bureau GNOME
- Python 3.10+

---

## Installation

```bash
chmod +x install.sh
./install.sh
```

Le script installe automatiquement :

| Paquet | Source |
|---|---|
| `python3-gi`, `gir1.2-gtk-3.0` | APT |
| `gir1.2-webkit2-4.1` ou `4.0` | APT (selon Ubuntu) |
| `gir1.2-ayatanaappindicator3-0.1` | APT (tray Wayland) |
| `pystray`, `Pillow` | pip |

Et crée :

```
~/.local/share/icons/hicolor/
├── scalable/apps/quiz-applet.svg
├── 48x48/apps/quiz-applet.png
├── 64x64/apps/quiz-applet.png
└── 128x128/apps/quiz-applet.png

~/.local/share/applications/quiz-applet.desktop  ← entrée menu GNOME
```

### Note — System Tray sous GNOME Shell

GNOME 40+ masque les icônes de tray par défaut. Installez l'extension AppIndicator :

```bash
sudo apt install gnome-shell-extension-appindicator
```

Puis activez-la via l'application **Extensions** ou **GNOME Tweaks**.

---

## Désinstallation

```bash
chmod +x uninstall.sh
./uninstall.sh
```

Supprime avec confirmation : processus actifs, config, autostart, entrée menu,
icônes hicolor (toutes tailles), et optionnellement le dossier applet et les paquets pip.

---

## Utilisation

### Depuis le menu GNOME

Applications → **Quiz Applet**

### Depuis le terminal

```bash
python3 quiz.py
```

### Sur Wayland — Always on top

Sur Wayland pur, `always on top` peut être ignoré par le compositeur.
Contournement via XWayland :

```bash
GDK_BACKEND=x11 python3 quiz.py
```

---

## Interface

### Barre de titre (mode fenêtres)

```
[ ☰ Fenêtres ▾ ]  Titre — URL              [ ✚ ] [ ⊟ ] [ ⚙ ] [ ✕ ]
```

| Bouton | Action |
|---|---|
| `☰ Fenêtres` | Sélectionner / afficher une autre fenêtre |
| `✚` | Créer une nouvelle fenêtre (dialogue nom + URL) |
| `⊟` | Passer en mode onglets |
| `⚙` | Configurer cette fenêtre (nom, URL, always on top, collé au bureau) |
| `✕` | Masquer cette fenêtre |

### Barre de titre (mode onglets)

```
Titre — Onglet courant              [ ✚ ] [ ⊞ ] [ ⚙ ] [ ✕ ]
[  Onglet 1  ✕ ] [  Onglet 2  ✕ ] [  Onglet 3  ✕ ]
```

| Bouton | Action |
|---|---|
| `✚` | Nouvel onglet (dialogue nom + URL) |
| `⊞` | Passer en mode fenêtres séparées |
| `⚙` | Configurer l'onglet courant |
| `✕` (header) | Fermer l'onglet courant |
| `✕` (label onglet) | Fermer cet onglet |

### Menu System Tray

```
Quiz Applet  v1.2
─────────────────
⊟  Passer en mode onglets          ← bascule le mode
─────────────────
✓  Fenêtre 1                       ← visible
○  Météo                           ← masquée
─────────────────
✚  Nouvelle fenêtre…
🗑  Supprimer une fenêtre…
─────────────────
Quitter
```

---

## Configuration

### Via l'interface

Bouton `⚙` dans la barre de titre de chaque fenêtre.

### Via le fichier JSON

```
~/.config/quiz-applet/default.json
```

```json
{
  "version": "1.2",
  "autostart": false,
  "display_mode": "windowed",
  "windows": [
    {
      "id": "abc12345",
      "name": "Ma fenêtre",
      "url": "https://www.google.com",
      "always_on_top": false,
      "stick_to_desktop": false,
      "enabled": true,
      "width": 900,
      "height": 600,
      "x": 100,
      "y": 100
    }
  ]
}
```

| Clé | Valeurs | Description |
|---|---|---|
| `display_mode` | `"windowed"` / `"tabbed"` | Mode d'affichage au démarrage |
| `always_on_top` | `true` / `false` | Fenêtre toujours devant |
| `stick_to_desktop` | `true` / `false` | Fenêtre toujours derrière |
| `enabled` | `true` / `false` | Visible au démarrage |
| `autostart` | `true` / `false` | Démarrage automatique à la session |

> `always_on_top` et `stick_to_desktop` sont mutuellement exclusifs.

---

## Autostart manuel

Créer `~/.config/autostart/quiz-applet.desktop` :

```ini
[Desktop Entry]
Type=Application
Name=Quiz Applet
Exec=python3 /chemin/vers/quiz.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

---

## Structure des fichiers

```
quiz-applet/
├── quiz.py         ← Application principale (v1.2)
├── install.sh      ← Installation complète
├── uninstall.sh    ← Désinstallation complète
└── README.md       ← Cette documentation
```

Fichiers créés à l'installation / l'exécution :

```
~/.config/quiz-applet/
└── default.json                         ← config (toutes les fenêtres)

~/.config/autostart/
└── quiz-applet.desktop                  ← autostart (si activé)

~/.local/share/applications/
└── quiz-applet.desktop                  ← entrée menu GNOME

~/.local/share/icons/hicolor/
├── scalable/apps/quiz-applet.svg
├── 48x48/apps/quiz-applet.png
├── 64x64/apps/quiz-applet.png
└── 128x128/apps/quiz-applet.png
```

---

## Dépannage

| Problème | Solution |
|---|---|
| `WebKit2 introuvable` | `sudo apt install gir1.2-webkit2-4.1` |
| Icône tray invisible | Installer + activer l'extension AppIndicator GNOME |
| `pystray` manquant | `pip3 install pystray Pillow` |
| Icône absente du menu GNOME | `gtk-update-icon-cache -f ~/.local/share/icons/hicolor` puis reconnexion |
| `always on top` inactif | Lancer avec `GDK_BACKEND=x11 python3 quiz.py` (XWayland) |
| Fenêtre ne s'affiche pas | Vérifier `"enabled": true` dans `default.json` |
