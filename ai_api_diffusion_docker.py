import json, base64, time, random, urllib.request, urllib.error
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
# Modelle mit Anbieter-Zuordnung. provider: "bfl" (Black Forest Labs) | "google"
MODELS = [
    {"label": "flux-2-pro", "provider": "bfl", "id": "flux-2-pro"},
    {"label": "flux-2-max", "provider": "bfl", "id": "flux-2-max"},
    {"label": "flux-2-flex", "provider": "bfl", "id": "flux-2-flex"},
    {"label": "flux-2-klein-9b", "provider": "bfl", "id": "flux-2-klein-9b"},
    {"label": "nano-banana-2 (Gemini 3.1 Flash)", "provider": "google",
     "id": "gemini-3.1-flash-image"},
    {"label": "nano-banana-pro (Gemini 3 Pro)", "provider": "google",
     "id": "gemini-3-pro-image"},
]
FILL_ENDPOINT = "flux-pro-1.0-fill"
API_BASE = "https://api.bfl.ai/v1/"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"

# Seitenverhältnis-Presets (~1 MP, Kanten Vielfache von 64) für "Neues Bild"
ASPECT_PRESETS = [
    ("Custom", None),
    ("1:1", (1024, 1024)),
    ("3:2", (1216, 832)),
    ("2:3", (832, 1216)),
    ("16:9", (1344, 768)),
    ("9:16", (768, 1344)),
    ("4:3", (1152, 896)),
    ("3:4", (896, 1152)),
]

CONTEXT_PAD = 0.35   # Kontext-Rand um die Auswahl (Anteil der Auswahlgröße)
MAX_EDGE = 1536      # Max. Kantenlänge, die zur API geschickt wird
FEATHER_DIV = 16     # Federung der Maskenkante (kleiner = weicher)

# ---------------------------------------------------------------------------
# Mehrsprachigkeit
# ---------------------------------------------------------------------------
LANGUAGES = [("English", "en"), ("Deutsch", "de"), ("中文", "zh"), ("ไทย", "th")]

