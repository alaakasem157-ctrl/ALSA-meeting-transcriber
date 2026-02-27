import json
from dataclasses import dataclass, asdict
from typing import Any, Dict

from meetingtranscriber.core.paths import config_path


@dataclass
class AppConfig:
    model: str = "small"
    compute_type: str = "int8"
    cpu_threads: int = 6
    beam_size: int = 2
    language: str = "ar"
    vad: bool = True
    arabic_cleanup: bool = True
    temperature: float = 0.0

    use_ollama: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    summary_language: str = "ar"

    @classmethod
    def load(cls) -> "AppConfig":
        p = config_path()
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return cls()

        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def save(self):
        p = config_path()
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)