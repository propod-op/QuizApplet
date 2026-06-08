#!/usr/bin/env python3
"""
Quiz Applet v1.6
Widget de bureau web — mode fenêtres ou mode onglets
Config : ~/.config/quiz-applet/default.json
"""

VERSION = "1.5"

import gi, os, sys, json, threading, signal, uuid

CONFIG_DIR     = os.path.expanduser("~/.config/quiz-applet")
CONFIG_FILE    = os.path.join(CONFIG_DIR, "default.json")


def _load_startup_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    except Exception:
        return {}
    if cfg.get("backend") not in ("auto", "wayland", "x11"):
        cfg["backend"] = "auto"
    return cfg

_startup_cfg = _load_startup_config()
_backend = _startup_cfg.get("backend")
if _backend in ("wayland", "x11"):
    os.environ["GDK_BACKEND"] = _backend


gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

_wk_ok = False
for _v in ('4.1', '4.0'):
    try:
        gi.require_version('WebKit2', _v)
        _wk_ok = True
        break
    except ValueError:
        pass
if not _wk_ok:
    print("ERREUR : WebKit2 introuvable. Installez gir1.2-webkit2-4.1")
    sys.exit(1)

from gi.repository import Gtk, Gdk, GLib, WebKit2

try:
    from gi.repository import GdkPixbuf
    _HAS_PIXBUF = True
except ImportError:
    _HAS_PIXBUF = False

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False
    print("AVERTISSEMENT : pystray/Pillow manquants — tray désactivé.")

# ─────────────────────────────────────────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR     = os.path.expanduser("~/.config/quiz-applet")
CONFIG_FILE    = os.path.join(CONFIG_DIR, "default.json")
AUTOSTART_DIR  = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "quiz-applet.desktop")

MODES = ("windowed", "tabbed")

# ─────────────────────────────────────────────────────────────────────────────
# Icône épingle (SVG Material Design thumbtack)
# ─────────────────────────────────────────────────────────────────────────────

# SVG épingle (Material Design — thumbtack)
_PIN_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    b'viewBox="0 0 24 24">'
    b'<path fill="white" '
    b'd="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>'
    b'</svg>'
)

_PIN_SVG_ACTIVE = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    b'viewBox="0 0 24 24">'
    b'<path fill="#f39c12" '
    b'd="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>'
    b'</svg>'
)


def _load_svg_pixbuf(svg_bytes: bytes):
    """Charge un SVG inline en GdkPixbuf."""
    if not _HAS_PIXBUF:
        return None
    try:
        ldr = GdkPixbuf.PixbufLoader.new_with_mime_type("image/svg+xml")
        ldr.write(svg_bytes)
        ldr.close()
        return ldr.get_pixbuf()
    except Exception:
        return None


def _make_pin_image(active: bool = False) -> Gtk.Widget:
    """
    Retourne un Gtk.Image avec l'icône épingle.
    Priorité : icon theme → SVG inline → emoji label.
    """
    # 1) Essai via le thème GTK (Adwaita 42+)
    theme = Gtk.IconTheme.get_default()
    for name in ("pin-symbolic", "view-pin-symbolic"):
        if theme.has_icon(name):
            return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.BUTTON)

    # 2) SVG inline
    svg = _PIN_SVG_ACTIVE if active else _PIN_SVG
    pb  = _load_svg_pixbuf(svg)
    if pb:
        return Gtk.Image.new_from_pixbuf(pb)

    # 3) Repli texte
    return Gtk.Label(label="📌")


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

def new_win_cfg(name: str = "Nouvelle fenêtre",
                url: str  = "https://www.google.com") -> dict:
    return {
        "id"              : uuid.uuid4().hex[:8],
        "name"            : name,
        "url"             : url,
        "always_on_top"   : False,
        "stick_to_desktop": False,
        "pinned"          : False,   # ← v1.4 : épingle (toujours devant + verrouillage)
        "enabled"         : True,
        "width"           : 900,
        "height"          : 600,
        "x"               : 100,
        "y"               : 100,
    }

DEFAULT_APP_CONFIG: dict = {
    "version"      : VERSION,
    "autostart"    : False,
    "display_mode" : "windowed",
    "backend"      : "auto",
    "windows"      : [],
}


def load_config() -> dict:
    base = DEFAULT_APP_CONFIG.copy()
    base["windows"] = []
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                base.update(json.load(f))
        except Exception:
            pass
    if base.get("backend") not in ("auto", "wayland", "x11"):
        base["backend"] = "auto"
    if not base["windows"]:
        base["windows"].append(new_win_cfg("Fenêtre 1"))
    for w in base["windows"]:
        if not w.get("id"):
            w["id"] = uuid.uuid4().hex[:8]
        w.setdefault("pinned", False)
    if base.get("display_mode") not in MODES:
        base["display_mode"] = "windowed"
    return base


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Icône tray
# ─────────────────────────────────────────────────────────────────────────────

