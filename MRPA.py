import sys
import threading
import json
import textwrap
from functools import partial
import os 

import requests
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, Slot, QTimer, Property, QUrl 
from PySide6.QtGui import QFont, QPixmap, QDesktopServices, QColor 
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QLabel, QScrollArea, QFrame, QPushButton,
                               QSpacerItem, QSizePolicy, QMessageBox, QFormLayout, 
                               QGraphicsOpacityEffect, QSpinBox, QColorDialog) # Added QSpinBox, QColorDialog

from io import BytesIO
from PIL import Image

# =================================================================================
# GLOBAL API KEY AND CONFIGURATION STATE
# =================================================================================

MISSING_API_KEY = None 

GEMINI_KEY_FILE = "gemini_api_key.txt"
OMDB_KEY_FILE = "omdb_api_key.txt"
CONFIG_FILE = "config.json" # New file for general settings

# Global mutable variables to hold the key contents and CWD
GLOBAL_GEMINI_API_KEY_CONTENT = ""
GLOBAL_OMDB_API_KEY_CONTENT = ""
GLOBAL_CWD = "" 

# API Keys used by API call functions
GEMINI_API_KEY = MISSING_API_KEY
OMDB_API_KEY = MISSING_API_KEY

# Global mutable variables for configuration (New)
GLOBAL_SUGGESTION_COUNT = 10 # Default to 10
GLOBAL_MOVIE_COLOR = "#1E90FF"  # Default Blue
GLOBAL_SHOW_COLOR = "#FF4500"   # Default Orange
GLOBAL_NEON_PINK = "#FF1493"    # Default Pink
GLOBAL_NEON_BLUE = "#1E90FF"    # Default Blue


def _read_key_content(filename: str, cwd: str) -> str:
    """Reads the raw content of the file or returns an empty string."""
    key_path = os.path.join(cwd, filename)
    if not os.path.exists(key_path):
        return ""
    try:
        with open(key_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"DEBUG: Error reading key file {filename}: {e}")
        return ""

def _save_key_content(filename: str, key_content: str):
    """Saves the key_content to the specified file in the determined CWD."""
    if not GLOBAL_CWD:
        raise RuntimeError("Cannot save key: Current Working Directory is not established.")

    key_path = os.path.join(GLOBAL_CWD, filename)
    try:
        with open(key_path, 'w') as f:
            f.write(key_content.strip())
        print(f"DEBUG: Successfully saved key content to: {key_path}")
    except Exception as e:
        raise RuntimeError(f"Error saving key to {filename}: {e}")

# NEW: Functions for Config Loading/Saving
def _load_config(cwd: str):
    """Loads application configuration from config.json."""
    global GLOBAL_SUGGESTION_COUNT, GLOBAL_MOVIE_COLOR, GLOBAL_SHOW_COLOR, GLOBAL_NEON_PINK, GLOBAL_NEON_BLUE
    
    config_path = os.path.join(cwd, CONFIG_FILE)
    if not os.path.exists(config_path):
        return # Use defaults if file doesn't exist

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
            # Load Suggestion Count (1-20)
            count = config.get('suggestion_count', 10)
            GLOBAL_SUGGESTION_COUNT = max(1, min(20, int(count)))
            
            # Load Colors
            GLOBAL_MOVIE_COLOR = config.get('movie_color', GLOBAL_MOVIE_COLOR)
            GLOBAL_SHOW_COLOR = config.get('show_color', GLOBAL_SHOW_COLOR)
            GLOBAL_NEON_PINK = config.get('neon_pink', GLOBAL_NEON_PINK)
            GLOBAL_NEON_BLUE = config.get('neon_blue', GLOBAL_NEON_BLUE)

    except Exception as e:
        print(f"DEBUG: Error loading configuration: {e}")

def _save_config(config: dict):
    """Saves application configuration to config.json and updates globals."""
    global GLOBAL_SUGGESTION_COUNT, GLOBAL_MOVIE_COLOR, GLOBAL_SHOW_COLOR, GLOBAL_NEON_PINK, GLOBAL_NEON_BLUE
    
    if not GLOBAL_CWD:
        raise RuntimeError("Cannot save config: Current Working Directory is not established.")

    config_path = os.path.join(GLOBAL_CWD, CONFIG_FILE)
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"DEBUG: Successfully saved configuration to: {config_path}")
        
        # Update Globals immediately after successful save
        _load_config(GLOBAL_CWD) 
        
    except Exception as e:
        raise RuntimeError(f"Error saving configuration to {CONFIG_FILE}: {e}")

        
def _setup_cwd_and_load_keys(first_load: bool = True):
    """
    Sets up the Current Working Directory (CWD) and loads all API keys 
    and configuration into their respective global variables.
    """
    global GLOBAL_GEMINI_API_KEY_CONTENT, GLOBAL_OMDB_API_KEY_CONTENT, GLOBAL_CWD
    global GEMINI_API_KEY, OMDB_API_KEY
    
    # Only perform CWD setup if not already set (or on first load)
    if not GLOBAL_CWD:
        try:
            script_path = os.path.abspath(sys.argv[0])
            script_dir = os.path.dirname(script_path)
        except IndexError:
            if first_load: print("DEBUG: sys.argv[0] failed to get script path.")
            return

        sub_folder_name = 'CONFIG'
        if not script_dir.endswith(sub_folder_name) and os.path.isdir(os.path.join(script_dir, sub_folder_name)):
            script_dir = os.path.join(script_dir, sub_folder_name)
            
        try:
            os.chdir(script_dir)
            GLOBAL_CWD = script_dir
            if first_load: print(f"DEBUG: Successfully set Current Working Directory (CWD) to: {GLOBAL_CWD}")
        except Exception as e:
            if first_load: print(f"DEBUG: FAILED to change CWD to {script_dir}. Error: {e}")
            return

    # NEW: Load configuration first
    _load_config(GLOBAL_CWD)

    # Load the key content strings
    GLOBAL_GEMINI_API_KEY_CONTENT = _read_key_content(GEMINI_KEY_FILE, GLOBAL_CWD)
    GLOBAL_OMDB_API_KEY_CONTENT = _read_key_content(OMDB_KEY_FILE, GLOBAL_CWD)

    # Set the keys used by the API call functions
    GEMINI_API_KEY = GLOBAL_GEMINI_API_KEY_CONTENT or MISSING_API_KEY
    OMDB_API_KEY = GLOBAL_OMDB_API_KEY_CONTENT or MISSING_API_KEY
    
