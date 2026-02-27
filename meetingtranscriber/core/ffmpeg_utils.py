import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from meetingtranscriber.core.paths import assets_dir


def ffmpeg_path() -> Path:
    p = assets_dir() / "ffmpeg" / "ffmpeg.exe"
    return p


def require_ffmpeg() -> Path:
    p = ffmpeg_path()
    if not p.exists():
        raise FileNotFoundError(f"ffmpeg.exe not found at: {p}")
    return p


def probe_duration_seconds(src: Path) -> float:
    exe = str(require_ffmpeg())
    p = subprocess.run(
        [exe, "-hide_banner", "-i", str(src)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    if not m:
        return 0.0
    h = int(m.group(1))
    mi = int(m.group(2))
    s = float(m.group(3))
    return h * 3600.0 + mi * 60.0 + s


def convert_to_wav16k_mono(
    src: Path,
    dst: Path,
    on_progress: Optional[Callable[[int], None]] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> None:
    exe = str(require_ffmpeg())
    total = max(0.01, probe_duration_seconds(src))
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        "-hide_banner",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-progress",
        "pipe:1",
        "-nostats",
        str(dst),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
        universal_newlines=True,
    )

    out_time_ms = 0
    if on_log:
        on_log("ffmpeg: converting to WAV 16k mono...")

    if proc.stdout:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k == "out_time_ms":
                    try:
                        out_time_ms = int(v)
                        pct = int(min(95, (out_time_ms / 1_000_000.0) / total * 100.0))
                        if on_progress:
                            on_progress(max(0, min(95, pct)))
                    except Exception:
                        pass
                elif k == "progress" and v == "end":
                    if on_progress:
                        on_progress(95)
            if on_log and (line.startswith("out_time") or line.startswith("progress=")):
                continue

    stderr_txt = ""
    if proc.stderr:
        stderr_txt = proc.stderr.read()

    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed (code {rc}). {stderr_txt[-1000:]}")
