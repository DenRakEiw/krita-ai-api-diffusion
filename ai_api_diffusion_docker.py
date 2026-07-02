import json
import base64
import requests
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QPlainTextEdit, 
    QScrollArea, QGroupBox
)
from krita import DockWidget, Krita

class APIWorker(QThread):
    """Worker-Thread für API-Aufrufe, um die UI nicht zu blockieren."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_type, prompt, api_key, model_type, image_data=None):
        super().__init__()
        self.api_type = api_type
        self.prompt = prompt
        self.api_key = api_key
        self.model_type = model_type
        self.image_data = image_data

    def run(self):
        try:
            # Platzhalter für die tatsächliche API-Logik (BFL Flux / Google Banana)
            # Hier würden die Requests implementiert werden
            
            # Beispielhafte Simulation eines Requests:
            # response = requests.post(...)
            
            # Für die Entwicklung geben wir vorerst einen Erfolg zurück
            self.finished.emit({"status": "success", "image_b64": ""})
        except Exception as e:
            self.error.emit(str(e))

class AIDiffusionDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Krita AI API Diffusion")
        
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # --- Settings Bereich ---
        settings_group = QGroupBox("Einstellungen")
        settings_layout = QVBoxLayout()
        
        self.flux_key_input = QLineEdit()
        self.flux_key_input.setPlaceholderText("Flux API Key...")
        self.flux_key_input.setEchoMode(QLineEdit.Password)
        settings_layout.addWidget(QLabel("Flux API Key (BFL):"))
        settings_layout.addWidget(self.flux_key_input)
        
        self.banana_key_input = QLineEdit()
        self.banana_key_input.setPlaceholderText("Banana API Key (Google)...")
        self.banana_key_input.setEchoMode(QLineEdit.Password)
        settings_layout.addWidget(QLabel("Banana API Key:"))
        settings_layout.addWidget(self.banana_key_input)
        
        save_settings_btn = QPushButton("Einstellungen speichern")
        save_settings_btn.clicked.connect(self.save_settings)
        settings_layout.addWidget(save_settings_btn)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # --- Modell Auswahl ---
        layout.addWidget(QLabel("Modell auswählen:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Flux (Text2Img)", "Flux (Inpainting)", "Banana"])
        layout.addWidget(self.model_combo)
        
        # --- Prompt Eingabe ---
        layout.addWidget(QLabel("Prompt:"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Beschreibe dein Bild...")
        layout.addWidget(self.prompt_edit)
        
        # --- Aktions Buttons ---
        self.generate_btn = QPushButton("Generieren (Text2Img)")
        self.generate_btn.clicked.connect(self.start_text2img)
        layout.addWidget(self.generate_btn)
        
        self.inpaint_btn = QPushButton("Inpaint Auswahl")
        self.inpaint_btn.clicked.connect(self.start_inpainting)
        layout.addWidget(self.inpaint_btn)
        
        # Status Anzeige
        self.status_label = QLabel("Bereit")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.setWidget(main_widget)
        self.load_settings()

    def load_settings(self):
        """Lädt die gespeicherten API-Keys aus den Krita-Einstellungen."""
        k = Krita.instance()
        flux_key = k.readSetting("AIDiffusion", "flux_api_key", "")
        banana_key = k.readSetting("AIDiffusion", "banana_api_key", "")
        self.flux_key_input.setText(flux_key)
        self.banana_key_input.setText(banana_key)

    def save_settings(self):
        """Speichert die API-Keys dauerhaft."""
        k = Krita.instance()
        k.writeSetting("AIDiffusion", "flux_api_key", self.flux_key_input.text())
        k.writeSetting("AIDiffusion", "banana_api_key", self.banana_key_input.text())
        self.status_label.setText("Einstellungen gespeichert!")

    def start_text2img(self):
        self.status_label.setText("Generiere Bild...")
        # Logik für Text2Img folgt im nächsten Schritt

    def start_inpainting(self):
        self.status_label.setText("Starte Inpainting...")
        # Logik für Inpainting folgt im nächsten Schritt

    def canvasChanged(self, canvas):
        pass
