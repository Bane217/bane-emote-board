import sys
import os
import json
import requests
import shutil
import webbrowser
import mimetypes
from pathlib import Path
import math
import unicodedata

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea,
                             QGridLayout, QLabel, QFrame, QMenu, QTabWidget,
                             QFileDialog, QMessageBox, QComboBox, QDialog,
                             QFormLayout, QColorDialog, QStackedLayout, QSizePolicy,
                             QInputDialog)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QUrl, QSize, QMimeData,
                          QTimer, QPropertyAnimation, QEasingCurve, QPoint, QPointF)
from PyQt6.QtGui import (QPixmap, QMovie, QAction, QDragEnterEvent,
                         QDropEvent, QCursor, QColor, QIcon, QPainter, QPainterPath, QPen, QBrush, QPolygonF, QFont)

# ==========================================
# CONSTANTS & SETUP
# ==========================================
DATA_DIR = Path.home() / ".local" / "share" / "bane-emote-board"
FAVS_FILE = DATA_DIR / "favorites.json"
CONFIG_FILE = DATA_DIR / "config.json"
IMPORTS_FILE = DATA_DIR / "imports.json"
LOCAL_IMG_DIR = DATA_DIR / "local_images"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_IMG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TENOR_KEY = "LIVDSRZULELA"
BATCH_SIZE = 50
CARD_WIDTH = 180
MIN_SPACING = 10

# ==========================================
# THEME & CONFIG MANAGER
# ==========================================
DEFAULT_THEME = {
    "bg_primary": "#121212",
    "bg_secondary": "#1e1e1e",
    "bg_tertiary": "#2d2d2d",
    "bg_canvas": "#121212",    # <--- NEW: Background behind the cards
    "accent": "#007acc",
    "text_primary": "#ffffff",
    "text_secondary": "#bbbbbb",
    "border": "#3e3e3e",
    "success": "#28a745",
    "danger": "#dc3545"
}

