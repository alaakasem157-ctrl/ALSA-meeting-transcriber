import json
from pathlib import Path

import soundfile as sf
from PySide6.QtCore import QObject, Signal, Slot

from faster_whisper import WhisperModel

from meetingtranscriber.core.cleanup_ar import cleanup_ar_text
from meetingtranscriber.core.ffmpeg_utils import convert_to_wav16k_mono
from meetingtranscriber.core.paths import outputs_dir, temp_dir, ensure_dirs
from meetingtranscriber.core.utils import now_stamp, safe_stem

from meetingtranscriber.core.summarizer import build_smart_summary
from meetingtranscriber.core.docx_report import build_docx_report


class TranscriptionService(QObject):
    log = Signal(str)
    progress = Signal(int)
    status = Signal(str)
    result = Signal(dict)
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._busy = False
        self._model = None
        self._model_key = None

    @Slot(str, dict)
    def start_job(self, src_path: str, settings: dict):
        if self._busy:
            self.log.emit("Busy: job ignored.")
            return
        self._busy = True
        self.busy_changed.emit(True)
        try:
            ensure_dirs()
            src = Path(src_path).resolve()
            if not src.exists():
                raise FileNotFoundError(str(src))

            self.status.emit("Converting...")
            self.progress.emit(0)

            tmp_wav = temp_dir() / f"{safe_stem(src_path)}__{now_stamp()}_16k.wav"

            def on_p(pct: int):
                self.progress.emit(pct)

            def on_l(line: str):
                self.log.emit(line)

            convert_to_wav16k_mono(src, tmp_wav, on_progress=on_p, on_log=on_l)

            try:
                info = sf.info(str(tmp_wav))
                duration = float(info.frames) / float(info.samplerate)
            except Exception:
                duration = 0.0

            self.status.emit("Loading model...")
            self._ensure_model(settings)

            self.status.emit("Transcribing...")
            self.progress.emit(95)

            lang = settings.get("language", "ar")
            language = None if lang == "auto" else lang

            beam = int(settings.get("beam_size", 2))
            vad = bool(settings.get("vad", True))
            temperature = float(settings.get("temperature", 0.0))
            cleanup = bool(settings.get("arabic_cleanup", True))

            segments_out = []
            text_parts = []

            seg_iter, info = self._model.transcribe(
                str(tmp_wav),
                language=language,
                beam_size=beam,
                vad_filter=vad,
                temperature=temperature,
            )

            last_pct = 95
            for i, seg in enumerate(seg_iter):
                seg_dict = {
                    "id": i,
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": (seg.text or "").strip(),
                }
                segments_out.append(seg_dict)
                if seg_dict["text"]:
                    text_parts.append(seg_dict["text"])
                if duration > 0.0:
                    pct = int(min(99, max(95, (seg_dict["end"] / duration) * 100.0)))
                    if pct != last_pct:
                        last_pct = pct
                        self.progress.emit(pct)

            full_text = " ".join(text_parts).strip()

            if cleanup and (lang in ["ar", "auto"]):
                full_text = cleanup_ar_text(full_text)
                for s in segments_out:
                    s["text"] = cleanup_ar_text(s.get("text", ""))

            out_base = f"{safe_stem(src_path)}__{now_stamp()}"
            out_txt = outputs_dir() / f"{out_base}.txt"
            out_json = outputs_dir() / f"{out_base}.json"
            out_docx = outputs_dir() / f"{out_base}.docx"

            out_txt.write_text(full_text, encoding="utf-8")

            payload = {
                "created_at": now_stamp(),
                "source": {
                    "path": str(src),
                    "converted_wav": str(tmp_wav),
                    "duration_sec": duration,
                },
                "settings": dict(settings),
                "text": full_text,
                "segments": segments_out,
            }

            # =========================
            # Smart summary (topics/speakers/decisions/tasks)
            # =========================
            self.status.emit("Summarizing...")
            smart = build_smart_summary(full_text)

            payload["summary"] = {
                "bullets": smart.bullets,
                "topics": smart.topics,
                "speakers": smart.speakers,
                "decisions": smart.decisions,
                "tasks": smart.tasks,
                "numbers_dates": smart.numbers_dates,
                "keywords": smart.keywords,
            }

            # =========================
            # Word report
            # =========================
            self.status.emit("Building DOCX...")
            build_docx_report(
                out_path=out_docx,
                created_at=payload["created_at"],
                source_path=str(src),
                duration_sec=duration,
                full_text=full_text,
                summary=smart,
                app_name="ALSA",
            )

            # Save JSON
            out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            payload["saved_txt"] = str(out_txt)
            payload["saved_json"] = str(out_json)
            payload["saved_docx"] = str(out_docx)

            self.progress.emit(100)
            self.status.emit("Done")
            self.result.emit(payload)

        except Exception as e:
            self.error.emit(str(e))
            self.status.emit("Error")
        finally:
            self._busy = False
            self.busy_changed.emit(False)

    def _ensure_model(self, settings: dict):
        model_name = settings.get("model", "small")
        compute_type = settings.get("compute_type", "int8")
        cpu_threads = int(settings.get("cpu_threads", 4))
        key = (model_name, compute_type, cpu_threads)
        if self._model is not None and self._model_key == key:
            return
        self._model = WhisperModel(
            model_name,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
        self._model_key = key
        self.log.emit(f"Model ready: {model_name} | {compute_type} | threads={cpu_threads}")