def make_tray_icon() -> "Image.Image":
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    d.ellipse([2, 2, 62, 62], fill=(30, 132, 73))
    d.ellipse([6, 6, 58, 58], fill=(39, 174, 96))
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    bb = d.textbbox((0, 0), "Q", font=font)
    tx = (size - (bb[2] - bb[0])) / 2 - bb[0]
    ty = (size - (bb[3] - bb[1])) / 2 - bb[1]
    d.text((tx, ty), "Q", fill="white", font=font)
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Dialogues
# ─────────────────────────────────────────────────────────────────────────────

class NewWindowDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(title="✚  Nouvelle fenêtre",
                         transient_for=parent, flags=0)
        self.add_buttons("_Annuler", Gtk.ResponseType.CANCEL,
                         "_Créer",   Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(420, -1)
        self.set_modal(True)

        box  = self.get_content_area()
        grid = Gtk.Grid(row_spacing=10, column_spacing=10,
                        margin_top=14, margin_bottom=14,
                        margin_start=14, margin_end=14)
        box.pack_start(grid, True, True, 0)

        grid.attach(Gtk.Label(label="Nom", xalign=0, width_chars=6), 0, 0, 1, 1)
        self.entry_name = Gtk.Entry(text="Nouvelle fenêtre",
                                     hexpand=True, activates_default=True)
        grid.attach(self.entry_name, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="URL", xalign=0), 0, 1, 1, 1)
        self.entry_url = Gtk.Entry(text="https://",
                                    hexpand=True, activates_default=True,
                                    placeholder_text="https://…")
        grid.attach(self.entry_url, 1, 1, 1, 1)
        box.show_all()

    def get_values(self):
        return (self.entry_name.get_text().strip(),
                self.entry_url.get_text().strip())


class DeleteWindowDialog(Gtk.Dialog):
    def __init__(self, parent, windows: list):
        super().__init__(title="🗑  Supprimer une fenêtre",
                         transient_for=parent, flags=0)
        self.add_buttons("_Annuler",   Gtk.ResponseType.CANCEL,
                         "_Supprimer", Gtk.ResponseType.OK)
        self.set_default_size(380, -1)
        self.set_modal(True)

        box  = self.get_content_area()
        grid = Gtk.Grid(row_spacing=10, column_spacing=10,
                        margin_top=14, margin_bottom=14,
                        margin_start=14, margin_end=14)
        box.pack_start(grid, True, True, 0)

        grid.attach(Gtk.Label(label="Fenêtre :", xalign=0), 0, 0, 1, 1)
        self.combo = Gtk.ComboBoxText(hexpand=True)
        for w in windows:
            self.combo.append(w["id"], w["name"])
        if windows:
            self.combo.set_active(0)
        grid.attach(self.combo, 1, 0, 1, 1)
        box.show_all()

    def get_selected_id(self) -> str | None:
        return self.combo.get_active_id()


