import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def internal_dir() -> Path:
    if is_frozen() and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS).resolve()
    return base_dir()


def assets_dir() -> Path:
    return internal_dir() / "assets"


def outputs_dir() -> Path:
    return base_dir() / "outputs"


def temp_dir() -> Path:
    return outputs_dir() / "_tmp"


def config_path() -> Path:
    return base_dir() / "config.json"


def ensure_dirs():
    outputs_dir().mkdir(parents=True, exist_ok=True)
    temp_dir().mkdir(parents=True, exist_ok=True)