# Initial load of keys and setup of CWD
_setup_cwd_and_load_keys()


# =================================================================================
# QUICK FILTER DATA (Unchanged)
# =================================================================================

TOP_MOVIES = [
    ("⭐ Highest Rated Films", "The Shawshank Redemption, The Godfather, The Dark Knight, 12 Angry Men, Schindler's List, Pulp Fiction, Lord of the Rings: The Return of the King, Forrest Gump, Fight Club, Inception"),
    ("🚀 Action / Sci-Fi", "Inception, Mad Max: Fury Road, Blade Runner 2049, Arrival, Terminator 2: Judgment Day, Dune, Children of Men, The Matrix, Interstellar, Alien"),
    ("😂 Comedy", "The Big Lebowski, Superbad, Monty Python and the Holy Grail, Airplane!, Shaun of the Dead, Hot Fuzz, Ferris Bueller's Day DayOff, Bridesmaids, Rushmore, Office Space")
]
TOP_SHOWS = [
    ("⭐ Highest Rated Series", "Breaking Bad, Band of Brothers, Chernobyl, The Wire, Game of Thrones, The Sopranos, Succession, The Queen's Gambit, Fleabag, The Mandalorian"),
    ("🚀 Sci-Fi / Fantasy", "The Mandalorian, The Expanse, Severance, Stranger Things, Game of Thrones, Watchmen, Westworld, Doctor Who, Black Mirror, Firefly"),
    ("😂 Sitcoms", "Parks and Recreation, The Office, Seinfeld, Friends, Arrested Development, Community, It's Always Sunny in Philadelphia, 30 Rock, Curb Your Enthusiasm, Father Ted")
]


# =================================================================================
# SETTINGS PANEL (NEW IN-WINDOW WIDGET)
# =================================================================================

def _get_display_key(key_content: str) -> str:
    """Returns a status string if the key is empty, or the key itself."""
    return "[Key Missing or Empty]" if key_content == "" else key_content

