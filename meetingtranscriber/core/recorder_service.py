import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from meetingtranscriber.core.paths import ensure_dirs, temp_dir
from meetingtranscriber.core.utils import now_stamp


class RecorderService(QObject):
    log = Signal(str)
    error = Signal(str)

    state = Signal(str)
    elapsed = Signal(float)
    level = Signal(float)
    saved = Signal(str)

    def __init__(self):
        super().__init__()
        self._stream: Optional[sd.InputStream] = None
        self._timer: Optional[QTimer] = None

        self._paused = False
        self._start_t = 0.0
        self._pause_t = 0.0
        self._paused_total = 0.0

        self._sr = 44100
        self._ch = 1

        self._frames: list[np.ndarray] = []
        self._last_level = 0.0

    @Slot(dict)
    def start_recording(self, cfg: dict):
        try:
            ensure_dirs()
            self._sr = int(cfg.get("samplerate", 44100))
            self._ch = int(cfg.get("channels", 1))

            self._frames = []
            self._paused = False
            self._start_t = time.monotonic()
            self._paused_total = 0.0
            self._pause_t = 0.0
            self._last_level = 0.0

            def callback(indata, frames, time_info, status):
                if status:
                    pass
                x = np.asarray(indata, dtype=np.float32)
                rms = float(np.sqrt(np.mean(x * x) + 1e-12))
                self._last_level = max(0.0, min(1.0, rms * 6.0))
                if not self._paused:
                    self._frames.append(x.copy())

            self._stream = sd.InputStream(
                samplerate=self._sr,
                channels=self._ch,
                dtype="float32",
                callback=callback,
            )
            self._stream.start()

            self._timer = QTimer()
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

            self.state.emit("Recording")
            self.log.emit("Recording started.")

        except Exception as e:
            self.error.emit(str(e))
            self.state.emit("Error")

    @Slot()
    def toggle_pause(self):
        if not self._stream:
            return
        self._paused = not self._paused
        if self._paused:
            self._pause_t = time.monotonic()
            self.state.emit("Paused")
        else:
            self._paused_total += (time.monotonic() - self._pause_t)
            self._pause_t = 0.0
            self.state.emit("Recording")

    @Slot()
    def stop_recording(self):
        try:
            if self._timer:
                self._timer.stop()
                self._timer = None

            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            self.state.emit("Idle")
            self.level.emit(0.0)
            self.elapsed.emit(0.0)
            self.log.emit("Recording stopped.")

        except Exception as e:
            self.error.emit(str(e))
            self.state.emit("Error")

    @Slot()
    def stop_and_save(self):
        try:
            self.stop_recording()

            if not self._frames:
                raise RuntimeError("No audio recorded.")

            audio = np.concatenate(self._frames, axis=0)
            out = temp_dir() / f"recording_{now_stamp()}.wav"
            sf.write(str(out), audio, self._sr)
            self.saved.emit(str(out))
            self.log.emit(f"Recording saved: {out}")

        except Exception as e:
            self.error.emit(str(e))
            self.state.emit("Error")

    def _tick(self):
        if not self._start_t:
            return
        now = time.monotonic()
        paused_total = self._paused_total
        if self._paused and self._pause_t:
            paused_total += (now - self._pause_t)
        sec = max(0.0, now - self._start_t - paused_total)
        self.elapsed.emit(sec)
        self.level.emit(self._last_level)


RecordingService = RecorderService