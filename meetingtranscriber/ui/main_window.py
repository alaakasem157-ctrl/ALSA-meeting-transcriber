import json
from collections import deque
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QPlainTextEdit,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QMessageBox,
    QSizePolicy,
)

from meetingtranscriber.core.paths import ensure_dirs, outputs_dir, assets_dir, config_path
from meetingtranscriber.core.transcription_service import TranscriptionService
from meetingtranscriber.core.recording_service import RecordingService
from meetingtranscriber.core.summarization_service import OllamaSummarizer, OllamaConfig
from meetingtranscriber.core.word_exporter import export_meeting_docx


DEFAULT_SETTINGS: Dict[str, Any] = {
    "model": "small",
    "compute_type": "int8",
    "cpu_threads": 6,
    "beam_size": 3,
    "language": "ar",
    "vad": True,
    "temperature": 0.0,
    "arabic_cleanup": True,
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "gemma3:4b",
    "summary_language": "ar",
}


def _load_settings() -> Dict[str, Any]:
    p = config_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out = dict(DEFAULT_SETTINGS)
                out.update(data)
                return out
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(s: Dict[str, Any]) -> None:
    p = config_path()
    p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


class WatermarkWidget(QWidget):
    def __init__(self, watermark_png: Path, opacity: float = 0.08, scale: float = 0.28, parent=None):
        super().__init__(parent)
        self._opacity = float(opacity)
        self._scale = float(scale)
        self._pix = QPixmap(str(watermark_png)) if watermark_png.exists() else QPixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pix.isNull():
            return
        w = self.width()
        h = self.height()
        if w <= 10 or h <= 10:
            return
        target_w = int(w * self._scale)
        if target_w < 180:
            target_w = 180
        pm = self._pix.scaledToWidth(target_w, Qt.SmoothTransformation)
        x = (w - pm.width()) // 2
        y = (h - pm.height()) // 2
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._opacity)
        p.drawPixmap(x, y, pm)
        p.end()


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._vals = deque(maxlen=240)
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push_level(self, level: float):
        v = float(level)
        v = max(0.0, min(1.0, v * 6.0))
        self._vals.append(v)
        self.update()

    def clear(self):
        self._vals.clear()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._vals:
            return
        w = self.width()
        h = self.height()
        mid = h // 2

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        pen = QPen()
        pen.setWidth(2)
        pen.setColor(Qt.white)
        p.setPen(pen)

        step = w / max(1, len(self._vals) - 1)
        x = 0.0
        points = []
        for v in self._vals:
            y = mid - (v * (h * 0.42))
            points.append((x, y))
            x += step

        for i in range(1, len(points)):
            x1, y1 = points[i - 1]
            x2, y2 = points[i]
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
            p.drawLine(int(x1), int(2 * mid - y1), int(x2), int(2 * mid - y2))

        p.end()


