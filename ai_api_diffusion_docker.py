import json, base64, time, urllib.request, urllib.error
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QComboBox, QPlainTextEdit, QMessageBox,
                             QTabWidget, QFormLayout, QSpinBox, QCheckBox, QFileDialog)
from krita import DockWidget, Krita

# ---------------------------------------------------------------------------
# Endpunkte
#   FLUX.2 (kontextbasiertes Editing)  -> input_image + prompt, KEINE mask
#   FLUX.1 Fill (maskenbasiert)        -> image + mask + prompt
# ---------------------------------------------------------------------------
FLUX2_MODELS = ["flux-2-pro", "flux-2-max", "flux-2-flex", "flux-2-klein-9b"]
FILL_ENDPOINT = "flux-pro-1.0-fill"
API_BASE = "https://api.bfl.ai/v1/"

# Wie viel Kontext-Rand um die Auswahl mitgeschickt wird (Anteil der Auswahlgröße)
CONTEXT_PAD = 0.35
# Maximale Kantenlänge, die zur API geschickt wird (Kosten/Speed-Bremse)
MAX_EDGE = 1536
# Federung der Maskenkante beim Zurück-Kompositing (kleiner Divisor = weicher)
FEATHER_DIV = 16


class APIWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, endpoint, payload, api_key, crop_info=None):
        super().__init__()
        self.endpoint = endpoint
        self.payload = payload
        self.api_key = api_key
        self.crop_info = crop_info

    def run(self):
        try:
            url = API_BASE + self.endpoint
            headers = {"accept": "application/json", "x-key": self.api_key,
                       "Content-Type": "application/json"}
            data = json.dumps(self.payload).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode())
            except urllib.error.HTTPError as he:
                detail = he.read().decode(errors="replace")
                raise Exception(f"HTTP {he.code} ({self.endpoint}): {detail}")

            polling_url = body.get("polling_url")
            if not polling_url:
                raise Exception(f"Keine polling_url erhalten: {body}")

            self.status.emit("Warte auf Ergebnis ...")
            while True:
                time.sleep(1.5)
                p_req = urllib.request.Request(polling_url, headers=headers)
                with urllib.request.urlopen(p_req, timeout=30) as p_resp:
                    res = json.loads(p_resp.read().decode())
                st = res.get("status")
                if st == "Ready":
                    img_url = res.get("result", {}).get("sample")
                    with urllib.request.urlopen(img_url, timeout=120) as i_resp:
                        self.finished.emit({"image_data": i_resp.read(),
                                            "crop": self.crop_info})
                    return
                if st in ("Error", "Failed", "Content Moderated",
                          "Request Moderated", "Task not found"):
                    raise Exception(f"BFL: {st} – {res.get('details') or res.get('error') or res}")
                self.status.emit(f"Status: {st} ...")
        except Exception as e:
            self.error.emit(str(e))


class AIDiffusionDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle("Krita AI API Diffusion")
        main_w = QWidget()
        layout = QVBoxLayout(main_w)
        self.tabs = QTabWidget()
        self.tab_gen = QWidget()
        self.tab_opt = QWidget()
        self.tabs.addTab(self.tab_gen, "Generieren")
        self.tabs.addTab(self.tab_opt, "Optionen")

        # --- Tab: Generieren -------------------------------------------------
        gen_l = QVBoxLayout(self.tab_gen)
        self.model_cb = QComboBox()
        self.model_cb.addItems(FLUX2_MODELS)
        self.prompt_ed = QPlainTextEdit()
        self.prompt_ed.setPlaceholderText(
            "Beschreibung / Edit-Anweisung, z.B. 'entferne die Person', "
            "'ersetze den Himmel durch Sonnenuntergang' ...")
        self.status_lbl = QLabel("Bereit")
        self.status_lbl.setWordWrap(True)

        # --- Referenzbild (optional, nur Kontext-Inpaint / Generieren) ------
        self.ref_b64 = None
        self.ref_lbl = QLabel("Kein Referenzbild")
        self.ref_lbl.setWordWrap(True)
        self.btn_ref = QPushButton("Referenzbild wählen ...")
        self.btn_ref_clr = QPushButton("Entfernen")
        self.btn_ref.clicked.connect(self.choose_ref)
        self.btn_ref_clr.clicked.connect(self.clear_ref)
        ref_row = QHBoxLayout()
        ref_row.addWidget(self.btn_ref)
        ref_row.addWidget(self.btn_ref_clr)
        ref_box = QWidget(); ref_box.setLayout(ref_row)

        self.btn_gen = QPushButton("Neues Bild (Text -> Bild)")
        self.btn_edit = QPushButton("Kontext-Inpaint (FLUX.2)")
        self.btn_fill = QPushButton("Masken-Inpaint (FLUX.1 Fill)")
        self.btn_gen.clicked.connect(lambda: self._start("generate"))
        self.btn_edit.clicked.connect(lambda: self._start("edit"))
        self.btn_fill.clicked.connect(lambda: self._start("fill"))

        for w in [QLabel("Modell (Generieren / Kontext-Inpaint):"), self.model_cb,
                  QLabel("Prompt:"), self.prompt_ed,
                  QLabel("Referenz (optional, z.B. Objekt zum Einfügen):"),
                  ref_box, self.ref_lbl,
                  self.btn_gen, self.btn_edit, self.btn_fill, self.status_lbl]:
            gen_l.addWidget(w)
        gen_l.addStretch()

        # --- Tab: Optionen ---------------------------------------------------
        opt_l = QFormLayout(self.tab_opt)
        self.f_key = QLineEdit()
        self.f_key.setEchoMode(QLineEdit.Password)
        btn_s = QPushButton("Speichern")
        btn_s.clicked.connect(self.save_k)

        self.gen_w = QSpinBox(); self.gen_w.setRange(256, 4096); self.gen_w.setSingleStep(64); self.gen_w.setValue(1024)
        self.gen_h = QSpinBox(); self.gen_h.setRange(256, 4096); self.gen_h.setSingleStep(64); self.gen_h.setValue(1024)
        self.feather_cb = QCheckBox("Maskenkante federn (weiche Übergänge)")
        self.feather_cb.setChecked(True)

        opt_l.addRow("API Key (BFL):", self.f_key)
        opt_l.addRow(btn_s)
        opt_l.addRow("Breite (Neues Bild):", self.gen_w)
        opt_l.addRow("Höhe (Neues Bild):", self.gen_h)
        opt_l.addRow(self.feather_cb)

        layout.addWidget(self.tabs)
        self.setWidget(main_w)
        self.load_k()

    # --- Settings -----------------------------------------------------------
    def save_k(self):
        Krita.instance().writeSetting("AIDiffusion", "fk_vPRO", self.f_key.text().strip())
        self.status_lbl.setText("Gespeichert.")

    def load_k(self):
        self.f_key.setText(Krita.instance().readSetting("AIDiffusion", "fk_vPRO", ""))

    # --- Helpers ------------------------------------------------------------
    def _warn(self, msg):
        self.status_lbl.setText(msg)
        QMessageBox.warning(None, "AI API Diffusion", msg)

    def choose_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Referenzbild wählen", "",
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            return self._warn("Referenzbild konnte nicht geladen werden.")
        # Auf MAX_EDGE begrenzen (Payload-Größe / Kosten)
        if max(img.width(), img.height()) > MAX_EDGE:
            img = img.scaled(MAX_EDGE, MAX_EDGE, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_ARGB32)
        self.ref_b64 = self.qimage_to_b64(img)
        name = path.replace("\\", "/").split("/")[-1]
        self.ref_lbl.setText(f"Referenz: {name} ({img.width()}x{img.height()})")

    def clear_ref(self):
        self.ref_b64 = None
        self.ref_lbl.setText("Kein Referenzbild")

    def _round32(self, v):
        return max(64, int(round(v / 32.0)) * 32)

    def _selection_crop(self, doc):
        """Bounding-Box der Auswahl + Kontext-Rand, geclamped auf Dokument."""
        sel = doc.selection()
        bx, by, bw, bh = sel.x(), sel.y(), sel.width(), sel.height()
        if bw <= 0 or bh <= 0:
            return None
        pad_x = int(bw * CONTEXT_PAD)
        pad_y = int(bh * CONTEXT_PAD)
        x0 = max(0, bx - pad_x)
        y0 = max(0, by - pad_y)
        x1 = min(doc.width(), bx + bw + pad_x)
        y1 = min(doc.height(), by + bh + pad_y)
        return x0, y0, x1 - x0, y1 - y0

    def _read_region(self, doc, x, y, w, h):
        """Sichtbares Compositing als QImage. Document.projection() liefert
        direkt ein QImage der Region (bereits korrekte Farben)."""
        img = doc.projection(x, y, w, h)
        return img.convertToFormat(QImage.Format_ARGB32)

    def _read_mask(self, doc, x, y, w, h):
        """Auswahl als Graustufen-QImage (255 = ausgewählt = inpaint) für die API."""
        raw = doc.selection().pixelData(x, y, w, h)
        img = QImage(raw, w, h, w, QImage.Format_Grayscale8)
        return img.copy()

    def _read_alpha(self, doc, x, y, w, h):
        """Auswahl direkt als Alpha8 (Wert == Alpha) fürs Zurück-Kompositing."""
        raw = doc.selection().pixelData(x, y, w, h)
        img = QImage(raw, w, h, w, QImage.Format_Alpha8)
        return img.copy()

    def _scaled_target(self, w, h):
        # Obergrenze (Kosten/Speed) ...
        scale = min(1.0, float(MAX_EDGE) / max(w, h))
        # ... und Untergrenze: BFL verlangt mind. 256 px pro Kante
        if min(w, h) * scale < 256:
            scale = 256.0 / min(w, h)
        return max(256, self._round32(w * scale)), max(256, self._round32(h * scale))

    def qimage_to_b64(self, qimg, fmt="PNG"):
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        qimg.save(buf, fmt)
        return base64.b64encode(ba.data()).decode("utf-8")

    # --- Start --------------------------------------------------------------
    def _start(self, mode):
        doc = Krita.instance().activeDocument()
        key = self.f_key.text().strip()
        if not doc:
            return self._warn("Kein aktives Dokument.")
        if not key:
            return self._warn("Bitte zuerst einen API Key unter 'Optionen' speichern.")
        if self.worker and self.worker.isRunning():
            return self._warn("Es läuft bereits eine Anfrage.")

        prompt = self.prompt_ed.toPlainText().strip()
        model = self.model_cb.currentText()

        if mode == "generate":
            if not prompt:
                return self._warn("Bitte einen Prompt eingeben.")
            payload = {"prompt": prompt,
                       "width": self._round32(self.gen_w.value()),
                       "height": self._round32(self.gen_h.value()),
                       "output_format": "png"}
            if self.ref_b64:  # FLUX.2: Referenz als Bildvorlage
                payload["input_image"] = self.ref_b64
            self._launch(model, payload, None, "Generiere Bild ...")
            return

        # edit / fill benötigen eine Auswahl
        crop = self._selection_crop(doc)
        if crop is None:
            return self._warn("Bitte zuerst einen Bereich auswählen (Auswahlwerkzeug).")
        x, y, w, h = crop
        tw, th = self._scaled_target(w, h)

        img = self._read_region(doc, x, y, w, h).scaled(
            tw, th, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        img_b64 = self.qimage_to_b64(img)

        crop_info = {"x": x, "y": y, "w": w, "h": h}

        if mode == "edit":
            if not prompt:
                return self._warn("Für Kontext-Inpaint bitte eine Edit-Anweisung eingeben.")
            # FLUX.2: kontextbasiert, KEINE Maske -> input_image + prompt
            # Optionale Referenz (z.B. Objekt/Stil) als input_image_2
            payload = {"prompt": prompt, "input_image": img_b64, "output_format": "png"}
            if self.ref_b64:
                payload["input_image_2"] = self.ref_b64
            self._launch(model, payload, crop_info, "Kontext-Inpaint (FLUX.2) ...")

        elif mode == "fill":
            # FLUX.1 Fill: image + mask (weiß = inpaint)
            mask = self._read_mask(doc, x, y, w, h).scaled(
                tw, th, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            mask_b64 = self.qimage_to_b64(mask)
            payload = {"prompt": prompt, "image": img_b64, "mask": mask_b64,
                       "output_format": "png"}
            self._launch(FILL_ENDPOINT, payload, crop_info, "Masken-Inpaint (FLUX.1 Fill) ...")

    def _launch(self, endpoint, payload, crop_info, status):
        self.status_lbl.setText(status)
        self._set_busy(True)
        self.worker = APIWorker(endpoint, payload, self.f_key.text().strip(), crop_info)
        self.worker.status.connect(self.status_lbl.setText)
        self.worker.finished.connect(self.handle_res)
        self.worker.error.connect(self.handle_err)
        self.worker.start()

    def _set_busy(self, busy):
        for b in (self.btn_gen, self.btn_edit, self.btn_fill):
            b.setEnabled(not busy)

    # --- Ergebnis -----------------------------------------------------------
    def handle_err(self, msg):
        self._set_busy(False)
        # Server spiegelt teils die (riesige) Base64-Eingabe zurück -> kürzen
        if len(msg) > 400:
            msg = msg[:400] + " ... [gekürzt]"
        self._warn("Fehler: " + msg)

    def handle_res(self, res):
        self._set_busy(False)
        doc = Krita.instance().activeDocument()
        if not doc:
            return
        result = QImage()
        result.loadFromData(res["image_data"])
        result = result.convertToFormat(QImage.Format_ARGB32)
        crop = res["crop"]

        if crop is None:
            # Neues Bild -> volle Ebene
            layer = doc.createNode("AI Generation", "paintLayer")
            doc.rootNode().addChildNode(layer, None)
            rgba = result  # ARGB32-Bytes == BGRA-Layout, passt zu Krita
            layer.setPixelData(rgba.bits().asstring(rgba.width() * rgba.height() * 4),
                               0, 0, rgba.width(), rgba.height())
            doc.refreshProjection()
            self.status_lbl.setText("Fertig – neues Bild eingefügt.")
            return

        x, y, w, h = crop["x"], crop["y"], crop["w"], crop["h"]
        # Ergebnis auf native Crop-Größe zurückskalieren
        result = result.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        # Alpha aus der Auswahl (nur innerhalb der Maske übernehmen)
        alpha = self._read_alpha(doc, x, y, w, h)
        if self.feather_cb.isChecked():
            d = max(2, min(w, h) // FEATHER_DIV)
            small = alpha.scaled(max(1, w // d), max(1, h // d),
                                 Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            alpha = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        composite = QImage(w, h, QImage.Format_ARGB32)
        composite.fill(Qt.transparent)
        p = QPainter(composite)
        p.drawImage(0, 0, result)
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.drawImage(0, 0, alpha)
        p.end()

        layer = doc.createNode("AI Inpaint", "paintLayer")
        doc.rootNode().addChildNode(layer, None)
        layer.setPixelData(composite.bits().asstring(w * h * 4), x, y, w, h)
        doc.refreshProjection()
        self.status_lbl.setText("Fertig – Inpaint als neue Ebene eingefügt.")

    def canvasChanged(self, canvas):
        pass