TR = {
    "en": {
        "tab_generate": "Generate", "tab_options": "Options",
        "label_model": "Model (Generate / Context Inpaint):",
        "label_prompt": "Prompt:",
        "prompt_placeholder": "Description / edit instruction, e.g. 'remove the person', "
                              "'replace the sky with a sunset' ...",
        "label_reference": "Reference (optional, e.g. object to insert):",
        "btn_ref_choose": "Choose reference image ...", "btn_ref_clear": "Remove",
        "ref_none": "No reference image", "ref_set": "Reference: {name} ({w}x{h})",
        "btn_generate": "New image (text -> image)",
        "btn_edit": "Context Inpaint",
        "btn_fill": "Mask Inpaint (FLUX only)",
        "status_ready": "Ready", "status_generating": "Generating image ...",
        "status_edit": "Context Inpaint ...",
        "status_fill": "Mask Inpaint (FLUX.1 Fill) ...",
        "status_waiting": "Waiting for result ...", "status_prefix": "Status:",
        "done_generate": "Done - new image inserted.",
        "done_inpaint": "Done - inpaint inserted as new layer.",
        "label_apikey": "API Key (BFL):", "btn_save": "Save", "saved": "Saved.",
        "label_width": "Width (new image):", "label_height": "Height (new image):",
        "feather": "Feather mask edge (soft transitions)", "label_language": "Language:",
        "btn_cancel": "Cancel", "status_cancelled": "Cancelled.",
        "label_aspect": "Aspect ratio (new image):", "label_seed": "Seed:",
        "seed_random": "Random seed", "btn_dice": "New seed",
        "label_batch": "Variants per run:", "status_batch_done": "Done - {n} variants.",
        "label_gkey": "Google AI Studio API Key:",
        "warn_no_gkey": "Please save a Google AI Studio API key under 'Options' first.",
        "warn_fill_flux_only": "Mask Inpaint requires a FLUX model. Nano Banana supports "
                               "Generate and Context Inpaint.",
        "warn_no_doc": "No active document.",
        "warn_no_key": "Please save an API key under 'Options' first.",
        "warn_running": "A request is already running.",
        "warn_no_prompt": "Please enter a prompt.",
        "warn_no_prompt_edit": "Please enter an edit instruction for context inpaint.",
        "warn_no_selection": "Please select an area first (selection tool).",
        "warn_ref_load": "Reference image could not be loaded.",
        "err_prefix": "Error: ",
        "dlg_choose_ref": "Choose reference image",
        "dlg_filter": "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
    },
    "de": {
        "tab_generate": "Generieren", "tab_options": "Optionen",
        "label_model": "Modell (Generieren / Kontext-Inpaint):",
        "label_prompt": "Prompt:",
        "prompt_placeholder": "Beschreibung / Edit-Anweisung, z.B. 'entferne die Person', "
                              "'ersetze den Himmel durch Sonnenuntergang' ...",
        "label_reference": "Referenz (optional, z.B. Objekt zum Einfügen):",
        "btn_ref_choose": "Referenzbild wählen ...", "btn_ref_clear": "Entfernen",
        "ref_none": "Kein Referenzbild", "ref_set": "Referenz: {name} ({w}x{h})",
        "btn_generate": "Neues Bild (Text -> Bild)",
        "btn_edit": "Kontext-Inpaint",
        "btn_fill": "Masken-Inpaint (nur FLUX)",
        "status_ready": "Bereit", "status_generating": "Generiere Bild ...",
        "status_edit": "Kontext-Inpaint ...",
        "status_fill": "Masken-Inpaint (FLUX.1 Fill) ...",
        "status_waiting": "Warte auf Ergebnis ...", "status_prefix": "Status:",
        "done_generate": "Fertig - neues Bild eingefügt.",
        "done_inpaint": "Fertig - Inpaint als neue Ebene eingefügt.",
        "label_apikey": "API Key (BFL):", "btn_save": "Speichern", "saved": "Gespeichert.",
        "label_width": "Breite (Neues Bild):", "label_height": "Höhe (Neues Bild):",
        "feather": "Maskenkante federn (weiche Übergänge)", "label_language": "Sprache:",
        "btn_cancel": "Abbrechen", "status_cancelled": "Abgebrochen.",
        "label_aspect": "Seitenverhältnis (Neues Bild):", "label_seed": "Seed:",
        "seed_random": "Zufalls-Seed", "btn_dice": "Neuer Seed",
        "label_batch": "Varianten pro Lauf:", "status_batch_done": "Fertig - {n} Varianten.",
        "label_gkey": "Google AI Studio API Key:",
        "warn_no_gkey": "Bitte zuerst einen Google AI Studio API Key unter 'Optionen' speichern.",
        "warn_fill_flux_only": "Masken-Inpaint benötigt ein FLUX-Modell. Nano Banana kann "
                               "Generieren und Kontext-Inpaint.",
        "warn_no_doc": "Kein aktives Dokument.",
        "warn_no_key": "Bitte zuerst einen API Key unter 'Optionen' speichern.",
        "warn_running": "Es läuft bereits eine Anfrage.",
        "warn_no_prompt": "Bitte einen Prompt eingeben.",
        "warn_no_prompt_edit": "Für Kontext-Inpaint bitte eine Edit-Anweisung eingeben.",
        "warn_no_selection": "Bitte zuerst einen Bereich auswählen (Auswahlwerkzeug).",
        "warn_ref_load": "Referenzbild konnte nicht geladen werden.",
        "err_prefix": "Fehler: ",
        "dlg_choose_ref": "Referenzbild wählen",
        "dlg_filter": "Bilder (*.png *.jpg *.jpeg *.webp *.bmp)",
    },
    "zh": {
        "tab_generate": "生成", "tab_options": "选项",
        "label_model": "模型（生成 / 上下文修复）：",
        "label_prompt": "提示词：",
        "prompt_placeholder": "描述 / 编辑指令，例如 '移除人物'、'把天空替换为日落' ...",
        "label_reference": "参考图（可选，例如要插入的物体）：",
        "btn_ref_choose": "选择参考图 ...", "btn_ref_clear": "移除",
        "ref_none": "无参考图", "ref_set": "参考图：{name}（{w}x{h}）",
        "btn_generate": "新建图像（文本 → 图像）",
        "btn_edit": "上下文修复",
        "btn_fill": "蒙版修复（仅 FLUX）",
        "status_ready": "就绪", "status_generating": "正在生成图像 ...",
        "status_edit": "上下文修复 ...",
        "status_fill": "蒙版修复（FLUX.1 Fill）...",
        "status_waiting": "等待结果 ...", "status_prefix": "状态：",
        "done_generate": "完成 - 已插入新图像。",
        "done_inpaint": "完成 - 已作为新图层插入修复结果。",
        "label_apikey": "API 密钥（BFL）：", "btn_save": "保存", "saved": "已保存。",
        "label_width": "宽度（新图像）：", "label_height": "高度（新图像）：",
        "feather": "羽化蒙版边缘（柔和过渡）", "label_language": "语言：",
        "btn_cancel": "取消", "status_cancelled": "已取消。",
        "label_aspect": "宽高比（新图像）：", "label_seed": "种子：",
        "seed_random": "随机种子", "btn_dice": "新种子",
        "label_batch": "每次生成数量：", "status_batch_done": "完成 - {n} 个变体。",
        "label_gkey": "Google AI Studio API 密钥：",
        "warn_no_gkey": "请先在 '选项' 中保存 Google AI Studio API 密钥。",
        "warn_fill_flux_only": "蒙版修复需要 FLUX 模型。Nano Banana 支持生成和上下文修复。",
        "warn_no_doc": "没有活动文档。",
        "warn_no_key": "请先在 '选项' 中保存 API 密钥。",
        "warn_running": "已有请求正在运行。",
        "warn_no_prompt": "请输入提示词。",
        "warn_no_prompt_edit": "上下文修复请输入编辑指令。",
        "warn_no_selection": "请先选择一个区域（选择工具）。",
        "warn_ref_load": "无法加载参考图。",
        "err_prefix": "错误：",
        "dlg_choose_ref": "选择参考图",
        "dlg_filter": "图像 (*.png *.jpg *.jpeg *.webp *.bmp)",
    },
    "th": {
        "tab_generate": "สร้าง", "tab_options": "ตัวเลือก",
        "label_model": "โมเดล (สร้าง / อินเพนต์ตามบริบท):",
        "label_prompt": "พรอมป์:",
        "prompt_placeholder": "คำอธิบาย / คำสั่งแก้ไข เช่น 'ลบบุคคลออก', "
                              "'เปลี่ยนท้องฟ้าเป็นพระอาทิตย์ตก' ...",
        "label_reference": "ภาพอ้างอิง (ไม่บังคับ เช่น วัตถุที่จะใส่เข้าไป):",
        "btn_ref_choose": "เลือกภาพอ้างอิง ...", "btn_ref_clear": "ลบออก",
        "ref_none": "ไม่มีภาพอ้างอิง", "ref_set": "อ้างอิง: {name} ({w}x{h})",
        "btn_generate": "ภาพใหม่ (ข้อความ → ภาพ)",
        "btn_edit": "อินเพนต์ตามบริบท",
        "btn_fill": "อินเพนต์ด้วยมาสก์ (เฉพาะ FLUX)",
        "status_ready": "พร้อม", "status_generating": "กำลังสร้างภาพ ...",
        "status_edit": "อินเพนต์ตามบริบท ...",
        "status_fill": "อินเพนต์ด้วยมาสก์ (FLUX.1 Fill) ...",
        "status_waiting": "กำลังรอผลลัพธ์ ...", "status_prefix": "สถานะ:",
        "done_generate": "เสร็จสิ้น - แทรกภาพใหม่แล้ว",
        "done_inpaint": "เสร็จสิ้น - แทรกผลอินเพนต์เป็นเลเยอร์ใหม่แล้ว",
        "label_apikey": "คีย์ API (BFL):", "btn_save": "บันทึก", "saved": "บันทึกแล้ว",
        "label_width": "ความกว้าง (ภาพใหม่):", "label_height": "ความสูง (ภาพใหม่):",
        "feather": "ทำขอบมาสก์ให้นุ่ม (การเปลี่ยนผ่านนุ่มนวล)", "label_language": "ภาษา:",
        "btn_cancel": "ยกเลิก", "status_cancelled": "ยกเลิกแล้ว",
        "label_aspect": "อัตราส่วนภาพ (ภาพใหม่):", "label_seed": "ซีด:",
        "seed_random": "ซีดสุ่ม", "btn_dice": "ซีดใหม่",
        "label_batch": "จำนวนต่อรอบ:", "status_batch_done": "เสร็จสิ้น - {n} แบบ",
        "label_gkey": "คีย์ API ของ Google AI Studio:",
        "warn_no_gkey": "กรุณาบันทึกคีย์ API ของ Google AI Studio ใน 'ตัวเลือก' ก่อน",
        "warn_fill_flux_only": "อินเพนต์ด้วยมาสก์ต้องใช้โมเดล FLUX. Nano Banana รองรับ "
                               "การสร้างและอินเพนต์ตามบริบท",
        "warn_no_doc": "ไม่มีเอกสารที่ใช้งานอยู่",
        "warn_no_key": "กรุณาบันทึกคีย์ API ใน 'ตัวเลือก' ก่อน",
        "warn_running": "มีคำขอกำลังทำงานอยู่แล้ว",
        "warn_no_prompt": "กรุณาใส่พรอมป์",
        "warn_no_prompt_edit": "กรุณาใส่คำสั่งแก้ไขสำหรับอินเพนต์ตามบริบท",
        "warn_no_selection": "กรุณาเลือกพื้นที่ก่อน (เครื่องมือเลือก)",
        "warn_ref_load": "ไม่สามารถโหลดภาพอ้างอิงได้",
        "err_prefix": "ข้อผิดพลาด: ",
        "dlg_choose_ref": "เลือกภาพอ้างอิง",
        "dlg_filter": "รูปภาพ (*.png *.jpg *.jpeg *.webp *.bmp)",
    },
}


class APIWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, endpoint, payload, api_key, crop_info=None,
                 status_wait="Waiting for result ...", status_prefix="Status:",
                 provider="bfl"):
        super().__init__()
        self.endpoint = endpoint
        self.payload = payload
        self.api_key = api_key
        self.crop_info = crop_info
        self.status_wait = status_wait
        self.status_prefix = status_prefix
        self.provider = provider
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            if self._cancel:
                return
            if self.provider == "google":
                self._run_google()
            else:
                self._run_bfl()
        except Exception as e:
            if not self._cancel:
                self.error.emit(str(e))

    def _run_google(self):
        # Gemini generateContent: synchron, Bild als inline_data zurück
        url = "{}{}:generateContent".format(GEMINI_BASE, self.endpoint)
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        parts = [{"text": self.payload.get("prompt", "")}]
        for b64 in self.payload.get("images", []):
            parts.append({"inline_data": {"mime_type": "image/png", "data": b64}})
        body = {"contents": [{"parts": parts}]}
        if self.payload.get("seed") is not None:
            body["generationConfig"] = {"seed": int(self.payload["seed"])}
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                res = json.loads(resp.read().decode())
        except urllib.error.HTTPError as he:
            detail = he.read().decode(errors="replace")
            raise Exception(f"HTTP {he.code} (Gemini {self.endpoint}): {detail}")

        if self._cancel:
            return
        cands = res.get("candidates") or []
        if not cands:
            fb = res.get("promptFeedback") or res.get("error") or res
            raise Exception(f"Gemini: no candidates - {fb}")
        for part in cands[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                img_bytes = base64.b64decode(inline["data"])
                self.finished.emit({"image_data": img_bytes, "crop": self.crop_info})
                return
        # Kein Bild -> ggf. Text/Blockgrund zurückgeben
        reason = cands[0].get("finishReason", "")
        texts = [p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])]
        raise Exception(f"Gemini: no image returned ({reason}) {' '.join(texts)[:200]}")

    def _run_bfl(self):
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
                raise Exception(f"No polling_url received: {body}")

            self.status.emit(self.status_wait)
            while True:
                if self._cancel:
                    return
                time.sleep(1.5)
                if self._cancel:
                    return
                p_req = urllib.request.Request(polling_url, headers=headers)
                with urllib.request.urlopen(p_req, timeout=30) as p_resp:
                    res = json.loads(p_resp.read().decode())
                st = res.get("status")
                if st == "Ready":
                    img_url = res.get("result", {}).get("sample")
                    with urllib.request.urlopen(img_url, timeout=120) as i_resp:
                        data_bytes = i_resp.read()
                    if self._cancel:
                        return
                    self.finished.emit({"image_data": data_bytes, "crop": self.crop_info})
                    return
                if st in ("Error", "Failed", "Content Moderated",
                          "Request Moderated", "Task not found"):
                    raise Exception(f"BFL: {st} - {res.get('details') or res.get('error') or res}")
                self.status.emit(f"{self.status_prefix} {st} ...")
        except Exception as e:
            self.error.emit(str(e))


class AIDiffusionDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.busy = False
        self._batch = None   # aktiver Batch-Zustand (siehe _begin)
        self._threads = []   # hält abgebrochene, noch laufende Worker am Leben (Anti-GC)
        self.ref_b64 = None
        self.ref_name = None
        self.ref_w = self.ref_h = 0
        self.lang = Krita.instance().readSetting("AIDiffusion", "lang", "en") or "en"
        if self.lang not in TR:
            self.lang = "en"

        self.setWindowTitle("Krita AI API Diffusion")
        main_w = QWidget()
        layout = QVBoxLayout(main_w)
        self.tabs = QTabWidget()
        self.tab_gen = QWidget()
        self.tab_opt = QWidget()
        self.tabs.addTab(self.tab_gen, "")
        self.tabs.addTab(self.tab_opt, "")

        # --- Tab: Generieren -------------------------------------------------
        gen_l = QVBoxLayout(self.tab_gen)
        self.lbl_model = QLabel()
        self.model_cb = QComboBox()
        self.model_cb.addItems([m["label"] for m in MODELS])
        self.model_cb.currentIndexChanged.connect(self._on_model_changed)
        self.lbl_prompt = QLabel()
        self.prompt_ed = QPlainTextEdit()
        self.status_lbl = QLabel()
        self.status_lbl.setWordWrap(True)

        self.lbl_ref = QLabel()
        self.ref_lbl = QLabel()
        self.ref_lbl.setWordWrap(True)
        self.btn_ref = QPushButton()
        self.btn_ref_clr = QPushButton()
        self.btn_ref.clicked.connect(self.choose_ref)
        self.btn_ref_clr.clicked.connect(self.clear_ref)
        ref_row = QHBoxLayout()
        ref_row.addWidget(self.btn_ref)
        ref_row.addWidget(self.btn_ref_clr)
        ref_box = QWidget(); ref_box.setLayout(ref_row)

        self.btn_gen = QPushButton()
        self.btn_edit = QPushButton()
        self.btn_fill = QPushButton()
        self.btn_cancel = QPushButton()
        self.btn_gen.clicked.connect(lambda: self._start("generate"))
        self.btn_edit.clicked.connect(lambda: self._start("edit"))
        self.btn_fill.clicked.connect(lambda: self._start("fill"))
        self.btn_cancel.clicked.connect(self.cancel_req)
        self.btn_cancel.setEnabled(False)

        for w in [self.lbl_model, self.model_cb, self.lbl_prompt, self.prompt_ed,
                  self.lbl_ref, ref_box, self.ref_lbl,
                  self.btn_gen, self.btn_edit, self.btn_fill, self.btn_cancel,
                  self.status_lbl]:
            gen_l.addWidget(w)
        gen_l.addStretch()

        # --- Tab: Optionen ---------------------------------------------------
        opt_l = QFormLayout(self.tab_opt)
        self.lang_cb = QComboBox()
        self.lang_cb.addItems([name for name, _ in LANGUAGES])
        codes = [c for _, c in LANGUAGES]
        self.lang_cb.setCurrentIndex(codes.index(self.lang) if self.lang in codes else 0)
        self.lang_cb.currentIndexChanged.connect(self._on_lang_changed)

        self.f_key = QLineEdit()
        self.f_key.setEchoMode(QLineEdit.Password)
        self.g_key = QLineEdit()
        self.g_key.setEchoMode(QLineEdit.Password)
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_k)

        self.aspect_cb = QComboBox()
        self.aspect_cb.addItems([name for name, _ in ASPECT_PRESETS])
        self.aspect_cb.currentIndexChanged.connect(self._on_aspect_changed)
        self.gen_w = QSpinBox(); self.gen_w.setRange(256, 4096); self.gen_w.setSingleStep(64); self.gen_w.setValue(1024)
        self.gen_h = QSpinBox(); self.gen_h.setRange(256, 4096); self.gen_h.setSingleStep(64); self.gen_h.setValue(1024)
        self.feather_cb = QCheckBox()
        self.feather_cb.setChecked(True)

        # Seed: Zufall (Checkbox) + fester Wert + Würfel-Button
        self.seed_random = QCheckBox()
        self.seed_random.setChecked(True)
        self.seed_val = QSpinBox(); self.seed_val.setRange(0, 2147483647)
        self.seed_val.setEnabled(False)
        self.btn_dice = QPushButton()
        self.seed_random.toggled.connect(lambda on: self.seed_val.setEnabled(not on))
        self.btn_dice.clicked.connect(self._roll_seed)
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed_random)
        seed_row.addWidget(self.seed_val, 1)
        seed_row.addWidget(self.btn_dice)
        seed_box = QWidget(); seed_box.setLayout(seed_row)

        self.batch_val = QSpinBox(); self.batch_val.setRange(1, 8); self.batch_val.setValue(1)

        self.lbl_lang = QLabel()
        self.lbl_apikey = QLabel()
        self.lbl_gkey = QLabel()
        self.lbl_aspect = QLabel()
        self.lbl_width = QLabel()
        self.lbl_height = QLabel()
        self.lbl_seed = QLabel()
        self.lbl_batch = QLabel()
        opt_l.addRow(self.lbl_lang, self.lang_cb)
        opt_l.addRow(self.lbl_apikey, self.f_key)
        opt_l.addRow(self.lbl_gkey, self.g_key)
        opt_l.addRow(self.btn_save)
        opt_l.addRow(self.lbl_aspect, self.aspect_cb)
        opt_l.addRow(self.lbl_width, self.gen_w)
        opt_l.addRow(self.lbl_height, self.gen_h)
        opt_l.addRow(self.lbl_seed, seed_box)
        opt_l.addRow(self.lbl_batch, self.batch_val)
        opt_l.addRow(self.feather_cb)

        layout.addWidget(self.tabs)
        self.setWidget(main_w)
        self.load_k()
        self.apply_language()
        self._on_model_changed()
        self.status_lbl.setText(self.tr("status_ready"))

    # --- i18n ---------------------------------------------------------------
    def tr(self, key, **kw):
        s = TR.get(self.lang, TR["en"]).get(key) or TR["en"].get(key, key)
        return s.format(**kw) if kw else s

    def _on_lang_changed(self, idx):
        self.lang = LANGUAGES[idx][1]
        Krita.instance().writeSetting("AIDiffusion", "lang", self.lang)
        self.apply_language()

    def apply_language(self):
        self.tabs.setTabText(0, self.tr("tab_generate"))
        self.tabs.setTabText(1, self.tr("tab_options"))
        self.lbl_model.setText(self.tr("label_model"))
        self.lbl_prompt.setText(self.tr("label_prompt"))
        self.prompt_ed.setPlaceholderText(self.tr("prompt_placeholder"))
        self.lbl_ref.setText(self.tr("label_reference"))
        self.btn_ref.setText(self.tr("btn_ref_choose"))
        self.btn_ref_clr.setText(self.tr("btn_ref_clear"))
        self._update_ref_label()
        self.btn_gen.setText(self.tr("btn_generate"))
        self.btn_edit.setText(self.tr("btn_edit"))
        self.btn_fill.setText(self.tr("btn_fill"))
        self.btn_cancel.setText(self.tr("btn_cancel"))
        self.lbl_lang.setText(self.tr("label_language"))
        self.lbl_apikey.setText(self.tr("label_apikey"))
        self.lbl_gkey.setText(self.tr("label_gkey"))
        self.btn_save.setText(self.tr("btn_save"))
        self.lbl_aspect.setText(self.tr("label_aspect"))
        self.lbl_width.setText(self.tr("label_width"))
        self.lbl_height.setText(self.tr("label_height"))
        self.lbl_seed.setText(self.tr("label_seed"))
        self.seed_random.setText(self.tr("seed_random"))
        self.btn_dice.setText(self.tr("btn_dice"))
        self.lbl_batch.setText(self.tr("label_batch"))
        self.feather_cb.setText(self.tr("feather"))

    def _update_ref_label(self):
        if self.ref_b64:
            self.ref_lbl.setText(self.tr("ref_set", name=self.ref_name,
                                         w=self.ref_w, h=self.ref_h))
        else:
            self.ref_lbl.setText(self.tr("ref_none"))

    def _on_aspect_changed(self, idx):
        dims = ASPECT_PRESETS[idx][1]
        if dims:
            self.gen_w.setValue(dims[0])
            self.gen_h.setValue(dims[1])

    def _roll_seed(self):
        self.seed_random.setChecked(False)
        self.seed_val.setValue(random.randint(0, 2147483647))

    def cancel_req(self):
        if self.busy and self.worker:
            self.worker.cancel()
        self._batch = None          # verhindert weitere Varianten
        self.busy = False
        self._set_busy(False)
        self.status_lbl.setText(self.tr("status_cancelled"))

    # --- Settings -----------------------------------------------------------
    def save_k(self):
        kr = Krita.instance()
        kr.writeSetting("AIDiffusion", "fk_vPRO", self.f_key.text().strip())
        kr.writeSetting("AIDiffusion", "gkey", self.g_key.text().strip())
        self.status_lbl.setText(self.tr("saved"))

    def load_k(self):
        kr = Krita.instance()
        self.f_key.setText(kr.readSetting("AIDiffusion", "fk_vPRO", ""))
        self.g_key.setText(kr.readSetting("AIDiffusion", "gkey", ""))

    # --- Helpers ------------------------------------------------------------
    def _warn(self, key):
        msg = self.tr(key)
        self.status_lbl.setText(msg)
        QMessageBox.warning(None, "AI API Diffusion", msg)

    def choose_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            None, self.tr("dlg_choose_ref"), "", self.tr("dlg_filter"))
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            return self._warn("warn_ref_load")
        if max(img.width(), img.height()) > MAX_EDGE:
            img = img.scaled(MAX_EDGE, MAX_EDGE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_ARGB32)
        self.ref_b64 = self.qimage_to_b64(img)
        self.ref_name = path.replace("\\", "/").split("/")[-1]
        self.ref_w, self.ref_h = img.width(), img.height()
        self._update_ref_label()

    def clear_ref(self):
        self.ref_b64 = None
        self.ref_name = None
        self._update_ref_label()

    def _round32(self, v):
        return max(64, int(round(v / 32.0)) * 32)

    def _selection_crop(self, doc):
        sel = doc.selection()
        bx, by, bw, bh = sel.x(), sel.y(), sel.width(), sel.height()
        if bw <= 0 or bh <= 0:
            return None
        pad_x, pad_y = int(bw * CONTEXT_PAD), int(bh * CONTEXT_PAD)
        x0 = max(0, bx - pad_x); y0 = max(0, by - pad_y)
        x1 = min(doc.width(), bx + bw + pad_x); y1 = min(doc.height(), by + bh + pad_y)
        return x0, y0, x1 - x0, y1 - y0

    def _read_region(self, doc, x, y, w, h):
        img = doc.projection(x, y, w, h)
        return img.convertToFormat(QImage.Format_ARGB32)

    def _read_mask(self, doc, x, y, w, h):
        raw = doc.selection().pixelData(x, y, w, h)
        return QImage(raw, w, h, w, QImage.Format_Grayscale8).copy()

    def _read_alpha(self, doc, x, y, w, h):
        raw = doc.selection().pixelData(x, y, w, h)
        return QImage(raw, w, h, w, QImage.Format_Alpha8).copy()

    def _scaled_target(self, w, h):
        scale = min(1.0, float(MAX_EDGE) / max(w, h))
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
        if not doc:
            return self._warn("warn_no_doc")
        if self.busy:
            return self._warn("warn_running")

        sel = MODELS[self.model_cb.currentIndex()]
        provider, model_id = sel["provider"], sel["id"]
        prompt = self.prompt_ed.toPlainText().strip()

        # Passenden API-Key prüfen
        if provider == "google":
            if not self.g_key.text().strip():
                return self._warn("warn_no_gkey")
        elif not self.f_key.text().strip():
            return self._warn("warn_no_key")

        if mode == "generate":
            if not prompt:
                return self._warn("warn_no_prompt")
            if provider == "google":
                imgs = [self.ref_b64] if self.ref_b64 else []
                payload = {"prompt": prompt, "images": imgs}
            else:
                payload = {"prompt": prompt,
                           "width": self._round32(self.gen_w.value()),
                           "height": self._round32(self.gen_h.value()),
                           "output_format": "png"}
                if self.ref_b64:
                    payload["input_image"] = self.ref_b64
            self._begin(model_id, payload, None, "status_generating", provider)
            return

        crop = self._selection_crop(doc)
        # Kontext-Inpaint funktioniert auch ohne Auswahl -> ganzes Bild als Kontext.
        # Masken-Inpaint braucht zwingend eine Auswahl.
        full = crop is None
        if full:
            if mode == "fill":
                return self._warn("warn_no_selection")
            x, y, w, h = 0, 0, doc.width(), doc.height()
        else:
            x, y, w, h = crop
        tw, th = self._scaled_target(w, h)

        img = self._read_region(doc, x, y, w, h).scaled(
            tw, th, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        img_b64 = self.qimage_to_b64(img)
        crop_info = {"x": x, "y": y, "w": w, "h": h, "full": full}

        if mode == "edit":
            if not prompt:
                return self._warn("warn_no_prompt_edit")
            if provider == "google":
                imgs = [img_b64] + ([self.ref_b64] if self.ref_b64 else [])
                payload = {"prompt": prompt, "images": imgs}
            else:
                payload = {"prompt": prompt, "input_image": img_b64, "output_format": "png"}
                if self.ref_b64:
                    payload["input_image_2"] = self.ref_b64
            self._begin(model_id, payload, crop_info, "status_edit", provider)

        elif mode == "fill":
            if provider == "google":
                return self._warn("warn_fill_flux_only")
            mask = self._read_mask(doc, x, y, w, h).scaled(
                tw, th, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            mask_b64 = self.qimage_to_b64(mask)
            payload = {"prompt": prompt, "image": img_b64, "mask": mask_b64,
                       "output_format": "png"}
            self._begin(FILL_ENDPOINT, payload, crop_info, "status_fill", "bfl")

    def _begin(self, endpoint, payload, crop_info, status_key, provider="bfl"):
        """Startet einen Batch von N Varianten (sequenziell), jede mit eigenem Seed."""
        count = self.batch_val.value()
        if self.seed_random.isChecked():
            seeds = [random.randint(0, 2147483647) for _ in range(count)]
        else:
            base = self.seed_val.value()
            seeds = [(base + i) % 2147483648 for i in range(count)]
        self.seed_val.setValue(seeds[0])  # ersten Seed sichtbar machen

        group = None
        if count > 1:
            doc = Krita.instance().activeDocument()
            group = doc.createNode("AI Batch", "grouplayer")
            doc.rootNode().addChildNode(group, None)

        self._batch = {"endpoint": endpoint, "payload": payload, "crop_info": crop_info,
                       "status_key": status_key, "provider": provider,
                       "seeds": seeds, "total": count, "i": 0, "group": group}
        self.busy = True
        self._set_busy(True)
        self._launch_variant()

    def _launch_variant(self):
        b = self._batch
        payload = dict(b["payload"])
        payload["seed"] = b["seeds"][b["i"]]
        status = self.tr(b["status_key"])
        if b["total"] > 1:
            status += "  ({}/{})".format(b["i"] + 1, b["total"])
        self.status_lbl.setText(status)
        provider = b["provider"]
        api_key = self.g_key.text().strip() if provider == "google" else self.f_key.text().strip()
        self.worker = APIWorker(b["endpoint"], payload, api_key, b["crop_info"],
                                status_wait=self.tr("status_waiting"),
                                status_prefix=self.tr("status_prefix"),
                                provider=provider)
        self.worker.status.connect(self.status_lbl.setText)
        self.worker.finished.connect(self.handle_res)
        self.worker.error.connect(self.handle_err)
        # Beendete Threads verwerfen, laufende (z.B. abgebrochene) am Leben halten
        self._threads = [t for t in self._threads if t.isRunning()]
        self._threads.append(self.worker)
        self.worker.start()

    def _set_busy(self, busy):
        self.btn_gen.setEnabled(not busy)
        self.btn_edit.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        # Masken-Inpaint nur für FLUX (BFL); Nano Banana kann das nicht
        fill_ok = MODELS[self.model_cb.currentIndex()]["provider"] == "bfl"
        self.btn_fill.setEnabled(not busy and fill_ok)

    def _on_model_changed(self, *_):
        if self.busy:
            return
        self._set_busy(False)

    # --- Ergebnis -----------------------------------------------------------
    def handle_err(self, msg):
        self._batch = None
        self.busy = False
        self._set_busy(False)
        if len(msg) > 400:
            msg = msg[:400] + " ... [truncated]"
        self.status_lbl.setText(self.tr("err_prefix") + msg)
        QMessageBox.warning(None, "AI API Diffusion", self.tr("err_prefix") + msg)

    def handle_res(self, res):
        doc = Krita.instance().activeDocument()
        if not doc:
            self._batch = None
            self.busy = False
            self._set_busy(False)
            return

        b = self._batch
        parent = (b["group"] if b else None) or doc.rootNode()
        # Variantenname mit Seed (nur bei Batch > 1)
        if b and b["total"] > 1:
            suffix = " {} (seed {})".format(b["i"] + 1, b["seeds"][b["i"]])
        else:
            suffix = ""

        result = QImage()
        result.loadFromData(res["image_data"])
        result = result.convertToFormat(QImage.Format_ARGB32)
        crop = res["crop"]

        if crop is None:
            layer = doc.createNode("AI Generation" + suffix, "paintLayer")
            parent.addChildNode(layer, None)
            layer.setPixelData(result.bits().asstring(result.width() * result.height() * 4),
                               0, 0, result.width(), result.height())
            self.status_lbl.setText(self.tr("done_generate"))
        else:
            x, y, w, h = crop["x"], crop["y"], crop["w"], crop["h"]
            result = result.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            if crop.get("full"):
                # Voll-Bild-Edit (keine Auswahl): Ergebnis als komplette Ebene
                layer = doc.createNode("AI Edit" + suffix, "paintLayer")
                parent.addChildNode(layer, None)
                layer.setPixelData(result.bits().asstring(w * h * 4), x, y, w, h)
            else:
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
                layer = doc.createNode("AI Inpaint" + suffix, "paintLayer")
                parent.addChildNode(layer, None)
                layer.setPixelData(composite.bits().asstring(w * h * 4), x, y, w, h)
            self.status_lbl.setText(self.tr("done_inpaint"))

        doc.refreshProjection()
        self._batch_next()

    def _batch_next(self):
        b = self._batch
        if b is None:
            self.busy = False
            self._set_busy(False)
            return
        b["i"] += 1
        if b["i"] < b["total"]:
            self._launch_variant()          # nächste Variante (busy bleibt True)
            return
        n = b["total"]
        self._batch = None
        self.busy = False
        self._set_busy(False)
        if n > 1:
            self.status_lbl.setText(self.tr("status_batch_done", n=n))

    def canvasChanged(self, canvas):
        pass