class MainWindow(QMainWindow):
    request_transcribe = Signal(str, dict)
    request_record_start = Signal(dict)
    request_record_toggle_pause = Signal()
    request_record_stop = Signal()

    def __init__(self):
        super().__init__()
        ensure_dirs()
        self.settings = _load_settings()
        self._last_source_path: Optional[str] = None

        self.setWindowTitle("alsa")
        self.resize(1200, 780)
        self.setLayoutDirection(Qt.RightToLeft)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)

        self._build_upload_tab()
        self._build_record_tab()
        self._build_settings_tab()
        self._build_output_tab()

        self._wire_services()
        self._apply_settings_to_ui()

    def _build_header(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(12)

        self.lbl_header_left = QLabel()
        header_img = assets_dir() / "header-ALSA.png"
        if header_img.exists():
            pm = QPixmap(str(header_img))
            self.lbl_header_left.setPixmap(pm.scaledToHeight(46, Qt.SmoothTransformation))
        lay.addWidget(self.lbl_header_left, 0, Qt.AlignLeft | Qt.AlignVCenter)

        lay.addStretch(1)

        self.lbl_header_status = QLabel("جاهز")
        self.lbl_header_status.setObjectName("HeaderStatus")
        lay.addWidget(self.lbl_header_status, 0, Qt.AlignRight | Qt.AlignVCenter)

        return w

    def _build_upload_tab(self):
        wm = assets_dir() / "logo-ALSA.png"
        self.tab_upload = WatermarkWidget(wm, opacity=0.10, scale=0.32)
        layout = QVBoxLayout(self.tab_upload)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        row = QHBoxLayout()
        self.upload_path = QLineEdit()
        self.upload_path.setPlaceholderText("اختر ملف الصوت...")
        self.upload_path.setAlignment(Qt.AlignRight)
        self.btn_browse = QPushButton("استعراض")
        self.btn_transcribe_file = QPushButton("تفريغ")
        row.addWidget(self.upload_path, 1)
        row.addWidget(self.btn_browse)
        row.addWidget(self.btn_transcribe_file)
        layout.addLayout(row)

        self.lbl_upload_hint = QLabel("Supported: wav/mp3/m4a/ogg/webm/flac/aac/wma/mp4 ...")
        layout.addWidget(self.lbl_upload_hint)

        layout.addStretch(1)

        self.tabs.addTab(self.tab_upload, "رفع ملف")

        self.btn_browse.clicked.connect(self._browse_audio)
        self.btn_transcribe_file.clicked.connect(self._transcribe_selected_file)

    def _build_record_tab(self):
        wm = assets_dir() / "logo-ALSA.png"
        self.tab_record = WatermarkWidget(wm, opacity=0.10, scale=0.26)
        layout = QVBoxLayout(self.tab_record)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.lbl_rec_time = QLabel("00:00.0")
        self.lbl_rec_time.setObjectName("RecTime")
        top.addWidget(self.lbl_rec_time, 0, Qt.AlignLeft)
        top.addStretch(1)
        layout.addLayout(top)

        self.wave = WaveformWidget()
        layout.addWidget(self.wave)

        btns = QHBoxLayout()
        self.btn_rec_start = QPushButton("بدء")
        self.btn_rec_pause = QPushButton("إيقاف مؤقت")
        self.btn_rec_stop = QPushButton("إنهاء")
        self.btn_rec_pause.setEnabled(False)
        self.btn_rec_stop.setEnabled(False)
        btns.addWidget(self.btn_rec_start)
        btns.addWidget(self.btn_rec_pause)
        btns.addWidget(self.btn_rec_stop)
        btns.addStretch(1)
        layout.addLayout(btns)

        self.lbl_record_hint = QLabel("سجّل من المايك ثم اضغط (إنهاء) وسيتم التفريغ تلقائياً.")
        layout.addWidget(self.lbl_record_hint)

        layout.addStretch(1)
        self.tabs.addTab(self.tab_record, "تسجيل")

        self.btn_rec_start.clicked.connect(self._start_recording)
        self.btn_rec_pause.clicked.connect(self._toggle_pause)
        self.btn_rec_stop.clicked.connect(self._stop_recording)

    def _build_settings_tab(self):
        wm = assets_dir() / "logo-ALSA.png"
        self.tab_settings = WatermarkWidget(wm, opacity=0.06, scale=0.22)
        layout = QVBoxLayout(self.tab_settings)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.cmb_model = QComboBox()
        self.cmb_model.addItems(["tiny", "base", "small", "medium", "large-v3"])

        self.cmb_compute = QComboBox()
        self.cmb_compute.addItems(["int8", "int8_float16", "float16"])

        self.spn_threads = QSpinBox()
        self.spn_threads.setRange(1, 64)

        self.spn_beam = QSpinBox()
        self.spn_beam.setRange(1, 10)

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["ar", "auto", "en"])

        self.chk_vad = QCheckBox("تفعيل VAD (مستحسن)")
        self.chk_cleanup = QCheckBox("تنظيف عربي")

        self.dsp_temp = QDoubleSpinBox()
        self.dsp_temp.setRange(0.0, 2.0)
        self.dsp_temp.setSingleStep(0.1)
        self.dsp_temp.setDecimals(2)

        form.addRow("Model", self.cmb_model)
        form.addRow("Compute", self.cmb_compute)
        form.addRow("CPU Threads", self.spn_threads)
        form.addRow("Beam Size", self.spn_beam)
        form.addRow("Language", self.cmb_lang)
        form.addRow("Temperature", self.dsp_temp)
        form.addRow(self.chk_vad)
        form.addRow(self.chk_cleanup)

        layout.addLayout(form)

        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight)

        self.ed_ollama_url = QLineEdit()
        self.ed_ollama_model = QLineEdit()
        self.cmb_sum_lang = QComboBox()
        self.cmb_sum_lang.addItems(["ar", "en"])

        form2.addRow("Ollama URL", self.ed_ollama_url)
        form2.addRow("Ollama Model", self.ed_ollama_model)
        form2.addRow("Summary Language", self.cmb_sum_lang)

        layout.addSpacing(10)
        layout.addLayout(form2)

        btn_row = QHBoxLayout()
        self.btn_save_settings = QPushButton("حفظ الإعدادات")
        self.btn_open_outputs = QPushButton("فتح مجلد outputs")
        btn_row.addWidget(self.btn_save_settings)
        btn_row.addWidget(self.btn_open_outputs)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addStretch(1)
        self.tabs.addTab(self.tab_settings, "إعدادات")

        self.btn_save_settings.clicked.connect(self._save_settings_clicked)
        self.btn_open_outputs.clicked.connect(self._open_outputs_folder)

    def _build_output_tab(self):
        wm = assets_dir() / "logo-ALSA.png"
        self.tab_output = WatermarkWidget(wm, opacity=0.06, scale=0.24)
        layout = QVBoxLayout(self.tab_output)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.btn_summarize = QPushButton("تلخيص ذكي")
        self.btn_export_word = QPushButton("تصدير Word")
        top.addWidget(self.btn_summarize)
        top.addWidget(self.btn_export_word)
        top.addStretch(1)
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("جاهز")
        layout.addWidget(self.lbl_status)

        self.txt_transcript = QPlainTextEdit()
        self.txt_transcript.setPlaceholderText("النص المفرّغ...")
        self.txt_transcript.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.txt_transcript, 2)

        self.txt_summary = QPlainTextEdit()
        self.txt_summary.setPlaceholderText("الملخّص...")
        self.txt_summary.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.txt_summary, 1)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        layout.addWidget(self.txt_log, 1)

        self.tabs.addTab(self.tab_output, "النتيجة")

        self.btn_summarize.clicked.connect(self._summarize_clicked)
        self.btn_export_word.clicked.connect(self._export_word_clicked)

    def _wire_services(self):
        self.trans_thread = QThread(self)
        self.trans_service = TranscriptionService()
        self.trans_service.moveToThread(self.trans_thread)
        self.trans_thread.start()

        self.rec_thread = QThread(self)
        self.rec_service = RecordingService()
        self.rec_service.moveToThread(self.rec_thread)
        self.rec_thread.start()

        self.request_transcribe.connect(self.trans_service.start_job, Qt.QueuedConnection)
        self.request_record_start.connect(self.rec_service.start_recording, Qt.QueuedConnection)
        self.request_record_toggle_pause.connect(self.rec_service.toggle_pause, Qt.QueuedConnection)
        self.request_record_stop.connect(self.rec_service.stop_recording, Qt.QueuedConnection)

        self.trans_service.log.connect(self._log)
        self.trans_service.progress.connect(self.progress.setValue)
        self.trans_service.status.connect(self._set_status)
        self.trans_service.result.connect(self._on_transcription_result)
        self.trans_service.error.connect(self._on_error)
        self.trans_service.busy_changed.connect(self._set_busy)

        self.rec_service.log.connect(self._log)
        self.rec_service.state.connect(self._on_rec_state)
        self.rec_service.saved.connect(self._on_record_saved)
        self.rec_service.level.connect(self._on_mic_level)
        self.rec_service.elapsed.connect(self._on_rec_elapsed)
        self.rec_service.error.connect(self._on_error)

    def _apply_settings_to_ui(self):
        s = self.settings
        self.cmb_model.setCurrentText(str(s.get("model", DEFAULT_SETTINGS["model"])))
        self.cmb_compute.setCurrentText(str(s.get("compute_type", DEFAULT_SETTINGS["compute_type"])))
        self.spn_threads.setValue(int(s.get("cpu_threads", DEFAULT_SETTINGS["cpu_threads"])))
        self.spn_beam.setValue(int(s.get("beam_size", DEFAULT_SETTINGS["beam_size"])))
        self.cmb_lang.setCurrentText(str(s.get("language", DEFAULT_SETTINGS["language"])))
        self.chk_vad.setChecked(bool(s.get("vad", True)))
        self.chk_cleanup.setChecked(bool(s.get("arabic_cleanup", True)))
        self.dsp_temp.setValue(float(s.get("temperature", 0.0)))

        self.ed_ollama_url.setText(str(s.get("ollama_url", DEFAULT_SETTINGS["ollama_url"])))
        self.ed_ollama_model.setText(str(s.get("ollama_model", DEFAULT_SETTINGS["ollama_model"])))
        self.cmb_sum_lang.setCurrentText(str(s.get("summary_language", DEFAULT_SETTINGS["summary_language"])))

    def _gather_settings_from_ui(self) -> Dict[str, Any]:
        s = dict(self.settings)
        s["model"] = self.cmb_model.currentText()
        s["compute_type"] = self.cmb_compute.currentText()
        s["cpu_threads"] = int(self.spn_threads.value())
        s["beam_size"] = int(self.spn_beam.value())
        s["language"] = self.cmb_lang.currentText()
        s["vad"] = bool(self.chk_vad.isChecked())
        s["arabic_cleanup"] = bool(self.chk_cleanup.isChecked())
        s["temperature"] = float(self.dsp_temp.value())
        s["ollama_url"] = self.ed_ollama_url.text().strip()
        s["ollama_model"] = self.ed_ollama_model.text().strip()
        s["summary_language"] = self.cmb_sum_lang.currentText()
        return s

    def _browse_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio",
            str(Path.home()),
            "Audio Files (*.wav *.mp3 *.m4a *.ogg *.webm *.flac *.aac *.wma *.mp4);;All Files (*)"
        )
        if path:
            self.upload_path.setText(path)

    def _transcribe_selected_file(self):
        src = self.upload_path.text().strip()
        if not src or not Path(src).exists():
            QMessageBox.warning(self, "alsa", "اختر ملف صوت صحيح أولاً.")
            return
        self._last_source_path = src
        self.tabs.setCurrentWidget(self.tab_output)
        self.progress.setValue(0)
        self.txt_log.clear()
        self._set_status("Queued...")
        settings = self._gather_settings_from_ui()
        self.request_transcribe.emit(src, settings)

    def _start_recording(self):
        self.wave.clear()
        self.lbl_rec_time.setText("00:00.0")
        self._last_source_path = None
        self.request_record_start.emit({"samplerate": 44100, "channels": 1})
        self.btn_rec_start.setEnabled(False)
        self.btn_rec_pause.setEnabled(True)
        self.btn_rec_stop.setEnabled(True)

    def _toggle_pause(self):
        self.request_record_toggle_pause.emit()

    def _stop_recording(self):
        self.request_record_stop.emit()
        self.btn_rec_start.setEnabled(True)
        self.btn_rec_pause.setEnabled(False)
        self.btn_rec_stop.setEnabled(False)

    def _on_record_saved(self, path: str):
        self._log(f"Recording saved: {path}")
        self._last_source_path = path
        self.tabs.setCurrentWidget(self.tab_output)
        self.progress.setValue(0)
        self._set_status("Queued...")
        settings = self._gather_settings_from_ui()
        self.request_transcribe.emit(path, settings)

    def _on_mic_level(self, level: float):
        self.wave.push_level(level)

    def _on_rec_elapsed(self, sec: float):
        m = int(sec // 60)
        s = sec - (m * 60)
        self.lbl_rec_time.setText(f"{m:02d}:{s:04.1f}")

    def _on_rec_state(self, s: str):
        if s == "Paused":
            self._set_status("إيقاف مؤقت")
        elif s == "Recording":
            self._set_status("تسجيل...")
        elif s == "Idle":
            self._set_status("جاهز")

    def _on_transcription_result(self, payload: dict):
        self.progress.setValue(100)
        self._set_status("تم")
        text = (payload.get("text") or "").strip()
        self.txt_transcript.setPlainText(text)
        self._log(f"Saved: {payload.get('saved_txt')}")
        self._log(f"Saved: {payload.get('saved_json')}")

    def _save_settings_clicked(self):
        self.settings = self._gather_settings_from_ui()
        _save_settings(self.settings)
        self._set_status("تم حفظ الإعدادات")
        self._log("Settings saved.")

    def _open_outputs_folder(self):
        out = outputs_dir()
        try:
            import os
            os.startfile(str(out))
        except Exception as e:
            QMessageBox.warning(self, "alsa", str(e))

    def _summarize_clicked(self):
        text = self.txt_transcript.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "alsa", "ما في نص للتلخيص.")
            return

        s = self._gather_settings_from_ui()
        base = s.get("ollama_url", DEFAULT_SETTINGS["ollama_url"])
        model = s.get("ollama_model", DEFAULT_SETTINGS["ollama_model"])
        lang = s.get("summary_language", "ar")

        try:
            self._set_status("جاري التلخيص...")
            cfg = OllamaConfig(base_url=base, model=model)
            summ = OllamaSummarizer(cfg).summarize_meeting(text, language=lang)
            self.txt_summary.setPlainText(summ)
            self._set_status("تم")
        except Exception as e:
            QMessageBox.critical(self, "alsa", str(e))
            self._set_status("Error")

    def _export_word_clicked(self):
        transcript = self.txt_transcript.toPlainText().strip()
        if not transcript:
            QMessageBox.warning(self, "alsa", "ما في نص للتصدير.")
            return
        summary = self.txt_summary.toPlainText().strip()
        meta = {}
        if self._last_source_path:
            meta["المصدر"] = self._last_source_path
        try:
            out = export_meeting_docx(
                transcript_text=transcript,
                summary_text=summary,
                meta=meta,
                header_logo_path=str(assets_dir() / "header-ALSA.png"),
            )
            self._log(f"Word saved: {out}")
            QMessageBox.information(self, "alsa", f"تم إنشاء ملف Word:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "alsa", str(e))

    def _set_busy(self, busy: bool):
        self.btn_transcribe_file.setEnabled(not busy)
        self.btn_browse.setEnabled(not busy)
        self.btn_summarize.setEnabled(not busy)
        self.btn_export_word.setEnabled(not busy)

    def _set_status(self, s: str):
        self.lbl_status.setText(s)
        self.lbl_header_status.setText(s)

    def _log(self, line: str):
        self.txt_log.appendPlainText(line)

    def _on_error(self, msg: str):
        self._set_status("Error")
        self._log(f"ERROR: {msg}")