class ConfigDialog(Gtk.Dialog):
    def __init__(self, parent, win_cfg: dict):
        super().__init__(title=f"⚙  {win_cfg.get('name', '…')}",
                         transient_for=parent, flags=0)
        self.add_buttons("_Annuler",   Gtk.ResponseType.CANCEL,
                         "_Appliquer", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(460, -1)
        self.set_modal(True)

        box  = self.get_content_area()
        grid = Gtk.Grid(row_spacing=12, column_spacing=10,
                        margin_top=14, margin_bottom=14,
                        margin_start=14, margin_end=14)
        box.pack_start(grid, True, True, 0)

        grid.attach(Gtk.Label(label="Nom", xalign=0, width_chars=8), 0, 0, 1, 1)
        self.entry_name = Gtk.Entry(text=win_cfg.get("name", ""), hexpand=True)
        grid.attach(self.entry_name, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="URL", xalign=0), 0, 1, 1, 1)
        self.entry_url = Gtk.Entry(text=win_cfg.get("url", ""),
                                    hexpand=True, activates_default=True)
        grid.attach(self.entry_url, 1, 1, 1, 1)

        grid.attach(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL,
                          margin_top=4, margin_bottom=4),
            0, 2, 2, 1)

        self.chk_desk = Gtk.CheckButton(
            label="📌  Collé au bureau (derrière toutes les fenêtres)",
            active=win_cfg.get("stick_to_desktop", False))
        grid.attach(self.chk_desk, 0, 3, 2, 1)

        note = Gtk.Label(xalign=0, margin_top=4)
        note.set_markup(
            "<small><i>ℹ  Pour épingler au premier plan, utilisez le bouton 📌 "
            "dans la barre de titre.\n"
            "Sur Wayland : lancez avec GDK_BACKEND=x11 pour un épinglage fiable.</i></small>")
        grid.attach(note, 0, 4, 2, 1)

        box.show_all()

    def get_values(self) -> dict:
        return {
            "name"            : self.entry_name.get_text().strip(),
            "url"             : self.entry_url.get_text().strip(),
            "stick_to_desktop": self.chk_desk.get_active(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hb_btn(label: str, tooltip: str, callback) -> Gtk.Button:
    b = Gtk.Button(label=label)
    b.set_tooltip_text(tooltip)
    b.connect("clicked", callback)
    return b


def _info_dialog(parent, text: str):
    dlg = Gtk.MessageDialog(
        transient_for=parent, flags=0,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.OK, text=text)
    dlg.run(); dlg.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# CSS — style du bouton épingle actif
# ─────────────────────────────────────────────────────────────────────────────

_CSS = b"""
.pin-active {
    background-color: #e67e22;
    color: white;
    border-color: #d35400;
}
.pin-active:hover {
    background-color: #d35400;
}
"""

def _apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MODE FENÊTRES — QuizWindow
# ─────────────────────────────────────────────────────────────────────────────

class QuizWindow(Gtk.Window):

    # Intervalle du timer de maintien always-on-top (ms)
    _PIN_INTERVAL = 900

    def __init__(self, win_cfg: dict, app: "QuizApp"):
        super().__init__()
        self._cfg        = win_cfg
        self._app        = app
        self._save_timer = None
        self._pin_timer  = None

        # État épingle
        self._pinned     = win_cfg.get("pinned", False)
        # Position/taille verrouillées quand épinglé
        self._locked_x   = win_cfg.get("x",      100)
        self._locked_y   = win_cfg.get("y",      100)
        self._locked_w   = win_cfg.get("width",   900)
        self._locked_h   = win_cfg.get("height",  600)

        self.set_default_size(win_cfg["width"], win_cfg["height"])
        self.move(win_cfg["x"], win_cfg["y"])

        # ── Header bar ────────────────────────────────────────────────────
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(False)
        hb.set_title(win_cfg["name"])
        hb.set_subtitle(win_cfg.get("url", ""))
        self.set_titlebar(hb)

        # Gauche : sélecteur de fenêtres
        self._win_btn  = Gtk.MenuButton(label="☰  Fenêtres")
        self._win_btn.set_tooltip_text("Gérer les fenêtres")
        self._win_menu = Gtk.Menu()
        self._win_btn.set_popup(self._win_menu)
        self._win_btn.connect("clicked", lambda *_: self._rebuild_win_menu())
        hb.pack_start(self._win_btn)

        # Droite : ✕ ⚙ ⊟ 📌 ✚
        hb.pack_end(_hb_btn("✕", "Masquer cette fenêtre",
                             lambda *_: self._hide()))
        hb.pack_end(_hb_btn("⚙", "Configurer cette fenêtre",
                             lambda *_: self._on_config()))
        hb.pack_end(_hb_btn("⊟", "Passer en mode onglets",
                             lambda *_: GLib.idle_add(self._app.switch_mode)))

        # ── Bouton épingle (ToggleButton) ─────────────────────────────────
        self._pin_btn = Gtk.ToggleButton()
        self._pin_btn.set_tooltip_text(
            "📌  Épingler au premier plan\n"
            "Verrouille aussi la position et la taille")
        self._pin_btn.set_active(self._pinned)
        self._update_pin_button_ui()
        self._pin_btn.connect("toggled", self._on_pin_toggled)
        hb.pack_end(self._pin_btn)

        hb.pack_end(_hb_btn("✚", "Nouvelle fenêtre",
                             lambda *_: self._app.create_new_window_dialog(self)))

        # ── WebView ───────────────────────────────────────────────────────
        self._webview = WebKit2.WebView()
        self._webview.load_uri(win_cfg["url"])
        self._webview.connect("load-changed", self._on_load_changed)
        self.add(self._webview)

        # ── Signaux ───────────────────────────────────────────────────────
        self.connect("delete-event",    self._on_delete)
        self.connect("configure-event", self._on_configure)
        self.connect("realize",         lambda *_: self._post_realize())

        self.show_all()

    # ── Post-réalisation ──────────────────────────────────────────────────

    def _post_realize(self):
        self._apply_hints()
        GLib.idle_add(self._apply_hints)
        if self._pinned:
            self._start_pin_timer()

    # ── Icône du bouton épingle ───────────────────────────────────────────

    def _update_pin_button_ui(self):
        """Met à jour l'icône et le style CSS du bouton épingle."""
        # Vider le contenu actuel
        child = self._pin_btn.get_child()
        if child:
            self._pin_btn.remove(child)

        img = _make_pin_image(active=self._pinned)
        self._pin_btn.add(img)
        img.show()

        ctx = self._pin_btn.get_style_context()
        if self._pinned:
            ctx.add_class("pin-active")
            ctx.remove_class("pin-inactive")
        else:
            ctx.remove_class("pin-active")

    # ── Logique épingle ───────────────────────────────────────────────────

    def _on_pin_toggled(self, btn):
        self._pinned = btn.get_active()
        self._cfg["pinned"] = self._pinned

        if self._pinned:
            # Capturer position + taille AVANT tout changement GTK
            x, y = self.get_position()
            w, h = self.get_size()
            self._locked_x, self._locked_y = x, y
            self._locked_w, self._locked_h = w, h
            self._cfg.update({"x": x, "y": y, "width": w, "height": h})
            # Figer la taille AVANT set_resizable(False)
            # (sinon GTK réduit la fenêtre à sa taille minimale naturelle)
            self.set_size_request(w, h)
            self.resize(w, h)
            self.set_resizable(False)
            # Appliquer always-on-top immédiatement
            self.set_keep_above(True)
            # Demander aussi à GTK de présenter la fenêtre pour la
            # remonter immédiatement au-dessus des autres (améliore
            # le comportement avec certains compositeurs).
            try:
                self.present()
            except Exception:
                pass
            self.set_keep_below(False)
            # Démarrer le timer de maintien
            self._start_pin_timer()
        else:
            # Libérer la contrainte de taille AVANT de rendre la fenêtre redimensionnable
            self.set_size_request(-1, -1)
            self.set_resizable(True)
            self.set_keep_above(False)
            self._stop_pin_timer()
            self._apply_hints()

        self._update_pin_button_ui()
        self._app.save()

    def _start_pin_timer(self):
        """Démarre un timer qui réapplique always-on-top périodiquement."""
        self._stop_pin_timer()
        self._pin_timer = GLib.timeout_add(self._PIN_INTERVAL, self._enforce_pin)

    def _stop_pin_timer(self):
        if self._pin_timer is not None:
            GLib.source_remove(self._pin_timer)
            self._pin_timer = None

    def _enforce_pin(self) -> bool:
        """
        Callback du timer : réapplique always-on-top et restaure
        la position/taille si la fenêtre a été déplacée/redimensionnée.
        Retourne True pour continuer, False pour arrêter.
        """
        if not self._pinned:
            return False

        # Réappliquer always-on-top (Wayland peut l'oublier)
        self.set_keep_above(True)
        try:
            self.present()
        except Exception:
            pass

        # Restaurer la position si elle a dérivé
        cx, cy = self.get_position()
        if abs(cx - self._locked_x) > 8 or abs(cy - self._locked_y) > 8:
            self.move(self._locked_x, self._locked_y)

        return True   # continuer le timer

    # ── Window hints (stick to desktop, etc.) ────────────────────────────

    def _apply_hints(self):
        if self._pinned:
            # Épinglé : always-on-top prime sur tout
            self.set_keep_above(True)
            self.set_keep_below(False)
            self.set_skip_taskbar_hint(False)
            self.set_skip_pager_hint(False)
        else:
            desk = self._cfg.get("stick_to_desktop", False)
            self.set_keep_above(False)
            self.set_keep_below(desk)
            self.set_skip_taskbar_hint(desk)
            self.set_skip_pager_hint(desk)
        return False

    # ── Menu fenêtres ─────────────────────────────────────────────────────

    def _rebuild_win_menu(self):
        for child in self._win_menu.get_children():
            self._win_menu.remove(child)
        for wcfg in self._app.config["windows"]:
            wid     = wcfg["id"]
            win     = self._app.windows.get(wid)
            visible = win is not None and win.get_visible()
            is_self = (wid == self._cfg["id"])
            pinned  = wcfg.get("pinned", False)
            label   = (
                f"{'▶' if is_self else ('✓' if visible else '○')}"
                f"{'  📌' if pinned else ''}"
                f"  {wcfg['name']}"
            )
            item = Gtk.MenuItem(label=label)
            item.set_sensitive(not is_self)

            def _cb(_, w=wid):
                GLib.idle_add(self._app.toggle_window_by_id, w)

            item.connect("activate", _cb)
            self._win_menu.append(item)
        self._win_menu.show_all()

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _on_config(self):
        dlg = ConfigDialog(self, self._cfg)
        if dlg.run() == Gtk.ResponseType.OK:
            vals = dlg.get_values()
            self.apply_config(vals)
            self._app.save()
        dlg.destroy()

    def _on_load_changed(self, wv, event):
        if event == WebKit2.LoadEvent.COMMITTED:
            uri = wv.get_uri() or ""
            self.get_titlebar().set_subtitle(uri)

    def _on_delete(self, *_):
        self._hide()
        return True

    def _on_configure(self, widget, event):
        """Sauvegarde position/taille — ignorée si épinglé."""
        if self._pinned:
            return False
        x, y = self.get_position()
        w, h = self.get_size()
        self._cfg.update({"x": x, "y": y, "width": w, "height": h})
        if self._save_timer:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(500, self._flush_save)
        return False

    def _flush_save(self):
        self._app.save()
        self._save_timer = None
        return False

    # ── API publique ──────────────────────────────────────────────────────

    def apply_config(self, new_cfg: dict):
        self._cfg.update(new_cfg)
        hb = self.get_titlebar()
        hb.set_title(self._cfg["name"])
        if new_cfg.get("url") and new_cfg["url"] != self._webview.get_uri():
            self._webview.load_uri(new_cfg["url"])
        self._apply_hints()

    def _hide(self):
        self._stop_pin_timer()
        self.hide()
        self._cfg["enabled"] = False
        self._app.save()
        self._app.rebuild_tray_menu()

    def destroy(self):
        self._stop_pin_timer()
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# MODE ONGLETS — QuizTabWindow
# ─────────────────────────────────────────────────────────────────────────────

class QuizTabWindow(Gtk.Window):
    """Fenêtre unique avec onglets (mode tabbed)."""

    _PIN_INTERVAL = 900

    def __init__(self, app: "QuizApp"):
        super().__init__()
        self._app        = app
        self._webviews   : dict[str, WebKit2.WebView] = {}
        self._save_timer = None
        self._pinned     = False
        self._pin_timer  = None
        self._locked_x   = 100
        self._locked_y   = 100
        self._locked_w   = 1100
        self._locked_h   = 700

        self.set_default_size(1100, 700)

        # ── Header bar ────────────────────────────────────────────────────
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(False)
        hb.set_title("Quiz Applet")
        self.set_titlebar(hb)

        # Droite : ✕ ⚙ 📌 ⊞ ✚
        hb.pack_end(_hb_btn("✕", "Fermer l'onglet courant",
                             lambda *_: self._close_current_tab()))
        hb.pack_end(_hb_btn("⚙", "Configurer l'onglet courant",
                             lambda *_: self._config_current_tab()))

        # Bouton épingle
        self._pin_btn = Gtk.ToggleButton()
        self._pin_btn.set_tooltip_text(
            "📌  Épingler au premier plan\n"
            "Verrouille aussi la position et la taille")
        self._pin_btn.set_active(False)
        self._update_pin_button_ui()
        self._pin_btn.connect("toggled", self._on_pin_toggled)
        hb.pack_end(self._pin_btn)

        hb.pack_end(_hb_btn("⊞", "Passer en mode fenêtres séparées",
                             lambda *_: GLib.idle_add(self._app.switch_mode)))
        hb.pack_end(_hb_btn("✚", "Nouvel onglet",
                             lambda *_: self._app.create_new_window_dialog(self)))

        # ── Notebook ──────────────────────────────────────────────────────
        self._nb = Gtk.Notebook()
        self._nb.set_tab_pos(Gtk.PositionType.TOP)
        self._nb.set_scrollable(True)
        self._nb.set_show_border(False)
        self._nb.connect("switch-page", self._on_switch_page)
        self.add(self._nb)

        self.connect("delete-event",    self._on_delete)
        self.connect("configure-event", self._on_configure)
        self.connect("realize",         lambda *_: GLib.idle_add(self._apply_hints))

        for wcfg in self._app.config["windows"]:
            self._add_tab(wcfg)

        self.show_all()

    # ── Épingle (tab window) ──────────────────────────────────────────────

    def _update_pin_button_ui(self):
        child = self._pin_btn.get_child()
        if child:
            self._pin_btn.remove(child)
        img = _make_pin_image(active=self._pinned)
        self._pin_btn.add(img)
        img.show()
        ctx = self._pin_btn.get_style_context()
        if self._pinned:
            ctx.add_class("pin-active")
        else:
            ctx.remove_class("pin-active")

    def _on_pin_toggled(self, btn):
        self._pinned = btn.get_active()
        if self._pinned:
            x, y = self.get_position()
            w, h = self.get_size()
            self._locked_x, self._locked_y = x, y
            self._locked_w, self._locked_h = w, h
            # Figer la taille AVANT set_resizable(False)
            self.set_size_request(w, h)
            self.resize(w, h)
            self.set_resizable(False)
            self.set_keep_above(True)
            try:
                self.present()
            except Exception:
                pass
            self._pin_timer = GLib.timeout_add(self._PIN_INTERVAL, self._enforce_pin)
        else:
            # Libérer la contrainte de taille AVANT de rendre la fenêtre redimensionnable
            self.set_size_request(-1, -1)
            self.set_resizable(True)
            self.set_keep_above(False)
            if self._pin_timer:
                GLib.source_remove(self._pin_timer)
                self._pin_timer = None
        self._update_pin_button_ui()

    def _enforce_pin(self) -> bool:
        if not self._pinned:
            return False
        self.set_keep_above(True)
        try:
            self.present()
        except Exception:
            pass
        cx, cy = self.get_position()
        if abs(cx - self._locked_x) > 8 or abs(cy - self._locked_y) > 8:
            self.move(self._locked_x, self._locked_y)
        return True

    def _apply_hints(self):
        if not self._pinned:
            self.set_keep_above(False)
        return False

    # ── Onglets ───────────────────────────────────────────────────────────

    def _make_tab_label(self, wcfg: dict) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=wcfg["name"])
        box.pack_start(lbl, True, True, 0)
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_focus_on_click(False)
        btn.add(Gtk.Label(label="✕"))
        btn.get_style_context().add_class("flat")

        def _on_close(b, wid=wcfg["id"]):
            self._close_tab(wid)

        btn.connect("clicked", _on_close)
        box.pack_start(btn, False, False, 0)
        box.show_all()
        return box

    def _add_tab(self, wcfg: dict):
        wid = wcfg["id"]
        if wid in self._webviews:
            return
        wv = WebKit2.WebView()
        wv.load_uri(wcfg.get("url", "https://www.google.com"))
        wv.show()
        self._webviews[wid] = wv
        self._nb.append_page(wv, self._make_tab_label(wcfg))
        self._nb.set_tab_reorderable(wv, True)

    def add_new_tab(self, wcfg: dict):
        self._add_tab(wcfg)
        self.show_all()
        wv  = self._webviews.get(wcfg["id"])
        idx = self._nb.page_num(wv) if wv else -1
        if idx >= 0:
            self._nb.set_current_page(idx)

    def _close_tab(self, wid: str):
        if len(self._app.config["windows"]) <= 1:
            _info_dialog(self, "Impossible de supprimer le dernier onglet.")
            return
        wv = self._webviews.pop(wid, None)
        if wv:
            idx = self._nb.page_num(wv)
            if idx >= 0:
                self._nb.remove_page(idx)
            wv.destroy()
        self._app.config["windows"] = [
            w for w in self._app.config["windows"] if w["id"] != wid]
        self._app.save()
        self._app.rebuild_tray_menu()

    def _current_wid(self) -> str | None:
        idx = self._nb.get_current_page()
        if idx < 0:
            return None
        wv = self._nb.get_nth_page(idx)
        return next((w for w, v in self._webviews.items() if v is wv), None)

    def _close_current_tab(self):
        wid = self._current_wid()
        if wid:
            self._close_tab(wid)

    def _config_current_tab(self):
        wid = self._current_wid()
        if not wid:
            return
        win_cfg = next(
            (w for w in self._app.config["windows"] if w["id"] == wid), None)
        if not win_cfg:
            return
        dlg = ConfigDialog(self, win_cfg)
        if dlg.run() == Gtk.ResponseType.OK:
            vals = dlg.get_values()
            win_cfg.update(vals)
            wv = self._webviews.get(wid)
            if wv:
                idx = self._nb.page_num(wv)
                if idx >= 0:
                    self._nb.set_tab_label(wv, self._make_tab_label(win_cfg))
                if vals.get("url") and vals["url"] != wv.get_uri():
                    wv.load_uri(vals["url"])
            self._app.save()
        dlg.destroy()

    # ── Signaux ───────────────────────────────────────────────────────────

    def _on_switch_page(self, nb, page, idx):
        wv  = self._nb.get_nth_page(idx)
        wid = next((w for w, v in self._webviews.items() if v is wv), None)
        if wid:
            wcfg = next(
                (c for c in self._app.config["windows"] if c["id"] == wid), None)
            if wcfg:
                self.get_titlebar().set_title(
                    f"Quiz Applet  —  {wcfg['name']}")

    def _on_delete(self, *_):
        self.hide()
        return True

    def _on_configure(self, widget, event):
        if self._pinned:
            return False
        if self._save_timer:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(500, self._flush_save)
        return False

    def _flush_save(self):
        self._app.save()
        self._save_timer = None
        return False

    def destroy(self):
        if self._pin_timer:
            GLib.source_remove(self._pin_timer)
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────

class QuizApp:

    def __init__(self):
        self.config     = load_config()
        self.windows    : dict[str, QuizWindow] = {}
        self.tab_window : QuizTabWindow | None = None
        self.tray       = None

    def _current_backend(self) -> str:
        env = os.environ.get("GDK_BACKEND", "").lower()
        if env in ("x11", "wayland"):
            return env
        try:
            display = Gdk.Display.get_default()
            if display:
                return display.get_backend()
        except Exception:
            pass
        return "auto"

    def _set_backend_and_restart(self, backend: str):
        if backend not in ("auto", "wayland", "x11"):
            return
        self.config["backend"] = backend
        self.save()

        env = os.environ.copy()
        if backend == "auto":
            env.pop("GDK_BACKEND", None)
        else:
            env["GDK_BACKEND"] = backend

        python = sys.executable
        script = os.path.abspath(__file__)
        os.execvpe(python, [python, script], env)

    @property
    def mode(self) -> str:
        return self.config.get("display_mode", "windowed")

    @mode.setter
    def mode(self, value: str):
        self.config["display_mode"] = value

    def save(self):
        save_config(self.config)

    # ── Basculement de mode ───────────────────────────────────────────────

    def switch_mode(self):
        if self.mode == "windowed":
            self._destroy_windows()
            self.mode = "tabbed"
            self.tab_window = QuizTabWindow(self)
        else:
            self._destroy_tab_window()
            self.mode = "windowed"
            for wcfg in self.config["windows"]:
                wcfg["enabled"] = True
                self._open_window(wcfg)
        self.save()
        self.rebuild_tray_menu()
        return False

    def _destroy_windows(self):
        for win in list(self.windows.values()):
            win.destroy()
        self.windows.clear()

    def _destroy_tab_window(self):
        if self.tab_window:
            self.tab_window.destroy()
            self.tab_window = None

    # ── Gestion fenêtres ──────────────────────────────────────────────────

    def _open_window(self, win_cfg: dict):
        wid = win_cfg["id"]
        if wid not in self.windows:
            self.windows[wid] = QuizWindow(win_cfg, self)
        else:
            w = self.windows[wid]
            if not w.get_visible():
                w.show_all()
                GLib.idle_add(w._apply_hints)
        win_cfg["enabled"] = True

    def toggle_window_by_id(self, wid: str):
        win_cfg = next(
            (w for w in self.config["windows"] if w["id"] == wid), None)
        if win_cfg is None:
            return

        if self.mode == "tabbed":
            if self.tab_window:
                if not self.tab_window.get_visible():
                    self.tab_window.show_all()
                wv = self.tab_window._webviews.get(wid)
                if wv:
                    idx = self.tab_window._nb.page_num(wv)
                    if idx >= 0:
                        self.tab_window._nb.set_current_page(idx)
                self.tab_window.present()
        else:
            win = self.windows.get(wid)
            if win is None:
                self._open_window(win_cfg)
            elif win.get_visible():
                win.hide()
                win_cfg["enabled"] = False
            else:
                win.show_all()
                GLib.idle_add(win._apply_hints)
                win_cfg["enabled"] = True
            self.save()
            self.rebuild_tray_menu()

    # ── Créer / supprimer ─────────────────────────────────────────────────

    def create_new_window_dialog(self, parent=None):
        GLib.idle_add(self._new_window_gtk, parent)

    def _new_window_gtk(self, parent):
        dlg = NewWindowDialog(parent)
        if dlg.run() == Gtk.ResponseType.OK:
            name, url = dlg.get_values()
            cfg = new_win_cfg(name or "Nouvelle fenêtre",
                              url  or "https://www.google.com")
            self.config["windows"].append(cfg)
            if self.mode == "tabbed" and self.tab_window:
                self.tab_window.add_new_tab(cfg)
            else:
                self._open_window(cfg)
            self.save()
            self.rebuild_tray_menu()
        dlg.destroy()
        return False

    def delete_window_dialog(self):
        GLib.idle_add(self._delete_window_gtk)

    def _delete_window_gtk(self):
        wins = self.config["windows"]
        if len(wins) <= 1:
            _info_dialog(None, "Impossible de supprimer la dernière fenêtre.")
            return False
        dlg = DeleteWindowDialog(None, wins)
        if dlg.run() == Gtk.ResponseType.OK:
            wid = dlg.get_selected_id()
            if wid:
                if self.mode == "tabbed" and self.tab_window:
                    self.tab_window._close_tab(wid)
                else:
                    win = self.windows.pop(wid, None)
                    if win:
                        win.destroy()
                    self.config["windows"] = [
                        w for w in wins if w["id"] != wid]
                    self.save()
                    self.rebuild_tray_menu()
        dlg.destroy()
        return False

    # ── System Tray ───────────────────────────────────────────────────────

    def rebuild_tray_menu(self):
        if not self.tray:
            return

        mode_label = ("⊞  Mode fenêtres" if self.mode == "tabbed"
                      else "⊟  Mode onglets")

        def _switch(icon, item):
            GLib.idle_add(self.switch_mode)

        def _backend_label(value: str) -> str:
            current = self.config.get("backend", "auto")
            mark = "✓" if current == value else "○"
            return f"{mark} {value.title()}"

        def _set_backend(icon, item, backend: str):
            if self.config.get("backend", "auto") == backend:
                return
            GLib.idle_add(self._set_backend_and_restart, backend)

        items = [
            pystray.MenuItem(f"Quiz Applet  v{VERSION}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(mode_label, _switch),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Backend :", None, enabled=False),
            pystray.MenuItem(_backend_label("auto"), lambda icon, item: _set_backend(icon, item, "auto")),
            pystray.MenuItem(_backend_label("x11"), lambda icon, item: _set_backend(icon, item, "x11")),
            pystray.MenuItem(_backend_label("wayland"), lambda icon, item: _set_backend(icon, item, "wayland")),
            pystray.Menu.SEPARATOR,
        ]

        def make_toggle(w):
            def _cb(icon, item):
                GLib.idle_add(self.toggle_window_by_id, w)
            return _cb

        for wcfg in self.config["windows"]:
            wid     = wcfg["id"]
            pinned  = wcfg.get("pinned", False)
            if self.mode == "tabbed":
                visible = (self.tab_window is not None
                           and self.tab_window.get_visible())
            else:
                win = self.windows.get(wid)
                visible = win is not None and win.get_visible()
            state = "✓" if visible else "○"
            pin   = "  📌" if pinned else ""
            label = f"{state}{pin}  {wcfg['name']}"
            items.append(pystray.MenuItem(label, make_toggle(wid)))

        def _new(icon, item):    self.create_new_window_dialog()
        def _del(icon, item):    self.delete_window_dialog()
        def _quit_cb(icon, item): self._quit()

        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✚  Nouvelle fenêtre…",       _new),
            pystray.MenuItem("🗑  Supprimer une fenêtre…", _del),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter",                     _quit_cb),
        ]

        self.tray.menu = pystray.Menu(*items)

    def _build_tray(self):
        if not _HAS_TRAY:
            return
        self.tray = pystray.Icon(
            name  = "quiz-applet",
            icon  = make_tray_icon(),
            title = f"Quiz Applet v{VERSION}",
            menu  = pystray.Menu(
                pystray.MenuItem("Chargement…", None, enabled=False)),
        )
        self.rebuild_tray_menu()

    # ── Autostart ─────────────────────────────────────────────────────────

    def update_autostart(self, enabled: bool):
        self.config["autostart"] = enabled
        if enabled:
            script = os.path.abspath(__file__)
            os.makedirs(AUTOSTART_DIR, exist_ok=True)
            with open(AUTOSTART_FILE, "w") as f:
                f.write(
                    "[Desktop Entry]\nType=Application\n"
                    f"Name=Quiz Applet\nExec=python3 {script}\n"
                    "Hidden=false\nNoDisplay=false\n"
                    "X-GNOME-Autostart-enabled=true\n")
        elif os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)
        self.save()

    # ── Quit ──────────────────────────────────────────────────────────────

    def _quit(self):
        GLib.idle_add(self._quit_gtk)

    def _quit_gtk(self):
        self.save()
        if self.tray:
            self.tray.stop()
        Gtk.main_quit()
        return False

    # ── Run ───────────────────────────────────────────────────────────────

    def run(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        _apply_css()

        if self.mode == "tabbed":
            self.tab_window = QuizTabWindow(self)
        else:
            for wcfg in self.config["windows"]:
                if wcfg.get("enabled", True):
                    self._open_window(wcfg)

        self._build_tray()
        if self.tray:
            threading.Thread(target=self.tray.run, daemon=True).start()
        else:
            print(f"[Quiz Applet v{VERSION}] Sans tray — Ctrl+C pour quitter.")

        signal.signal(signal.SIGINT, lambda *_: self._quit())
        Gtk.main()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    QuizApp().run()
