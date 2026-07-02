import json
import base64
import time
import urllib.request
import urllib.error
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QPlainTextEdit, 
    QScrollArea, QGroupBox, QMessageBox, QTabWidget, QFormLayout
)
from krita import DockWidget, Krita, InfoObject, Selection

class APIWorker(QThread):
    """Worker für asynchrone API-Anfragen an BFL Flux und Google Gemini."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, api_type, prompt, api_key, model_name, image_b64=None, mask_b64=None):
        super().__init__()
        self.api_type = api_type
        self.prompt = prompt
        self.api_key = api_key
        self.model_name = model_name
        self.image_b64 = image_b64
        self.mask_b64 = mask_b64

    def run(self):
        try:
            if self.api_type == "flux":
                self.run_flux()
            elif self.api_type == "google":
                self.run_google()
        except Exception as e:
            self.error.emit(str(e))

    def run_flux(self):
        # Neue BFL API Endpunkte gemäß Dokumentation
        model_id = "flux-2-pro"
        if "ULTRA" in self.model_name.upper(): model_id = "flux-2-pro-ultra"
        elif "MAX" in self.model_name.upper(): model_id = "flux-2-max"
        elif "FLEX" in self.model_name.upper(): model_id = "flux-2-flex"
        elif "KLEIN" in self.model_name.upper(): model_id = "flux-2-klein"

        url = f"https://api.bfl.ai/v1/{model_id}"
        headers = {
            "accept": "application/json",
            "x-key": self.api_key, 
            "Content-Type": "application/json",
            "User-Agent": "Krita-Plugin/2.0"
        }
        
        payload = {"prompt": self.prompt}
        
        # LOGIK FÜR INPAINTING / REDRAW
        # Wenn Bilddaten vorhanden sind, müssen wir die Dimensionen an das Quellbild anpassen
        if self.image_b64:
            # Bei Redraw nutzen wir die exakten Pixelmaße der Auswahl
            # Diese werden im Worker in __init__ noch nicht gesetzt, wir berechnen sie aus den B64 Daten
            # Oder besser: Wir lassen Flux das Resizing machen, aber setzen die Zielgröße
            payload["image"] = self.image_b64
            payload["mask"] = self.mask_b64
            # Flux Redraw benötigt Breite/Höhe des Eingabebildes
            # Da wir in Krita croppen, setzen wir hier die Standardwerte oder extrahieren sie
            payload["width"] = 1024 
            payload["height"] = 1024
        elif "ULTRA" in model_id.upper() or "MAX" in model_id.upper():
            payload["aspect_ratio"] = "1:1"
        else:
            payload["width"] = 1024
            payload["height"] = 1024

        self.status.emit(f"Sende Request an {model_id}...")
        
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST')
            # Timeout auf 60s erhöhen für initialen Request
            with urllib.request.urlopen(req, timeout=60) as response:
                resp_data = json.loads(response.read().decode())
                polling_url = resp_data.get("polling_url")
        except urllib.error.HTTPError as e:
            raise Exception(f"BFL API Fehler {e.code}: {e.read().decode()}")

        while True:
            time.sleep(2)
            self.status.emit("Warte auf Bild...")
            try:
                # Polling an der von der API gelieferten URL
                poll_req = urllib.request.Request(polling_url, headers={"x-key": self.api_key, "accept": "application/json"})
                with urllib.request.urlopen(poll_req, timeout=30) as response:
                    res = json.loads(response.read().decode())
                    if res.get("status") == "Ready":
                        img_url = res.get("result", {}).get("sample")
                        # Bild herunterladen
                        with urllib.request.urlopen(img_url, timeout=60) as img_res:
                            self.finished.emit({"image_data": img_res.read()})
                        break
                    elif res.get("status") in ["Failed", "Error"]:
                        raise Exception(f"BFL Fehler: {res.get('error')}")
            except Exception as e:
                self.status.emit(f"Polling... ({str(e)})")

    def run_google(self):
        # Nano Banana 2 (Gemini 3.1 Flash Image)
        model = "gemini-3.1-flash-image"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "instances": [{"prompt": self.prompt}],
            "parameters": {"sampleCount": 1}
        }
        
        if self.image_b64:
            payload["instances"][0]["image"] = {"bytesBase64Encoded": self.image_b64}

        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            b64 = data["predictions"][0]["bytesBase64Encoded"]
            self.finished.emit({"image_data": base64.b64decode(b64)})

class AIDiffusionDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Krita AI API Diffusion")
        
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        self.tabs = QTabWidget()
        self.tab_gen = QWidget()
        self.tab_set = QWidget()
        self.tabs.addTab(self.tab_gen, "Generieren")
        self.tabs.addTab(self.tab_set, "Optionen")
        
        # UI Tab Generieren
        gen_layout = QVBoxLayout(self.tab_gen)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "FLUX.2 [max]", 
            "FLUX.2 [pro]", 
            "FLUX.2 [flex]", 
            "FLUX.2 [klein]",
            "Nano Banana 2 (Gemini 3.1)"
        ])
        gen_layout.addWidget(QLabel("Backend Modell:"))
        gen_layout.addWidget(self.model_combo)
        
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Beschreibe dein Bild...")
        gen_layout.addWidget(QLabel("Prompt:"))
        gen_layout.addWidget(self.prompt_edit)
        
        self.btn_gen = QPushButton("Jetzt Generieren")
        self.btn_gen.clicked.connect(self.start_text2img)
        gen_layout.addWidget(self.btn_gen)
        
        self.btn_inp = QPushButton("Inpaint (Auswahl nutzen)")
        self.btn_inp.clicked.connect(self.start_inpainting)
        gen_layout.addWidget(self.btn_inp)
        
        self.status_label = QLabel("Status: Bereit")
        gen_layout.addWidget(self.status_label)
        gen_layout.addStretch()

        # UI Tab Einstellungen
        set_layout = QFormLayout(self.tab_set)
        self.flux_key = QLineEdit()
        self.flux_key.setEchoMode(QLineEdit.Password)
        self.google_key = QLineEdit()
        self.google_key.setEchoMode(QLineEdit.Password)
        set_layout.addRow("BFL Flux Key:", self.flux_key)
        set_layout.addRow("Google Key:", self.google_key)
        
        btn_save = QPushButton("Keys Speichern")
        btn_save.clicked.connect(self.save_settings)
        set_layout.addRow(btn_save)

        layout.addWidget(self.tabs)
        self.setWidget(main_widget)
        self.load_settings()

    def save_settings(self):
        k = Krita.instance()
        k.writeSetting("AIDiffusion", "f_key", self.flux_key.text())
        k.writeSetting("AIDiffusion", "g_key", self.google_key.text())
        self.status_label.setText("Status: Einstellungen gespeichert")

    def load_settings(self):
        k = Krita.instance()
        self.flux_key.setText(k.readSetting("AIDiffusion", "f_key", ""))
        self.google_key.setText(k.readSetting("AIDiffusion", "g_key", ""))

    def start_text2img(self):
        self._run_api()

    def start_inpainting(self):
        doc = Krita.instance().activeDocument()
        if not doc or not doc.selection():
            QMessageBox.warning(self, "Fehler", "Bitte erst eine Auswahl in Krita ziehen!")
            return
        
        sel = doc.selection()
        x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
        
        # WICHTIG: Krita AI Diffusion Skalierungs-Logik
        # Wir müssen das Bild auf eine von Flux unterstützte Größe bringen (z.B. 1024x1024)
        # aber die Proportionen beibehalten.
        
        # Pixel & Maske extrahieren
        raw_img = QImage(doc.pixelData(x,y,w,h), w, h, QImage.Format_RGBA8888)
        raw_msk = QImage(sel.pixelData(x,y,w,h), w, h, QImage.Format_Grayscale8)
        
        # Resize auf 1024 (Flux Standard) für bessere Ergebnisse und API Specs
        scaled_img = raw_img.scaled(1024, 1024, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled_msk = raw_msk.scaled(1024, 1024, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        img_b64 = self.qimage_to_b64(scaled_img)
        msk_b64 = self.qimage_to_b64(scaled_msk)
        
        self._run_api(img_b64, msk_b64, x, y, w, h) # Reiche Originalgröße weiter

    def _run_api(self, img=None, msk=None, x=0, y=0, orig_w=0, orig_h=0):
        mode = self.model_combo.currentText()
        is_flux = "FLUX" in mode.upper()
        key = self.flux_key.text().strip() if is_flux else self.google_key.text().strip()
        
        if not key:
            QMessageBox.warning(self, "Fehler", f"Bitte API Key für {'Flux' if is_flux else 'Google'} in den Optionen eingeben!")
            return

        self.worker = APIWorker("flux" if is_flux else "google", self.prompt_edit.toPlainText(), key, mode, img, msk)
        self.worker.status.connect(self.status_label.setText)
        # Übergebe Originalmaße an Handle Result für korrektes Upscaling zurück
        self.worker.finished.connect(lambda res: self.handle_result(res, x, y, orig_w, orig_h))
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "API Fehler", e))
        self.worker.start()

    def qimage_to_b64(self, qimg):
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        qimg.save(buffer, "PNG")
        return base64.b64encode(ba.data()).decode("utf-8")

    def handle_result(self, result, x, y, orig_w=0, orig_h=0):
        qimg = QImage()
        if not qimg.loadFromData(result["image_data"]):
            self.status_label.setText("Fehler: Bilddaten ungültig")
            return
            
        doc = Krita.instance().activeDocument()
        if not doc: return
        
        # Wenn es Inpainting war, skaliere das Bild zurück auf die Originalgröße der Auswahl
        if orig_w > 0 and orig_h > 0:
            qimg = qimg.scaled(orig_w, orig_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        layer = doc.createNode("AI Result", "paintLayer")
        qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
        
        ptr = qimg.bits()
        ptr.setsize(qimg.byteCount())
        pixel_data = ptr.asstring()
        
        layer.setPixelData(pixel_data, 0, 0, qimg.width(), qimg.height())
        doc.rootNode().addChildNode(layer, None)
        
        if x != 0 or y != 0:
            layer.move(x, y)
            
        doc.refreshProjection()
        self.status_label.setText(f"Inpaint erfolgreich eingefügt bei {x},{y}")

    def canvasChanged(self, canvas): pass