def load_config():
    cfg = {
        "tenor_key": DEFAULT_TENOR_KEY,
        "theme": DEFAULT_THEME.copy()
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                for key, value in saved.items():
                    if key != "theme":
                        cfg[key] = value
                if "theme" in saved and isinstance(saved["theme"], dict):
                    cfg["theme"] = {**DEFAULT_THEME, **saved["theme"]}
        except Exception as e:
            print(f"Error loading config: {e}")
            pass
    return cfg

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def cleanup_temp_files():
    if DATA_DIR.exists():
        for p in DATA_DIR.glob("tmp_*"):
            try:
                p.unlink()
            except Exception as e:
                print(f"Failed to delete temp file {p}: {e}")

class ThemeManager:
    @staticmethod
    def get_stylesheet(theme):
        if not isinstance(theme, dict): theme = DEFAULT_THEME

        # Ensure new keys exist if loading old config
        bg_canvas = theme.get('bg_canvas', theme['bg_primary'])

        return f"""
            QMainWindow {{ background-color: {theme['bg_primary']}; }}
            QWidget {{ color: {theme['text_primary']}; font-family: 'Segoe UI', sans-serif; font-size: 14px; }}

            /* Canvas / Scroll Area Background */
            QScrollArea {{
                background-color: {bg_canvas};
                border: none;
            }}
            /* Specific ID for the content widget inside ScrollArea to ensure it gets colored */
            #ScrollContent {{
                background-color: {bg_canvas};
            }}

            QLineEdit {{
                background-color: {theme['bg_tertiary']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 8px;
                color: {theme['text_primary']};
            }}
            QLineEdit:focus {{ border: 1px solid {theme['accent']}; }}

            QPushButton {{
                background-color: {theme['bg_tertiary']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {theme['accent']}; border-color: {theme['accent']}; color: white; }}
            QPushButton:pressed {{ background-color: {theme['bg_primary']}; }}

            QComboBox {{
                background-color: {theme['bg_tertiary']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 5px;
            }}
            QComboBox::drop-down {{ border: 0px; }}

            QScrollBar:vertical {{
                border: none;
                background: {theme['bg_primary']};
                width: 14px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme['bg_tertiary']};
                min-height: 20px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            QTabWidget::pane {{ border: 1px solid {theme['border']}; border-radius: 4px; }}
            QTabBar::tab {{
                background: {theme['bg_secondary']};
                color: {theme['text_secondary']};
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {theme['bg_tertiary']};
                color: {theme['accent']};
                border-bottom: 2px solid {theme['accent']};
            }}

            QDialog {{ background-color: {theme['bg_primary']}; }}
            QLabel {{ color: {theme['text_primary']}; }}
            QMenu {{ background: {theme['bg_tertiary']}; color: {theme['text_primary']}; border: 1px solid {theme['border']}; }}
            QMenu::item {{ padding: 5px 20px; }}
            QMenu::item:selected {{ background: {theme['accent']}; }}
        """

# ==========================================
# GRAPHICS UTILS
# ==========================================
def create_star_icon(is_filled, size=48):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if is_filled:
        fill_color = QColor("#FFD700")
        stroke_color = QColor("#B8860B")
        stroke_width = 2
    else:
        fill_color = QColor(0, 0, 0, 100)
        stroke_color = QColor("white")
        stroke_width = 3

    cx, cy = size / 2, size / 2
    outer_radius = size * 0.45
    inner_radius = size * 0.20
    points = []

    angle = -math.pi / 2
    step = math.pi / 5

    for i in range(10):
        r = outer_radius if i % 2 == 0 else inner_radius
        x = cx + math.cos(angle) * r
        y = cy + math.sin(angle) * r
        points.append(QPointF(x, y))
        angle += step

    poly = QPolygonF(points)

    painter.setPen(QPen(stroke_color, stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QBrush(fill_color))
    painter.drawPolygon(poly)
    painter.end()

    return QIcon(pixmap)

# ==========================================
# DATA SOURCES
# ==========================================
class DataSource:
    def search(self, query, pos=None): pass

class TenorSource(DataSource):
    def search(self, query, pos=None):
        results = []
        config = load_config()
        api_key = config.get("tenor_key", DEFAULT_TENOR_KEY)
        next_pos = None

        if api_key == DEFAULT_TENOR_KEY:
            url = "https://g.tenor.com/v1/search"
            params = {"q": query, "key": api_key, "limit": BATCH_SIZE}
            if pos: params["pos"] = pos
        else:
            url = "https://tenor.googleapis.com/v2/search"
            params = {"q": query, "key": api_key, "client_key": "bane_board_v1", "limit": BATCH_SIZE, "media_filter": "minimal"}
            if pos: params["pos"] = pos

        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                next_pos = data.get("next") or data.get("next_pos")

                for item in data.get('results', []):
                    gif_url = None
                    if 'media_formats' in item:
                        formats = item['media_formats']
                        gif_obj = formats.get('tinygif') or formats.get('gif')
                        if gif_obj: gif_url = gif_obj['url']
                    elif 'media' in item:
                        media_list = item.get('media', [])
                        if media_list:
                            gif_obj = media_list[0].get('tinygif') or media_list[0].get('gif')
                            if gif_obj: gif_url = gif_obj['url']

                    title = item.get('content_description', '').strip() or item.get('title', '').strip() or "GIF"
                    if gif_url:
                        results.append({"name": title, "url": gif_url, "type": "gif", "source": "Tenor"})
        except Exception: pass
        return results, next_pos

class SevenTVSource(DataSource):
    def search(self, query, pos=None):
        page = pos if pos else 1
        results = []
        url = "https://7tv.io/v3/gql"
        payload = {
            "operationName": "Search",
            "variables": {"query": query, "limit": BATCH_SIZE, "page": page, "sort": {"value": "popularity", "order": "DESCENDING"}},
            "query": "query Search($query: String!, $page: Int, $limit: Int, $sort: Sort) { emotes(query: $query, page: $page, limit: $limit, sort: $sort) { items { id name host { url } } } }"
        }
        try:
            r = requests.post(url, json=payload, headers={"User-Agent": "BaneBoard/1.0", "Content-Type": "application/json"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("data") and data["data"].get("emotes"):
                    items = data["data"]["emotes"]["items"]
                    if not items: return [], None
                    for item in items:
                        name = item.get('name', 'Emote')
                        base = item.get('host', {}).get('url')
                        if base:
                            if base.startswith("//"): base = "https:" + base
                            results.append({"name": name, "url": f"{base}/2x.webp", "type": "webp", "source": "7TV"})
                    return results, page + 1
        except Exception: pass
        return results, None

class EmojiSource(DataSource):
    def __init__(self):
        self.all_emojis = []
        self._load_emojis()

    def _load_emojis(self):
        # Range includes standard emoticons, dingbats, supplemental symbols, and extended pictographs
        ranges = [
            (0x1F600, 0x1F64F), # Emoticons
            (0x1F300, 0x1F5FF), # Misc Symbols and Pictographs
            (0x1F680, 0x1F6FF), # Transport and Map
            (0x1F900, 0x1F9FF), # Supplemental Symbols and Pictographs
            (0x2600, 0x26FF),   # Misc Symbols
            (0x2700, 0x27BF),   # Dingbats
            (0x1F1E0, 0x1F1FF), # Flags
            (0x1FA70, 0x1FAFF)  # Symbols and Pictographs Extended-A
        ]

        seen = set()
        for start, end in ranges:
            for code in range(start, end + 1):
                char = chr(code)
                try:
                    name = unicodedata.name(char).lower()
                    if char not in seen:
                        self.all_emojis.append({
                            "name": name.title(),
                            "url": char,
                            "type": "emoji",
                            "source": "Emoji"
                        })
                        seen.add(char)
                except ValueError:
                    pass

    def search(self, query, pos=None):
        offset = pos if pos else 0
        results = []

        if query:
            q = query.lower()
            filtered = []

            for item in self.all_emojis:
                if q in item['name'].lower() or q == item['url']:
                    filtered.append(item)

            sliced = filtered[offset : offset + BATCH_SIZE]
            next_offset = offset + len(sliced)
            if next_offset >= len(filtered): next_offset = None

            return sliced, next_offset
        else:
            sliced = self.all_emojis[offset : offset + BATCH_SIZE]
            if not sliced: return [], None

            next_offset = offset + len(sliced)
            if next_offset >= len(self.all_emojis): next_offset = None
            return sliced, next_offset

class LocalSource(DataSource):
    def search(self, query, pos=None):
        offset = pos if pos else 0
        results = []
        if not LOCAL_IMG_DIR.exists(): return [], None

        imports_map = {}
        if IMPORTS_FILE.exists():
            try:
                with open(IMPORTS_FILE, 'r') as f: imports_map = json.load(f)
            except: pass

        all_files = []
        for f in os.listdir(LOCAL_IMG_DIR):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                if not query or query.lower() in f.lower():
                    all_files.append(f)

        sliced = all_files[offset : offset + BATCH_SIZE]
        if not sliced: return [], None

        for f in sliced:
            item = {
                "name": f,
                "url": str(LOCAL_IMG_DIR / f),
                "type": "local",
                "source": "Local"
            }
            if f in imports_map:
                item["original_url"] = imports_map[f]
            results.append(item)

        next_offset = offset + len(sliced)
        if next_offset >= len(all_files): next_offset = None
        return results, next_offset

# ==========================================
# WORKERS
# ==========================================
class SearchWorker(QThread):
    results_ready = pyqtSignal(list, object)
    def __init__(self, source, query, pos=None):
        super().__init__()
        self.source = source
        self.query = query
        self.pos = pos
    def run(self):
        res, next_pos = self.source.search(self.query, self.pos)
        self.results_ready.emit(res, next_pos)

class ImageDownloadWorker(QThread):
    image_loaded = pyqtSignal(bytes)
    failed = pyqtSignal(str)
    def __init__(self, url):
        super().__init__()
        self.url = url
    def run(self):
        try:
            r = requests.get(self.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200: self.image_loaded.emit(r.content)
            else: self.failed.emit(f"HTTP {r.status_code}")
        except Exception as e: self.failed.emit(str(e))

# ==========================================
# UI COMPONENTS
# ==========================================
class FullscreenViewer(QDialog):
    def __init__(self, file_path, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Details")
        self.resize(900, 750)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #050505; border: none;")
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_img)
        self.scroll.setWidget(container)
        layout.addWidget(self.scroll, 1)

        meta_frame = QFrame()
        cfg = load_config()
        th = cfg['theme']
        meta_frame.setStyleSheet(f"background: {th['bg_secondary']}; border-top: 1px solid {th['border']}; padding: 15px;")
        meta_layout = QGridLayout(meta_frame)
        meta_layout.setSpacing(10)

        lbl_name_val = QLabel(data.get('name', 'Unknown'))
        lbl_name_val.setStyleSheet(f"font-size: 16px; color: {th['text_primary']}; font-weight: bold;")

        self.lbl_dim_val = QLabel("Calculating...")
        self.lbl_dim_val.setStyleSheet(f"color: {th['text_primary']};")

        display_url = data.get('original_url', data['url'])
        lbl_src_val = QLabel(f"<a href='{display_url}' style='color: {th['accent']}; text-decoration: none;'>{display_url}</a>")
        lbl_src_val.setOpenExternalLinks(True)
        lbl_src_val.setWordWrap(True)

        lbl_dim_title = QLabel("Size:")
        lbl_dim_title.setStyleSheet(f"color: {th['text_secondary']}; font-weight: bold;")

        lbl_src_title = QLabel("Source:")
        lbl_src_title.setStyleSheet(f"color: {th['text_secondary']}; font-weight: bold;")

        meta_layout.addWidget(lbl_name_val, 0, 0, 1, 2)
        meta_layout.addWidget(lbl_dim_title, 1, 0)
        meta_layout.addWidget(self.lbl_dim_val, 1, 1)
        meta_layout.addWidget(lbl_src_title, 2, 0)
        meta_layout.addWidget(lbl_src_val, 2, 1)

        layout.addWidget(meta_frame, 0)

        if data['type'] == 'emoji':
            self.lbl_img.setText(data['url'])
            self.lbl_img.setStyleSheet("font-size: 350px; color: white; background: transparent;")
            self.lbl_dim_val.setText("Scalable (Text)")
        else:
            self.load_image(file_path, data['type'])

    def load_image(self, path, ftype):
        w, h = 0, 0
        if path.endswith(('.gif', '.webp')) or ftype == 'gif':
            movie = QMovie(path)
            if movie.isValid():
                self.lbl_img.setMovie(movie)
                movie.start()
                movie.jumpToFrame(0)
                sz = movie.currentImage().size()
                w, h = sz.width(), sz.height()
                movie.start()
        else:
            pix = QPixmap(path)
            if not pix.isNull():
                w, h = pix.width(), pix.height()
                if w > 1200 or h > 1200:
                    pix = pix.scaled(1200, 1200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_img.setPixmap(pix)

        self.lbl_dim_val.setText(f"{w} x {h} px")

class ImageCard(QFrame):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.local_path = None
        self.setFixedSize(CARD_WIDTH, CARD_WIDTH)

        # Initial Theme Application
        self.update_theme()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("border: none; background: transparent;")
        self.layout.addWidget(self.lbl)

        self.star_btn = QPushButton(self)
        self.star_btn.setFixedSize(36, 36)
        self.star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.star_btn.move(140, 5)
        self.star_btn.clicked.connect(self.toggle_fav)
        self.star_btn.setStyleSheet("background: transparent; border: none;")
        self.star_btn.setIconSize(QSize(32, 32))
        self.update_star_style(self.is_favorited())
        self.star_btn.hide()

        self.info_btn = QPushButton("i", self)
        self.info_btn.setFixedSize(30, 30)
        self.info_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.info_btn.clicked.connect(self.open_fullscreen)
        self.info_btn.move(140, 140)
        self.info_btn.hide()

        # Apply button styles (done in update_theme, but need to be sure)
        self.update_theme_buttons()

        if "error" in data:
            self.lbl.setText("Error")
            self.lbl.setStyleSheet("color: #e74c3c;")
        elif data['type'] == 'emoji':
            self.lbl.setText(data['url'])
            self.lbl.setStyleSheet("font-size: 130px; border: none; background: transparent;")
            self.local_path = "EMOJI"
        elif data['type'] == 'local':
            self.load_bytes(None, data['url'])
        else:
            self.lbl.setText("...")
            self.worker = ImageDownloadWorker(data['url'])
            self.worker.image_loaded.connect(self.load_bytes)
            self.worker.failed.connect(lambda: self.lbl.setText("X"))
            self.worker.start()

    def update_theme(self):
        self.cfg = load_config()
        self.theme = self.cfg['theme']

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme['bg_secondary']};
                border-radius: 12px;
                border: 1px solid {self.theme['border']};
            }}
            QFrame:hover {{
                border: 1px solid {self.theme['accent']};
                background-color: {self.theme['bg_tertiary']};
            }}
        """)
        self.update_theme_buttons()

    def update_theme_buttons(self):
        if hasattr(self, 'info_btn'):
             self.info_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.theme['accent']};
                    color: white;
                    border-radius: 15px;
                    font-family: serif;
                    font-weight: bold;
                    font-style: italic;
                    border: 1px solid rgba(255,255,255,0.3);
                    font-size: 16px;
                }}
                QPushButton:hover {{ background-color: white; color: {self.theme['accent']}; }}
            """)

    def is_favorited(self):
        if not FAVS_FILE.exists(): return False
        try:
            with open(FAVS_FILE, 'r') as f:
                favs = json.load(f)
                return any(x['url'] == self.data['url'] for x in favs)
        except: return False

    def update_star_style(self, is_fav):
        icon = create_star_icon(is_filled=is_fav, size=64)
        self.star_btn.setIcon(icon)

    def toggle_fav(self):
        favs = []
        if FAVS_FILE.exists():
            try:
                with open(FAVS_FILE, 'r') as f: favs = json.load(f)
            except: pass

        found = False
        for i, item in enumerate(favs):
            if item['url'] == self.data['url']:
                favs.pop(i)
                found = True
                break

        if not found:
            favs.append(self.data)
            self.flash("★ Saved")
        else:
            self.flash("Removed")

        with open(FAVS_FILE, 'w') as f: json.dump(favs, f)
        self.update_star_style(not found)
        mw = self.window()
        if hasattr(mw, 'refresh_favs_if_visible'): mw.refresh_favs_if_visible()

    def enterEvent(self, event):
        if "error" not in self.data:
            self.star_btn.show()
            self.info_btn.show()
            self.move(self.x(), self.y() - 2)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.star_btn.hide()
        self.info_btn.hide()
        self.move(self.x(), self.y() + 2)
        super().leaveEvent(event)

    def load_bytes(self, data_bytes, local_path=None):
        if local_path:
            self.local_path = local_path
        else:
            ext = ".gif" if self.data['type'] == 'gif' else ".webp"
            fname = f"tmp_{abs(hash(self.data['url']))}{ext}"
            self.local_path = str(DATA_DIR / fname)
            if data_bytes:
                with open(self.local_path, 'wb') as f: f.write(data_bytes)

        is_anim = self.local_path.endswith(('.gif', '.webp'))
        if is_anim:
            movie = QMovie(self.local_path)
            if movie.isValid():
                movie.setScaledSize(QSize(160, 160))
                self.lbl.setMovie(movie)
                movie.start()
                return

        pix = QPixmap(self.local_path)
        if not pix.isNull():
            pix = pix.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if child not in [self.star_btn, self.info_btn]:
                self.copy_link()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu(event)

    def copy_link(self):
        cb = QApplication.clipboard()

        if self.data.get('type') == 'emoji':
            cb.setText(self.data['url'])
            self.flash("Copied Char")
            return

        if self.data.get('original_url'):
            cb.setText(self.data['original_url'])
            self.flash("Link Copied")
        elif self.data['source'] == 'Local':
            mime = QMimeData()
            u = QUrl.fromLocalFile(self.data['url'])
            mime.setUrls([u])
            cb.setMimeData(mime)
            self.flash("File Copied")
        else:
            cb.setText(self.data['url'])
            self.flash("Link Copied")

    def flash(self, text):
        lbl = QLabel(text, self)
        lbl.setStyleSheet(f"background: {self.theme['accent']}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
        lbl.adjustSize()
        lbl.move((180 - lbl.width())//2, (180 - lbl.height())//2)
        lbl.show()
        QTimer.singleShot(1000, lbl.deleteLater)

    def open_fullscreen(self):
        if (self.local_path and os.path.exists(self.local_path)) or self.data['type'] == 'emoji':
            FullscreenViewer(self.local_path, self.data, self.window()).exec()

    def context_menu(self, event):
        menu = QMenu(self)
        action_copy_link = QAction("Copy", self)
        action_copy_link.triggered.connect(self.copy_link)
        menu.addAction(action_copy_link)
        action_save_as = QAction("Save As...", self)
        action_save_as.triggered.connect(self.save_image_as)
        menu.addAction(action_save_as)
        if self.data.get('source') == 'Local':
            menu.addSeparator()
            act_del = QAction("Delete File", self)
            act_del.triggered.connect(self.delete_file)
            menu.addAction(act_del)
        menu.exec(event.globalPosition().toPoint())

    def save_image_as(self):
        if self.data['type'] == 'emoji':
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Emoji", "emoji.png", "PNG (*.png)")
            if save_path:
                pix = QPixmap(512, 512)
                pix.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pix)
                font = QFont()
                font.setPixelSize(400)
                painter.setFont(font)
                painter.setPen(QColor("white"))
                painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, self.data['url'])
                painter.end()
                pix.save(save_path)
                self.flash("Saved!")
            return

        if not self.local_path or not os.path.exists(self.local_path): return
        ext = ".png"
        if self.data['type'] == 'gif': ext = ".gif"
        elif self.data['type'] == 'webp': ext = ".webp"
        default_name = self.data['name'].replace(" ", "_") + ext
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Image", default_name, f"Images (*{ext})")
        if save_path:
            try:
                shutil.copy(self.local_path, save_path)
                self.flash("Saved!")
            except Exception as e:
                self.flash("Error")
                print(e)

    def delete_file(self):
        if self.local_path and os.path.exists(self.local_path):
            try:
                os.remove(self.local_path)
                self.deleteLater()
            except: pass

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Theme")
        self.resize(500, 450)
        self.config = load_config()
        self.theme_data = self.config['theme']
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        gen_tab = QWidget()
        gen_layout = QFormLayout(gen_tab)
        gen_layout.setSpacing(15)

        self.key_input = QLineEdit(self.config.get("tenor_key", ""))
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)

        gen_layout.addRow("Tenor API Key:", self.key_input)

        tabs.addTab(gen_tab, "General")

        theme_tab = QWidget()
        self.theme_layout = QGridLayout(theme_tab)
        self.theme_layout.setSpacing(10)
        self.color_buttons = {}
        colors_to_edit = {
            "Background (Main)": "bg_primary",
            "Canvas Background": "bg_canvas",    # <--- NEW SETTING
            "Card Color": "bg_secondary",
            "Input Color": "bg_tertiary",
            "Accent Color": "accent",
            "Text Color": "text_primary",
            "Border Color": "border"
        }
        row = 0
        for label, key in colors_to_edit.items():
            lbl = QLabel(label)
            btn = QPushButton()
            btn.setFixedSize(60, 30)
            c_val = self.theme_data.get(key, DEFAULT_THEME.get(key, "#000"))
            btn.setStyleSheet(f"background-color: {c_val}; border: 1px solid #555; border-radius: 4px;")
            btn.clicked.connect(lambda checked, k=key, b=btn: self.pick_color(k, b))
            self.color_buttons[key] = btn
            self.theme_layout.addWidget(lbl, row, 0)
            self.theme_layout.addWidget(btn, row, 1)
            row += 1

        tabs.addTab(theme_tab, "Theming")

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"background: {self.theme_data.get('accent', '#007acc')}; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        btn_box.addStretch()
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def pick_color(self, key, btn):
        curr = self.theme_data.get(key, "#000000")
        color = QColorDialog.getColor(QColor(curr), self, "Pick Color")
        if color.isValid():
            hex_c = color.name()
            self.theme_data[key] = hex_c
            btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid #555; border-radius: 4px;")

    def save_settings(self):
        self.config['tenor_key'] = self.key_input.text()
        self.config['theme'] = self.theme_data
        save_config(self.config)
        self.accept()
        if self.parent():
            self.parent().apply_theme()

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bane Emote Board")
        self.resize(1150, 850)
        cleanup_temp_files()

        self.sources = {
            "Tenor": TenorSource(),
            "7TV": SevenTVSource(),
            "Emojis": EmojiSource(),
            "Local Images": LocalSource()
        }

        self.next_ptr = None
        self.is_loading = False
        self.current_query = ""
        self.current_source_name = ""

        self.search_card_widgets = []
        self.fav_card_widgets = []

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(100)
        self.resize_timer.timeout.connect(self.reflow_grids)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Header ===
        header = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.addItems(self.sources.keys())
        self.combo.setFixedWidth(160)
        self.combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.returnPressed.connect(self.search)
        btn_search = QPushButton("Search")
        btn_search.setIcon(QIcon.fromTheme("system-search"))
        btn_search.clicked.connect(self.search)
        btn_search.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_import = QPushButton("Import")
        self.btn_import.clicked.connect(self.show_import_menu)
        self.btn_import.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_settings = QPushButton("⚙")
        btn_settings.setFixedSize(40, 36)
        btn_settings.clicked.connect(self.open_settings)
        header.addWidget(self.combo)
        header.addWidget(self.search_input)
        header.addWidget(btn_search)
        header.addWidget(self.btn_import)
        header.addWidget(btn_settings)
        main_layout.addLayout(header)

        # === Tabs ===
        self.tabs = QTabWidget()

        # -- Search Tab --
        self.res_area = QScrollArea()
        self.res_area.setWidgetResizable(True)
        self.res_widget = QWidget()
        # IMPORTANT: Set ID for CSS styling of background
        self.res_widget.setObjectName("ScrollContent")

        self.res_grid = QGridLayout(self.res_widget)
        self.res_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.res_area.setWidget(self.res_widget)
        self.res_area.verticalScrollBar().valueChanged.connect(self.check_scroll)
        self.tabs.addTab(self.res_area, "Search Results")

        # -- Favorites Tab --
        self.fav_tab_widget = QWidget()
        self.fav_tab_layout = QVBoxLayout(self.fav_tab_widget)
        self.fav_tab_layout.setContentsMargins(0, 0, 0, 0)

        # Favorites Search Bar
        fav_search_bar_layout = QHBoxLayout()
        self.fav_search_input = QLineEdit()
        self.fav_search_input.setPlaceholderText("Search saved favorites...")
        self.fav_search_input.textChanged.connect(self.load_favorites)
        fav_search_bar_layout.addWidget(self.fav_search_input)

        self.fav_tab_layout.addLayout(fav_search_bar_layout)

        self.fav_area = QScrollArea()
        self.fav_area.setWidgetResizable(True)
        self.fav_widget = QWidget()
        # IMPORTANT: Set ID for CSS styling of background
        self.fav_widget.setObjectName("ScrollContent")

        self.fav_grid = QGridLayout(self.fav_widget)
        self.fav_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.fav_area.setWidget(self.fav_widget)

        self.fav_tab_layout.addWidget(self.fav_area)
        self.tabs.addTab(self.fav_tab_widget, "Favorites (★)")

        self.tabs.currentChanged.connect(self.on_tab_change)
        main_layout.addWidget(self.tabs)
        self.setAcceptDrops(True)

        # Apply theme LAST so object names are respected
        self.apply_theme()
        self.load_favorites()

    def resizeEvent(self, event):
        self.resize_timer.start()
        super().resizeEvent(event)

    def reflow_grids(self):
        width = self.res_area.viewport().width()
        cols = (width - MIN_SPACING) // (CARD_WIDTH + MIN_SPACING)
        cols = max(1, int(cols))

        remaining_space = width - (cols * CARD_WIDTH)
        spacing = int(remaining_space / (cols + 1))
        if spacing < MIN_SPACING: spacing = MIN_SPACING

        self.res_grid.setHorizontalSpacing(spacing)
        self.res_grid.setVerticalSpacing(spacing)
        self.res_grid.setContentsMargins(spacing, spacing, spacing, spacing)

        for i, widget in enumerate(self.search_card_widgets):
            row = i // cols
            col = i % cols
            self.res_grid.addWidget(widget, row, col)

        self.fav_grid.setHorizontalSpacing(spacing)
        self.fav_grid.setVerticalSpacing(spacing)
        self.fav_grid.setContentsMargins(spacing, spacing, spacing, spacing)

        for i, widget in enumerate(self.fav_card_widgets):
            row = i // cols
            col = i % cols
            self.fav_grid.addWidget(widget, row, col)

        if self.tabs.currentIndex() == 0:
             QTimer.singleShot(50, self.fill_screen_if_needed)

    def closeEvent(self, event):
        cleanup_temp_files()
        event.accept()

    def apply_theme(self):
        cfg = load_config()
        self.setStyleSheet(ThemeManager.get_stylesheet(cfg['theme']))

        # Refresh individual cards
        all_cards = self.search_card_widgets + self.fav_card_widgets
        for card in all_cards:
            if isinstance(card, ImageCard):
                card.update_theme()

    def check_scroll(self):
        bar = self.res_area.verticalScrollBar()
        if bar.value() > bar.maximum() * 0.9:
            if not self.is_loading and self.next_ptr:
                self.load_more()

    def search(self):
        self.tabs.setCurrentIndex(0)
        self.current_source_name = self.combo.currentText()
        self.current_query = self.search_input.text()
        self.next_ptr = None

        for w in self.search_card_widgets:
            w.deleteLater()
        self.search_card_widgets.clear()

        while self.res_grid.count():
            item = self.res_grid.takeAt(0)

        self.load_more()

    def load_more(self):
        self.is_loading = True
        if not self.search_card_widgets:
            loading_lbl = QLabel("Searching...")
            loading_lbl.setStyleSheet("color: #888; font-size: 16px; margin: 20px;")
            self.res_grid.addWidget(loading_lbl, 0, 0)
            self.loading_indicator = loading_lbl

        self.worker = SearchWorker(self.sources[self.current_source_name], self.current_query, self.next_ptr)
        self.worker.results_ready.connect(self.display_results)
        self.worker.start()

    def display_results(self, results, next_pos):
        self.is_loading = False
        self.next_ptr = next_pos

        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.deleteLater()
            del self.loading_indicator

        if not results and not self.search_card_widgets:
            lbl = QLabel("No results found.")
            self.res_grid.addWidget(lbl, 0, 0)
            self.search_card_widgets.append(lbl)
            return

        for item in results:
            card = ImageCard(item, self)
            self.search_card_widgets.append(card)

        self.reflow_grids()

        if self.next_ptr:
            QTimer.singleShot(50, self.fill_screen_if_needed)

    def fill_screen_if_needed(self):
        if self.is_loading or not self.next_ptr:
            return

        bar = self.res_area.verticalScrollBar()
        if bar.maximum() <= 0 or bar.value() >= bar.maximum() * 0.9:
            self.load_more()

    def load_favorites(self):
        for w in self.fav_card_widgets:
            w.deleteLater()
        self.fav_card_widgets.clear()
        while self.fav_grid.count():
            self.fav_grid.takeAt(0)

        query = self.fav_search_input.text().lower()

        if FAVS_FILE.exists():
            try:
                with open(FAVS_FILE, 'r') as f:
                    favs = json.load(f)

                    filtered_favs = []
                    for item in favs:
                        if not query or query in item.get('name', '').lower() or query in item.get('url', '').lower():
                            filtered_favs.append(item)

                    if filtered_favs:
                        for item in filtered_favs:
                            card = ImageCard(item, self)
                            self.fav_card_widgets.append(card)
                    else:
                        lbl = QLabel("No favorites match search." if query else "No favorites yet. Click the ★ on an image!")
                        self.fav_card_widgets.append(lbl)
            except:
                pass

        self.reflow_grids()

    def on_tab_change(self, index):
        if index == 1: self.load_favorites()

    def refresh_favs_if_visible(self):
        if self.tabs.currentIndex() == 1:
            self.load_favorites()

    def open_settings(self):
        SettingsDialog(self).exec()

    def show_import_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: {self.palette().window().color().name()}; border: 1px solid #555; }}")
        act_file = QAction("From File...", self)
        act_file.triggered.connect(self.import_files)
        act_url = QAction("From URL...", self)
        act_url.triggered.connect(self.import_from_url)
        menu.addAction(act_file)
        menu.addAction(act_url)
        menu.exec(QCursor.pos())

    def import_from_url(self):
        url, ok = QInputDialog.getText(self, "Import from URL", "Enter Image URL:")
        if ok and url:
            try:
                try: h = requests.head(url, timeout=5)
                except: pass
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    ext = mimetypes.guess_extension(r.headers.get('content-type'))
                    if not ext:
                        if url.endswith('.gif'): ext = '.gif'
                        elif url.endswith('.webp'): ext = '.webp'
                        elif url.endswith('.png'): ext = '.png'
                        else: ext = '.jpg'
                    fname = f"imported_{abs(hash(url))}{ext}"
                    save_path = LOCAL_IMG_DIR / fname
                    with open(save_path, 'wb') as f: f.write(r.content)

                    try:
                        imports = {}
                        if IMPORTS_FILE.exists():
                            with open(IMPORTS_FILE, 'r') as f: imports = json.load(f)
                        imports[fname] = url
                        with open(IMPORTS_FILE, 'w') as f: json.dump(imports, f)
                    except Exception as e: print(e)

                    QMessageBox.information(self, "Success", "Image imported!")
                    if "Local" in self.combo.currentText(): self.search()
                else:
                    QMessageBox.warning(self, "Error", f"Could not download image. HTTP {r.status_code}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.png *.jpg *.gif *.webp)")
        count = 0
        for f in files:
            try:
                shutil.copy(f, LOCAL_IMG_DIR)
                count += 1
            except: pass
        if count:
            QMessageBox.information(self, "Import", f"Imported {count} images.")
            if "Local" in self.combo.currentText(): self.search()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.accept()
        else: e.ignore()

    def dropEvent(self, e: QDropEvent):
        count = 0
        for url in e.mimeData().urls():
            f = url.toLocalFile()
            if os.path.isfile(f) and f.lower().endswith(('.png', '.jpg', '.gif', '.webp')):
                shutil.copy(f, LOCAL_IMG_DIR)
                count += 1
        if count:
            QMessageBox.information(self, "Dropped", f"Added {count} images to Local.")
            if "Local" in self.combo.currentText(): self.search()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())
