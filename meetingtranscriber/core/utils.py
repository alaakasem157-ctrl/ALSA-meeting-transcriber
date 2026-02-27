import re
from datetime import datetime
from pathlib import Path


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_stem(path: str) -> str:
    stem = Path(path).stem
    stem = re.sub(r"[^\w\-\.]+", "_", stem, flags=re.UNICODE)
    return stem[:80] if stem else "audio"


def fmt_ts(seconds: float) -> str:
    if seconds is None:
        seconds = 0.0
    ms = int(round(float(seconds) * 1000.0))
    s = ms // 1000
    ms = ms % 1000
    h = s // 3600
    s = s % 3600
    m = s // 60
    s = s % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
