from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict

import numpy as np
import sounddevice as sd
import soundfile as sf

from PySide6.QtCore import QObject, Signal, Slot, QElapsedTimer, QTimer

from meetingtranscriber.core.paths import ensure_dirs, temp_dir
from meetingtranscriber.core.utils import now_stamp


class RecordingService(QObject):
    log = Signal(str)
    state = Signal(str)
    level = Signal(float)
    elapsed = Signal(float)
    saved = Signal(str)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stream: Optional[sd.InputStream] = None
        self._frames: List[np.ndarray] = []
        self._paused: bool = False
        self._samplerate: int = 44100
        self._channels: int = 1

        self._timer = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._emit_elapsed)

    @Slot(dict)
    def start_recording(self, settings: Dict) -> None:
        try:
            ensure_dirs()

            if self._stream is not None:
                self.log.emit("Recording already running.")
                return

            self._frames = []
            self._paused = False
            self._samplerate = int(settings.get("samplerate", 44100))
            self._channels = int(settings.get("channels", 1))

            self._timer.restart()
            self._tick.start()

            def callback(indata, frames, time, status):
                if status:
                    self.log.emit(str(status))
                if self._paused:
                    self.level.emit(0.0)
                    return

                x = np.array(indata, dtype=np.float32, copy=True)
                self._frames.append(x)

                rms = float(np.sqrt(np.mean(np.square(x))) + 1e-12)
                lvl = min(1.0, rms * 4.0)
                self.level.emit(float(lvl))

            self._stream = sd.InputStream(
                samplerate=self._samplerate,
                channels=self._channels,
                dtype="float32",
                blocksize=0,
                callback=callback,
            )
            self._stream.start()

            self.state.emit("Recording")
            self.log.emit(f"Recording started: {self._samplerate} Hz, ch={self._channels}")

        except Exception as e:
            self.error.emit(str(e))
            self.state.emit("Error")
            self._cleanup()

    @Slot()
    def toggle_pause(self) -> None:
        if self._stream is None:
            return
        self._paused = not self._paused
        if self._paused:
            self.state.emit("Paused")
            self.log.emit("Paused")
        else:
            self.state.emit("Recording")
            self.log.emit("Resumed")

    @Slot()
    def stop_recording(self) -> None:
        try:
            if self._stream is None:
                return

            self._tick.stop()

            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

            audio = self._merge_frames()
            out = self._write_wav(audio)

            self.state.emit("Idle")
            self.saved.emit(str(out))
            self.log.emit(f"Recording saved: {out}")

        except Exception as e:
            self.error.emit(str(e))
            self.state.emit("Error")
        finally:
            self._cleanup()

    def _emit_elapsed(self) -> None:
        if not self._timer.isValid():
            self.elapsed.emit(0.0)
            return
        sec = self._timer.elapsed() / 1000.0
        self.elapsed.emit(float(sec))

    def _merge_frames(self) -> np.ndarray:
        if not self._frames:
            return np.zeros((0, self._channels), dtype=np.float32)
        return np.concatenate(self._frames, axis=0)

    def _write_wav(self, audio: np.ndarray) -> Path:
        out = temp_dir() / f"recording__{now_stamp()}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)

        if audio.size == 0:
            sf.write(str(out), np.zeros((1, self._channels), dtype=np.float32), self._samplerate, subtype="PCM_16")
            return out

        sf.write(str(out), audio, self._samplerate, subtype="PCM_16")
        return out

    def _cleanup(self) -> None:
        self._paused = False