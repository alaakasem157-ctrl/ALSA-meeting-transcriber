import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from meetingtranscriber.core.paths import assets_dir


@dataclass
class ReplaceRule:
    src: str
    dst: str


@dataclass
class RegexRule:
    pattern: str
    dst: str


class PostProcessor:
    """
    Fast, deterministic post-processing:
    - plain string replacements
    - regex replacements
    Loaded from assets/glossary.json
    """

    def __init__(self, glossary_path: Optional[Path] = None):
        self.glossary_path = glossary_path or (assets_dir() / "glossary.json")
        self._loaded = False
        self._plain: List[ReplaceRule] = []
        self._regex: List[RegexRule] = []
        self._regex_compiled: List[re.Pattern] = []

    def load(self) -> bool:
        if self._loaded:
            return True

        if not self.glossary_path.exists():
            # No glossary => no processing, but still "loaded"
            self._loaded = True
            return False

        data = json.loads(self.glossary_path.read_text(encoding="utf-8"))

        self._plain = []
        for r in data.get("replacements", []):
            src = str(r.get("from", "")).strip()
            dst = str(r.get("to", "")).strip()
            if src:
                self._plain.append(ReplaceRule(src=src, dst=dst))

        self._regex = []
        self._regex_compiled = []
        for rr in data.get("regex_replacements", []):
            pat = str(rr.get("pattern", "")).strip()
            dst = str(rr.get("to", ""))
            if pat:
                self._regex.append(RegexRule(pattern=pat, dst=dst))
                self._regex_compiled.append(re.compile(pat))

        self._loaded = True
        return True

    def apply(self, text: str) -> str:
        if not text:
            return ""

        # lazy-load
        if not self._loaded:
            self.load()

        out = text

        # plain replacements (ordered)
        for r in self._plain:
            out = out.replace(r.src, r.dst)

        # regex replacements (ordered)
        for rx, rule in zip(self._regex_compiled, self._regex):
            out = rx.sub(rule.dst, out)

        # light normalization
        out = out.strip()
        out = re.sub(r"\s{2,}", " ", out)
        return out

    def apply_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not segments:
            return segments
        for s in segments:
            s["text"] = self.apply(str(s.get("text", "")))
        return segments