class SettingsPanel(QFrame):
    """A floating panel for viewing and updating API keys and general settings."""
    keys_saved = Signal()
    closed = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(550, 600) # Increased size to accommodate new controls
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0) 
        
        # FIX 1: Updated stylesheet to ensure QLabel backgrounds match the panel's background
        # Updated Stylesheet in __init__
        self.setStyleSheet("""
            SettingsPanel {
                background-color: #1E1E1E; /* Panel Background */
                border-radius: 20px;
                border: 2px solid #1E1E1E;
            }
            QLabel { 
                font-weight: bold; 
                background-color: #1E1E1E; 
            } 
            QLineEdit {
                background-color: #333333; /* <-- NEW: Lighter gray for distinction */
                border: 1px solid #4A4A4A; /* <-- NEW: Subtle border */
                border-radius: 8px;
                padding: 10px;
                color: #E0E0E0;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Settings")
        title_label.setFont(QFont('Segoe UI', 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Scroll area for the content (useful since we added many controls)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        # 💡 FIX: Explicitly set the background of the content container
        content_widget.setStyleSheet("background-color: #1E1E1E;") 
        scroll_area.setWidget(content_widget)

        form_layout = QFormLayout(content_widget)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form_layout.setHorizontalSpacing(15)
        form_layout.setVerticalSpacing(15)
        
        # --- API Key Inputs ---
        
        # Gemini Key Input
        self.gemini_input = QLineEdit()
        form_layout.addRow(QLabel("Gemini Key:"), self.gemini_input)

        # OMDb Key Input
        self.omdb_input = QLineEdit()
        form_layout.addRow(QLabel("OMDb Key:"), self.omdb_input)

        form_layout.addRow(QLabel(""), QLabel("<hr style='border: 1px solid #444444;'>")) # Separator
        
        # --- Suggestion Count Input (New) ---
        
        self.count_input = QSpinBox()
        self.count_input.setRange(1, 20)
        self.count_input.setValue(GLOBAL_SUGGESTION_COUNT)
        form_layout.addRow(QLabel("Max Suggestions (1-20):"), self.count_input)

        form_layout.addRow(QLabel(""), QLabel("<hr style='border: 1px solid #444444;'>")) # Separator

        # --- Color Pickers (New) ---
        
        # Store references to the QLineEdits holding the hex codes
        self.movie_color_line = self._create_color_picker("Movie Button Color (Blue):", GLOBAL_MOVIE_COLOR, form_layout)
        self.show_color_line = self._create_color_picker("Show Button Color (Orange):", GLOBAL_SHOW_COLOR, form_layout)
        self.neon_pink_line = self._create_color_picker("Neon Border Color 1 (Pink):", GLOBAL_NEON_PINK, form_layout)
        self.neon_blue_line = self._create_color_picker("Neon Border Color 2 (Blue):", GLOBAL_NEON_BLUE, form_layout)
        
        main_layout.addWidget(scroll_area)
        
        # Status Label 
        status_label = QLabel(f"Settings are saved/read from: <b>{os.path.basename(GLOBAL_CWD) or 'N/A'}</b>")
        status_label.setWordWrap(True)
        status_label.setStyleSheet("color: #AAAAAA; font-size: 10px; font-weight: normal; background-color: #2E2E2E;")
        status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(status_label)
        
        # Buttons Layout
        button_layout = QHBoxLayout()
        
        # Cancel Button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close_panel)
        cancel_button.setStyleSheet("""
            QPushButton { background-color: #4A4A4A; border-radius: 12px; padding: 10px; border: none;}
            QPushButton:hover { background-color: #5A5A5A; }
        """)
        
        # Save Button
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_keys)
        save_button.setStyleSheet("""
            QPushButton { background-color: #1E90FF; border-radius: 12px; padding: 10px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #0066CC; }
        """)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        
        main_layout.addLayout(button_layout)


    def _create_color_picker(self, label_text: str, default_hex: str, form_layout: QFormLayout) -> QLineEdit:
        """Helper to create a color picker row for the QFormLayout."""
        color_line = QLineEdit(default_hex)
        color_line.setFixedWidth(80)
        
        # Function to style the QLineEdit to show the color
        def style_line_edit(hex_code):
             color_line.setStyleSheet(f"""
                QLineEdit {{ 
                    background-color: {hex_code}; 
                    border: 1px solid #444444;
                    border-radius: 8px;
                    padding: 8px;
                    color: #E0E0E0;
                    text-align: center;
                }}
            """)
        style_line_edit(default_hex)
        
        # Connect the style function to text changes (manual hex entry)
        color_line.textChanged.connect(style_line_edit)

        # Color Dialog Button
        picker_button = QPushButton("Pick")
        picker_button.setFixedSize(60, 30)
        
        # Lambda function to open the dialog and update the line edit
        def open_dialog():
            current_color = QColor(color_line.text())
            # Ensure QColorDialog is imported
            color = QColorDialog.getColor(current_color, self, "Select Color")
            if color.isValid():
                new_hex = color.name().upper()
                color_line.setText(new_hex)
        
        picker_button.clicked.connect(open_dialog)

        # Container for the input and button
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        row_layout.addWidget(color_line)
        row_layout.addWidget(picker_button)
        row_layout.addStretch(1) 
        
        # Add to form layout
        form_layout.addRow(QLabel(label_text), row_widget)

        return color_line


    @Slot()
    def close_panel(self):
        """Starts the fade-out animation and emits the closed signal on completion."""
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out.setDuration(200)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)
        fade_out.finished.connect(self.closed.emit) 
        fade_out.start()
        self._fade_out_anim = fade_out


    @Slot()
    def save_keys(self):
        try:
            # 1. Save API Keys
            _save_key_content(GEMINI_KEY_FILE, self.gemini_input.text())
            _save_key_content(OMDB_KEY_FILE, self.omdb_input.text())

            # >>> FIX: Reload the key content into the global variables immediately after saving the files.
            _setup_cwd_and_load_keys(first_load=False)
            # <<< END FIX

            # 2. Collect and Save Configuration (Count & Colors)
            new_config = {
                'suggestion_count': self.count_input.value(),
                'movie_color': self.movie_color_line.text(),
                'show_color': self.show_color_line.text(),
                'neon_pink': self.neon_pink_line.text(),
                'neon_blue': self.neon_blue_line.text(),
            }
            
            _save_config(new_config) # This will also update the global configuration variables

            QMessageBox.information(self, "Success", "Settings saved and reloaded successfully.")
            self.keys_saved.emit()
            self.close_panel()
            
        except RuntimeError as e:
            QMessageBox.critical(self, "Save Error", str(e))


# =================================================================================
# (Rest of the original classes/functions)
# =================================================================================


# Clickable Label (Unchanged)
class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked, carrying an associated IMDb ID."""
    clicked = Signal(str)

    def __init__(self, imdb_id: str, parent=None):
        super().__init__(parent)
        self.imdb_id = imdb_id
        self.setCursor(Qt.PointingHandCursor) 

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.imdb_id)
        super().mousePressEvent(event) 

# Network worker (Unchanged)
class NetworkWorker(QWidget):
    finished = Signal(list) 
    error = Signal(str)

    def __init__(self, query_text: str, search_type: str, pre_defined_titles: list = None, excluded_ids: list = None):
        super().__init__()
        self.query_text = query_text
        self.search_type = search_type
        self.pre_defined_titles = pre_defined_titles
        self.excluded_ids = excluded_ids or []

    def run(self):
        try:
            titles = []
            if self.pre_defined_titles:
                titles = self.pre_defined_titles
            else:
                titles = generate_recommendations(self.query_text, self.search_type, self.excluded_ids)
                
            results = []
            
            for t in titles:
                info = fetch_imdb_info(t)
                if info and info.get('imdb_id') and info.get('imdb_id') not in self.excluded_ids:
                    results.append(info)
                    
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

# Gemini API call (Unchanged)
def direct_gemini_api_call(prompt_text: str, encoded_image: str = None, max_tokens: int = 2000):
    if GEMINI_API_KEY is MISSING_API_KEY:
        raise RuntimeError("Gemini API Key is not configured. Cannot make API call.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/{'models/gemini-2.5-flash'}:generateContent?key={GEMINI_API_KEY}"

    content_parts = [{"text": prompt_text}]
    
    if encoded_image:
        import base64
        content_parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": encoded_image
            }
        })

    payload = {
        "contents": [
            {
                "parts": content_parts
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2
        }
    }

    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    try:
        return data['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        return json.dumps(data)

# Recommendation logic (Updated to use GLOBAL_SUGGESTION_COUNT)
def generate_recommendations(query_text: str, search_type: str, excluded_ids: list = None):
    if GEMINI_API_KEY is MISSING_API_KEY:
        raise RuntimeError("Gemini API Key is missing. Cannot generate recommendations.")
        
    excluded_list = ", ".join(excluded_ids) if excluded_ids else "None"
    count = GLOBAL_SUGGESTION_COUNT # Use the global setting

    prompt = textwrap.dedent(f"""
    You are a helpful assistant that suggests {search_type}s.
    Only suggest {search_type}s (do not suggest the other type).

    User tastes: {query_text}
    
    IMPORTANT: DO NOT suggest any titles with the following IMDb IDs: {excluded_list}.

    Provide a short ordered list of {count} titles only (one per line).
    """)
    try:
        raw = direct_gemini_api_call(prompt)
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        titles = []
        
        for l in lines:
            temp_l = l.strip()
            # Handle list markers 1. to 10.
            for sep in [f"{i}." for i in range(1, count + 1)] + ['-', '•', '*']:
                if temp_l.startswith(sep): 
                    l = l[len(sep):].strip() 
                    break 
            
            cleaned_title = l.strip().replace('\xa0', ' ').strip()
            
            if cleaned_title:
                titles.append(cleaned_title)
                if len(titles) >= count: # Use the global count here
                    break
                    
        if not titles:
            raise RuntimeError('No titles parsed from Gemini response.')
        return titles
    except Exception as e:
        raise e 


# IMDb info fetch (Unchanged)
def fetch_imdb_info(title: str):
    if OMDB_API_KEY is MISSING_API_KEY:
        return {
            'title': title,
            'year': 'N/A',
            'kind': 'N/A',
            'rating': 'N/A',
            'genres': ['API Key Missing'],
            'plot': 'OMDB API Key is missing, unable to fetch movie metadata.',
            'directors': ['N/A'],
            'cover_url': None,
            'imdb_id': title.replace(' ', ''), 
        }
        
    try:
        url = f"http://www.omdbapi.com/?t={title}&apikey={OMDB_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('Response') == 'False':
            return None

        info = {
            'title': data.get('Title'),
            'year': data.get('Year'),
            'kind': data.get('Type'),
            'rating': data.get('imdbRating'),
            'genres': data.get('Genre', '').split(', '),
            'plot': data.get('Plot'),
            'directors': data.get('Director', '').split(', '),
            'cover_url': data.get('Poster') if data.get('Poster') != 'N/A' else None,
            'imdb_id': data.get('imdbID'), 
        }
        return info
        
    except Exception as e:
        return None
        
# PULSING BUTTON (Updated to use global colors)
class SizePulsingSelectorButton(QPushButton):
    toggled = Signal(bool) 
    
    BASE_WIDTH = 160
    BASE_HEIGHT = 36
    PULSE_WIDTH_INCREASE = 10 

    def __init__(self, initial=False):
        super().__init__()
        self.setMinimumSize(self.BASE_WIDTH, self.BASE_HEIGHT)
        self.setMaximumSize(self.BASE_WIDTH, self.BASE_HEIGHT)
        
        self.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        self.setCursor(Qt.PointingHandCursor)
        
        self._is_show = initial
        self.clicked.connect(self._toggle_mode)
        
        self.pulse_anim = QPropertyAnimation(self, b"maximumWidth")
        self.pulse_anim.setDuration(300) 
        self.pulse_anim.setLoopCount(2) 
        self.pulse_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._update_ui(initial, animate=False)


    def _update_ui(self, is_show: bool, animate: bool = True):
        self._is_show = is_show
        
        # Updated to use global colors
        base_color = GLOBAL_SHOW_COLOR if is_show else GLOBAL_MOVIE_COLOR
        text = "Shows Mode" if is_show else "Movies Mode"
        
        self.setText(text)
        
        self.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {base_color}; 
                color: white; 
                border-radius: 18px;
                border: none;
            }}
        """)
        
        if animate:
            self._start_pulse()

    def _start_pulse(self):
        start_width = self.BASE_WIDTH
        peak_width = self.BASE_WIDTH + self.PULSE_WIDTH_INCREASE
        
        self.pulse_anim.stop() 
        
        self.pulse_anim.setStartValue(start_width)
        self.pulse_anim.setKeyValueAt(0.25, peak_width) 
        self.pulse_anim.setKeyValueAt(0.50, start_width) 
        self.pulse_anim.setKeyValueAt(0.75, peak_width)
        self.pulse_anim.setEndValue(start_width)
        
        self.setMaximumWidth(peak_width)
        self.pulse_anim.finished.connect(lambda: self.setMaximumWidth(self.BASE_WIDTH), Qt.SingleShotConnection)
        
        self.pulse_anim.start()

    @Slot()
    def _toggle_mode(self):
        new_mode = not self._is_show
        self._update_ui(new_mode, animate=True)
        self.toggled.emit(new_mode)


class PulseWrapper(QFrame):
    def __init__(self):
        super().__init__()
        
        self.selector_button = SizePulsingSelectorButton(initial=False)
        
        max_width = self.selector_button.BASE_WIDTH + self.selector_button.PULSE_WIDTH_INCREASE
        max_height = self.selector_button.BASE_HEIGHT
        self.setFixedSize(max_width, max_height)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.selector_button)
        
# WRAPPER CLASS FOR ROTATING BORDER EFFECT (Updated to use global colors)
class NeonSearchWrapper(QFrame):
    
    _rotation_angle = Property(int, 
                               lambda self: self._current_angle, 
                               lambda self, angle: self._set_rotation_angle(angle))
    
    _color_factor = Property(float, 
                             lambda self: self._current_color_factor, 
                             lambda self, factor: self._set_color_factor(factor))
    
    # Define resting color locally (not configurable)
    COLOR_REST = QColor("#555555") 
    BORDER_THICKNESS = 4 

    def __init__(self, search_input: QLineEdit):
        super().__init__()
        self.search_input = search_input
        
        self.setFixedSize(search_input.width() + self.BORDER_THICKNESS, 
                          search_input.height() + self.BORDER_THICKNESS)
        
        self._current_angle = 0
        self._current_color_factor = 0.0 
        self.is_hovering = False
        
        self.wrapper_layout = QHBoxLayout(self)
        margin = self.BORDER_THICKNESS // 2
        self.wrapper_layout.setContentsMargins(margin, margin, margin, margin) 
        self.wrapper_layout.setSpacing(0)
        self.wrapper_layout.addWidget(search_input)
        
        self.rotation_animation = QPropertyAnimation(self, b"_rotation_angle")
        self.rotation_animation.setDuration(3000) 
        self.rotation_animation.setStartValue(0)
        self.rotation_animation.setEndValue(360) 
        self.rotation_animation.setLoopCount(-1) 
        self.rotation_animation.setEasingCurve(QEasingCurve.Type.Linear)
        
        self.fade_animation = QPropertyAnimation(self, b"_color_factor")
        self.fade_animation.setDuration(250)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._apply_resting_style()
        
        self.search_input.installEventFilter(self)

    @staticmethod
    def _blend_color(c1: QColor, c2: QColor, factor: float) -> str:
        """Manually blends two QColors based on a float factor (0.0 to 1.0)."""
        r = int(c1.red() * factor + c2.red() * (1 - factor))
        g = int(c1.green() * factor + c2.green() * (1 - factor))
        b = int(c1.blue() * factor + c2.blue() * (1 - factor))
        return QColor(r, g, b, 255).name()

    def _set_color_factor(self, factor: float):
        """Setter for the _color_factor property, recalculates the gradient with blended colors."""
        self._current_color_factor = factor
        
        # Get the globally configured colors
        color_pink = QColor(GLOBAL_NEON_PINK) 
        color_blue = QColor(GLOBAL_NEON_BLUE)
        
        factor_clamped = max(0.0, min(1.0, factor))
        blended_pink = self._blend_color(color_pink, self.COLOR_REST, factor_clamped)
        blended_blue = self._blend_color(color_blue, self.COLOR_REST, factor_clamped)

        style = f"""
            NeonSearchWrapper {{
                background: qconicalgradient(
                    cx:0.5, cy:0.5, angle:{self._current_angle}, 
                    stop:0.0 {blended_pink}, 
                    stop:0.49 {blended_pink}, 
                    stop:0.50 {blended_blue}, 
                    stop:0.99 {blended_blue},
                    stop:1.0 {blended_pink}
                );
                border-radius: 16px; 
            }}
            QLineEdit {{
                background: #2E2E2E; 
                border-radius: 14px; 
                border: none;
                padding: 12px; 
                font-size: 16px; 
                color: #FFF;
            }}
        """
        self.setStyleSheet(style)
        
        if not self.is_hovering and factor < 0.05:
            self._apply_resting_style()


    def _set_rotation_angle(self, angle: int):
        """Setter for the _rotation_angle property."""
        self._current_angle = angle
        self._set_color_factor(self._current_color_factor)

    def _apply_resting_style(self):
        """Applies the default, non-rotating style."""
        self.rotation_animation.stop() 
        
        self.setStyleSheet(f"""
            NeonSearchWrapper {{
                background: qconicalgradient(
                    cx:0.5, cy:0.5, angle:0, 
                    stop:0.0 {self.COLOR_REST.name()}, 
                    stop:1.0 {self.COLOR_REST.name()}
                );
                border-radius: 16px;
            }}
            QLineEdit {{
                background: #2E2E2E; 
                border-radius: 14px; 
                border: none;
                padding: 12px; 
                font-size: 16px; 
                color: #FFF;
            }}
        """)

    def eventFilter(self, watched, event):
        if watched == self.search_input:
            if event.type() == event.Type.Enter and not self.is_hovering:
                self.is_hovering = True
                self.on_wrapper_enter()
            elif event.type() == event.Type.Leave and self.is_hovering:
                self.is_hovering = False
                self.on_wrapper_leave()
        return super().eventFilter(watched, event)


    def on_wrapper_enter(self):
        """Starts the rotation and fades the neon brightness in."""
        # Re-set colors on enter to pick up new global settings
        self._set_rotation_angle(self._current_angle)
        self.rotation_animation.start()
        
        self.fade_animation.stop()
        self.fade_animation.setStartValue(self._current_color_factor)
        self.fade_animation.setEndValue(1.0) 
        self.fade_animation.finished.disconnect()
        self.fade_animation.start()

    def on_wrapper_leave(self):
        """Fades the neon brightness out."""
        
        self.fade_animation.stop()
        self.fade_animation.setStartValue(self._current_color_factor)
        self.fade_animation.setEndValue(0.0) 
        self.fade_animation.finished.connect(self._apply_resting_style, Qt.SingleShotConnection) 
        self.fade_animation.start()
        
        
# Main Window 
class MainWindow(QWidget):
    INITIAL_TITLE_HEIGHT = 130 
    
    # ... indices remain the same ...
    TOP_SPACER_INDEX = 1
    TITLE_FRAME_INDEX = 2
    SEARCH_ROW_INDEX = 3
    QUICK_FILTER_INDEX = 4
    BOTTOM_SPACER_INDEX = 5
    RESULTS_HEADER_INDEX = 6 
    RESULTS_AREA_INDEX = 7 
    STATUS_INDEX = 8 


    def __init__(self):
        super().__init__()
        self.setWindowTitle('Gemini Movie/Show Recommender')
        self.resize(1100, 700) 
        
        self.setStyleSheet(f"""
        QWidget{{ background-color: #1E1E1E; color: #E0E0E0; }}
        
        QScrollArea {{ border: none; }}
        QScrollArea > QWidget {{ border: none; background-color: #1E1E1E; }}
        
        QLabel#subtitle {{ color: #AAAAAA }}
        QPushButton {{ 
            background: #2E2E2E; 
            border-radius: 10px; 
            padding: 8px 15px; 
            color: #FFF; 
            border: 1px solid #444444; 
        }}
        QPushButton:hover {{ background: #3A3A3A; }}
        QPushButton#quick_filter {{
            background: #3A3A3A;
            border-radius: 8px;
            padding: 6px 14px; 
            font-size: 14px;
            border: none;
        }}
        QPushButton#quick_filter:hover {{ background: #4A4A4A; }}
        .card {{ background: #2E2E2E; border-radius: 12px; padding: 12px; border: none; }}
        """)
        
        self.api_keys_ok = True
        self._init_layout()
        
        self.search_active = False 
        self.last_query = ""
        self.last_search_type = "movie"
        self.excluded_ids = [] 

        self.settings_overlay = QFrame(self)
        self.settings_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);") 
        self.settings_overlay.setLayout(QVBoxLayout()) 
        self.settings_overlay.layout().setAlignment(Qt.AlignCenter)
        
        self.settings_panel = SettingsPanel(self.settings_overlay) 
        self.settings_panel.keys_saved.connect(self._handle_keys_updated)
        self.settings_panel.closed.connect(self._hide_settings_overlay) 
        
        self.settings_overlay.layout().addWidget(self.settings_panel)
        self.settings_overlay.setVisible(False) 

        self._check_api_keys()


    # Overridden method to ensure the overlay covers the window on resize
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.settings_overlay.setGeometry(self.rect())


    @Slot()
    def open_settings(self):
        """Opens the API Key Settings as an in-window modal overlay."""
        # 1. Update the input fields and config controls with current global values before showing
        self.settings_panel.gemini_input.setText(GLOBAL_GEMINI_API_KEY_CONTENT)
        self.settings_panel.omdb_input.setText(GLOBAL_OMDB_API_KEY_CONTENT)
        self.settings_panel.gemini_input.setPlaceholderText(_get_display_key(GLOBAL_GEMINI_API_KEY_CONTENT))
        self.settings_panel.omdb_input.setPlaceholderText(_get_display_key(GLOBAL_OMDB_API_KEY_CONTENT))
        
        # New: Update config controls
        self.settings_panel.count_input.setValue(GLOBAL_SUGGESTION_COUNT)
        self.settings_panel.movie_color_line.setText(GLOBAL_MOVIE_COLOR)
        self.settings_panel.show_color_line.setText(GLOBAL_SHOW_COLOR)
        self.settings_panel.neon_pink_line.setText(GLOBAL_NEON_PINK)
        self.settings_panel.neon_blue_line.setText(GLOBAL_NEON_BLUE)
        
        # 2. Show the overlay
        self.settings_overlay.setGeometry(self.rect())
        self.settings_overlay.setVisible(True)
        self.settings_overlay.raise_() 
        
        # 3. Animate the panel in
        fade_in = QPropertyAnimation(self.settings_panel.opacity_effect, b"opacity") 
        fade_in.setDuration(200)
        fade_in.setStartValue(self.settings_panel.opacity_effect.opacity())
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InQuad)
        fade_in.start()
        self.settings_panel._fade_in_anim = fade_in 

        # 4. Ensure the overlay and its content are enabled for input:
        self.settings_overlay.setEnabled(True) 
        self.settings_panel.setEnabled(True) 
        
        # 5. Set focus to the first input
        self.settings_panel.gemini_input.setFocus()


    @Slot()
    def _hide_settings_overlay(self):
        """Hides the settings overlay and re-enables the main window."""
        self.settings_overlay.setVisible(False)
        self.setEnabled(True) 
        
        # Re-initialize UI elements that depend on global colors/config
        self.selector_button._update_ui(self.selector_button._is_show, animate=False)
        self.search_wrapper._apply_resting_style()
        
        self._check_api_keys(show_message_box=False)


    @Slot()
    def _handle_keys_updated(self):
        """Called after keys are saved in the dialog to update status."""
        pass

    def _check_api_keys(self, show_message_box: bool = True):
        """Checks the current status of the global API keys."""
        missing = []
        if GEMINI_API_KEY is MISSING_API_KEY:
            missing.append("Gemini (AI Recommendations)")
        if OMDB_API_KEY is MISSING_API_KEY:
            missing.append("OMDB (Movie Metadata/Posters)")
            
        self.api_keys_ok = not missing
            
        if missing:
            missing_str = "\n- " + "\n- ".join(missing)
            
            error_message = f"🚨 API KEY SETUP REQUIRED 🚨\n\n**The following API keys were not found or are empty in the script's directory:**\n{missing_str}\n\nPlease click the 'Settings' button to enter them or create the necessary text files."
            
            if show_message_box:
                msg = QMessageBox()
                msg.setWindowTitle("API KEY Setup Required")
                msg.setText(error_message)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()
            
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            self.status.setStyleSheet("background-color: #550000; color: white; border-radius: 0px;")
            
            self.selector_button.setEnabled(False)
            self.search_input.setEnabled(False)
            self.update_quick_filters(self.selector_button._is_show) 
        else:
            self.status.setText(f'Ready ({"Shows" if self.selector_button._is_show else "Movies"} Mode)')
            self.status.setStyleSheet("background-color: rgba(0, 0, 0, 0); color: #AAAAAA;")
            self.selector_button.setEnabled(True)
            self.search_input.setEnabled(True)
            self.update_quick_filters(self.selector_button._is_show)
            

    def _init_layout(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(40, 40, 40, 40)
        main.setSpacing(20)

        # 0. TOP BAR LAYOUT
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(0)

        self.back_button = QPushButton("← Back to Search")
        self.back_button.setFixedWidth(150)
        self.back_button.clicked.connect(self.animate_search_down)
        self.back_button.setVisible(False) 
        top_bar_layout.addWidget(self.back_button)
        
        top_bar_layout.addStretch(1) 

        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.setFixedSize(90, 30)
        self.settings_button.clicked.connect(self.open_settings)
        self.settings_button.setStyleSheet("""
            QPushButton { 
                background: #2E2E2E; 
                border-radius: 15px; 
                padding: 5px; 
                color: #E0E0E0; 
                font-size: 13px;
                border: 1px solid #444444; 
            }
            QPushButton:hover { background: #3A3A3A; }
        """)
        top_bar_layout.addWidget(self.settings_button)

        main.addLayout(top_bar_layout)


        # 1. Top Spacer 
        self.top_spacer_item = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main.addItem(self.top_spacer_item)
        main.setStretch(self.TOP_SPACER_INDEX, 1) 

        
        # 2. Title Frame
        self.title_frame = QFrame()
        self.title_frame.setMaximumHeight(self.INITIAL_TITLE_HEIGHT)
        title_layout = QVBoxLayout(self.title_frame)
        title_layout.setAlignment(Qt.AlignCenter)
        title_layout.setSpacing(10)

        title = QLabel('What would you like to watch?')
        title.setFont(QFont('Segoe UI', 20))
        title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title)

        subtitle = QLabel('Tell me genres, moods or shows you like and I\'ll give you some suggestions!')
        subtitle.setObjectName('subtitle')
        subtitle.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(subtitle)
        
        main.addWidget(self.title_frame)

        # 3. Search Bar and Selector Row
        search_row_layout = QHBoxLayout()
        search_row_layout.setAlignment(Qt.AlignCenter)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('e.g. gritty sci-fi with moral complexity')
        self.search_input.setFixedSize(560, 48) 
        self.search_input.returnPressed.connect(self.on_search)
        
        self.search_wrapper = NeonSearchWrapper(self.search_input) 

        self.selector_wrapper = PulseWrapper()
        self.selector_button = self.selector_wrapper.selector_button
        self.selector_button.toggled.connect(self.on_toggle)

        search_row_layout.addWidget(self.search_wrapper) 
        search_row_layout.addSpacing(12)
        search_row_layout.addWidget(self.selector_wrapper) 
        
        main.addLayout(search_row_layout)
        
        # 4. Quick Filter Section
        self.quick_filter_frame = QFrame()
        self.quick_filter_layout = QHBoxLayout(self.quick_filter_frame)
        self.quick_filter_layout.setAlignment(Qt.AlignCenter)
        self.quick_filter_layout.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self.quick_filter_frame)

        self.update_quick_filters(self.selector_button._is_show)

        # 5. Bottom Spacer
        main.addStretch(1) 

        # 6. Results Header Row 
        results_header_layout = QHBoxLayout()
        results_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_title = QLabel('Recommendations')
        self.results_title.setFont(QFont('Segoe UI', 14, QFont.Weight.Bold))
        self.results_title.setVisible(False)
        results_header_layout.addWidget(self.results_title)
        results_header_layout.addStretch(1) 

        self.more_button = QPushButton("Generate More Picks") 
        self.more_button.clicked.connect(self.on_generate_more)
        self.more_button.setFixedSize(220, 30) 
        self.more_button.setVisible(False)
        self.more_button.setStyleSheet("""
            QPushButton { 
                background: #4A4A4A; 
                border-radius: 8px; 
                padding: 4px 10px; 
                font-size: 13px; 
                border: none;
            }
            QPushButton:hover { background: #5A5A5A; }
        """)
        results_header_layout.addWidget(self.more_button)
        main.addLayout(results_header_layout) 

        # 7. Results area
        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_container.setStyleSheet('background-color: #1E1E1E;')
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_area.setWidget(self.results_container)
        main.addWidget(self.results_area) 
        main.setStretch(self.RESULTS_AREA_INDEX, 0) 

        # 8. Status 
        self.status = QLabel('Ready (Movies Mode)')
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setMaximumHeight(30) 
        self.status.setStyleSheet("background-color: rgba(0, 0, 0, 0); border: 0px solid transparent; color: #AAAAAA;") 
        main.addWidget(self.status)
        
    def _clear_results_cards(self):
        """Removes all widget cards currently in the results layout."""
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    @Slot(str)
    def open_imdb_link(self, imdb_id: str):
        """Opens the IMDb link in the default browser."""
        if imdb_id and OMDB_API_KEY is not MISSING_API_KEY:
            url = f"https://www.imdb.com/title/{imdb_id}/"
            QDesktopServices.openUrl(QUrl(url))
            self.status.setText(f"Opened IMDb link for {imdb_id}")
        elif OMDB_API_KEY is MISSING_API_KEY:
            self.status.setText("🚫 ERROR: OMDb API Key is missing. Cannot open external links.")
            
    def update_quick_filters(self, is_show: bool):
        for i in reversed(range(self.quick_filter_layout.count())):
            w = self.quick_filter_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                
        filters = TOP_SHOWS if is_show else TOP_MOVIES
        search_type = 'TV show' if is_show else 'movie'
        
        for label, query_string in filters:
            btn = QPushButton(label) 
            btn.setObjectName('quick_filter')
            
            titles_list = [t.strip() for t in query_string.split(',')]
            btn.clicked.connect(partial(self.on_filter_search, titles_list, search_type))
            btn.setEnabled(self.api_keys_ok) 
            self.quick_filter_layout.addWidget(btn)

    @Slot(bool)
    def on_toggle(self, is_show: bool):
        if not self.api_keys_ok:
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            return
            
        self.status.setText(f'Selected: {"Shows" if is_show else "Movies"}')
        self.update_quick_filters(is_show)

    @Slot(list, str)
    def on_filter_search(self, pre_defined_titles: list, search_type: str):
        if not self.api_keys_ok:
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            return
            
        query_text = f"Pre-defined {len(pre_defined_titles)} {search_type}s" 
        self.start_search(query_text, search_type, pre_defined_titles=pre_defined_titles, is_filter=True)
        
    @Slot()
    def on_search(self):
        if not self.api_keys_ok:
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            return
            
        text = self.search_input.text().strip()
        search_type = 'TV show' if self.selector_button._is_show else 'movie'
        self.start_search(text, search_type)
        
    @Slot()
    def on_generate_more(self):
        if not self.api_keys_ok:
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            return
            
        self.status.setText(f'Generating {GLOBAL_SUGGESTION_COUNT} more recommendations, excluding current results...')
        self.more_button.setVisible(False)
        
        self.results_area.verticalScrollBar().setValue(0) 
        self._clear_results_cards()
        
        worker = NetworkWorker(self.last_query, self.last_search_type, excluded_ids=self.excluded_ids)
        worker.finished.connect(self.on_results_ready)
        worker.error.connect(self.on_network_error)
        threading.Thread(target=worker.run, daemon=True).start()
        

    def start_search(self, text: str, search_type: str, pre_defined_titles: list = None, is_filter: bool = False):
        if not self.api_keys_ok:
            self.status.setText("🚫 ERROR: API KEYS HAVE NOT BEEN SETUP. Functionality is disabled. 🚫")
            return

        if not text and not pre_defined_titles:
            self.status.setText('Please type something or select a filter.')
            return
        
        self.search_input.clear()
        
        display_text = "quick filter" if is_filter else "text input"
        action_type = "loading pre-defined titles" if is_filter else "contacting AI"
        self.status.setText(f'Search initiated ({display_text}): {action_type} for {search_type} recommendations...')
        
        self.quick_filter_frame.setVisible(False) 
        
        self.animate_search_up()
        self.search_active = True
        self.back_button.setVisible(True)
        
        self.last_query = text
        self.last_search_type = search_type
        self.excluded_ids = []
        self.more_button.setVisible(False)
        self.results_title.setVisible(True)
        self.results_title.setText(f'Recommendations ({GLOBAL_SUGGESTION_COUNT} Picks)')
        
        main_layout = self.layout()
        main_layout.setStretch(self.TOP_SPACER_INDEX, 0)
        main_layout.setStretch(self.BOTTOM_SPACER_INDEX, 0)
        main_layout.setStretch(self.RESULTS_AREA_INDEX, 1) 
        

        self._clear_results_cards()

        worker = NetworkWorker(text, search_type, pre_defined_titles=pre_defined_titles, excluded_ids=self.excluded_ids) 
        worker.finished.connect(self.on_results_ready)
        worker.error.connect(self.on_network_error)
        threading.Thread(target=worker.run, daemon=True).start()

    @Slot(list)
    def on_results_ready(self, results):
        if not results:
            if not self.excluded_ids:
                 self.status.setText('No results found for that query. Try a different query.')
            else:
                 self.status.setText('No more unique results found for that query.')
            self.more_button.setVisible(False) 
            return
        
        self.status.setText(f'Showing {len(results)} new results (Total loaded: {len(self.excluded_ids) + len(results)})')
        
        for i, info in enumerate(results):
            if info.get('imdb_id'):
                self.excluded_ids.append(info['imdb_id'])
                
            card = self.make_result_card(info)
            self.results_layout.addWidget(card)
            QTimer.singleShot(i * 100, partial(self.animate_card, card))

        self.more_button.setVisible(True)

    @Slot(str)
    def on_network_error(self, msg):
        self.status.setText(f'Error: {msg}')
        self.more_button.setVisible(False) 
        self.results_title.setVisible(False)

    def animate_search_up(self):
        anim = QPropertyAnimation(self.title_frame, b"maximumHeight")
        anim.setDuration(500)
        anim.setStartValue(self.title_frame.maximumHeight())
        anim.setEndValue(0) 
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim
        
    @Slot()
    def animate_search_down(self):
        self._clear_results_cards()
                
        self.back_button.setVisible(False)
        self.search_active = False
        self.more_button.setVisible(False) 
        self.results_title.setVisible(False) 
        
        self._check_api_keys(show_message_box=False)

        main_layout = self.layout()
        main_layout.setStretch(self.TOP_SPACER_INDEX, 1)
        main_layout.setStretch(self.BOTTOM_SPACER_INDEX, 1)
        main_layout.setStretch(self.RESULTS_AREA_INDEX, 0) 
        
        self.quick_filter_frame.setVisible(True)
        
        anim = QPropertyAnimation(self.title_frame, b"maximumHeight")
        anim.setDuration(500)
        anim.setStartValue(self.title_frame.maximumHeight())
        anim.setEndValue(self.INITIAL_TITLE_HEIGHT) 
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def animate_card(self, card: QFrame):
        opacity_effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(opacity_effect) 
        
        opacity_effect.setOpacity(0.0) 
        card.setMaximumHeight(0) 
        
        height_anim = QPropertyAnimation(card, b"maximumHeight")
        height_anim.setDuration(300)
        height_anim.setStartValue(0)
        height_anim.setEndValue(200) 
        height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        height_anim.start()
        
        opacity_anim = QPropertyAnimation(opacity_effect, b"opacity") 
        opacity_anim.setDuration(300)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InQuad)
        
        opacity_anim.finished.connect(lambda: card.setGraphicsEffect(None))
        opacity_anim.start()
        
        card._height_anim = height_anim 
        card._opacity_anim = opacity_anim 

    def make_result_card(self, info: dict):
        card = QFrame()
        card.setProperty('class', 'card')
        card.setMaximumHeight(200) 
        layout = QHBoxLayout(card)
        layout.setSpacing(12)

        poster_label = ClickableLabel(info.get('imdb_id', '')) 
        poster_label.clicked.connect(self.open_imdb_link) 
        
        poster_label.setFixedSize(120, 170)
        poster_label.setStyleSheet('background: #3E3E3E; border-radius: 8px')
        
        if info.get('cover_url') and OMDB_API_KEY is not MISSING_API_KEY:
            try:
                r = requests.get(info['cover_url'], timeout=8)
                r.raise_for_status()
                img = Image.open(BytesIO(r.content))
                img = img.resize((120, 170))
                bio = BytesIO()
                img.save(bio, format='PNG')
                pix = QPixmap()
                pix.loadFromData(bio.getvalue())
                poster_label.setPixmap(pix)
            except Exception:
                pass
        layout.addWidget(poster_label)

        meta = QVBoxLayout()
        
        title = QLabel(f"**{info.get('title')}** ({info.get('year')})")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        meta.addWidget(title)
        
        sub = QLabel(', '.join(info.get('genres') or []))
        sub.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sub.setStyleSheet('color: #AAAAAA;') 
        meta.addWidget(sub)
        
        rating = QLabel(f"IMDb: **{info.get('rating') or 'N/A'}**")
        rating.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta.addWidget(rating)
        
        plot = QLabel(info.get('plot') or '')
        plot.setTextInteractionFlags(Qt.TextSelectableByMouse) 
        plot.setWordWrap(True)
        plot.setFixedHeight(60)
        meta.addWidget(plot)
        
        layout.addLayout(meta)

        return card

# Run App
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()