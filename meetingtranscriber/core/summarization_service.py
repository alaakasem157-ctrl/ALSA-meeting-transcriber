from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "gemma3:4b"
    timeout_sec: int = 180


@dataclass
class SummaryResult:
    summary: str
    topics: List[str]
    decisions: List[str]
    tasks: List[str]
    speakers: List[str]


class OllamaSummarizer:
    def __init__(
        self,
        base_url: Optional[Any] = None,
        model: Optional[str] = None,
        timeout_sec: int = 180,
        config: Optional[OllamaConfig] = None,
        **kwargs: Any,
    ):
        # allow: OllamaSummarizer(OllamaConfig(...))
        if config is None and base_url is not None and hasattr(base_url, "base_url") and hasattr(base_url, "model"):
            config = base_url  # type: ignore
            base_url = None

        if config is not None:
            base_url = config.base_url
            model = config.model
            timeout_sec = int(config.timeout_sec)

        if base_url is None:
            base_url = kwargs.get("base_url") or kwargs.get("url") or "http://127.0.0.1:11434"

        # in case object was passed
        if not isinstance(base_url, str) and hasattr(base_url, "base_url"):
            base_url = getattr(base_url, "base_url")

        if model is None:
            model = kwargs.get("model") or "gemma3:4b"

        base_url = str(base_url).strip().rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]

        self.base_url = base_url
        self.model = str(model)
        self.timeout_sec = int(timeout_sec)

        # IMPORTANT: ignore OS proxy env vars (fixes ProxyError on localhost)
        self._session = requests.Session()
        self._session.trust_env = False  # <== key line

    # ---------- Public API ----------

    def summarize_meeting(self, transcript_text: str, title: str = "اجتماع", language: str = "ar") -> str:
        res = self.summarize_structured(transcript_text, title=title, language=language)
        return self.format_summary(res, language=language)

    def summarize_structured(self, transcript_text: str, title: str = "اجتماع", language: str = "ar") -> SummaryResult:
        text = (transcript_text or "").strip()
        if not text:
            return SummaryResult(summary="", topics=[], decisions=[], tasks=[], speakers=[])

        max_chars = 12000
        if len(text) > max_chars:
            chunks = self._chunk_text(text, chunk_size=6000, max_chunks=6)
            chunk_summaries: List[str] = []
            for idx, ch in enumerate(chunks, start=1):
                chunk_summaries.append(self._summarize_chunk(ch, language=language, title=f"{title} (جزء {idx})"))
            merged = "\n\n".join(chunk_summaries)
            return self._summarize_structured_once(merged, language=language, title=title)

        return self._summarize_structured_once(text, language=language, title=title)

    def format_summary(self, res: SummaryResult, language: str = "ar") -> str:
        if language.lower().startswith("ar"):
            def sec(name: str, items: List[str]) -> str:
                if not items:
                    return f"{name}:\n- لا يوجد\n"
                return f"{name}:\n" + "\n".join([f"- {x}" for x in items]) + "\n"

            out = []
            out.append("ملخص تنفيذي:\n" + (res.summary.strip() or "لا يوجد") + "\n")
            out.append(sec("محاور الاجتماع", res.topics))
            out.append(sec("القرارات", res.decisions))
            out.append(sec("المهام", res.tasks))
            out.append(sec("المتحدثون", res.speakers))
            return "\n".join(out).strip()

        # English format
        def sec_en(name: str, items: List[str]) -> str:
            if not items:
                return f"{name}:\n- None\n"
            return f"{name}:\n" + "\n".join([f"- {x}" for x in items]) + "\n"

        out = []
        out.append("Executive Summary:\n" + (res.summary.strip() or "None") + "\n")
        out.append(sec_en("Topics", res.topics))
        out.append(sec_en("Decisions", res.decisions))
        out.append(sec_en("Action Items", res.tasks))
        out.append(sec_en("Speakers", res.speakers))
        return "\n".join(out).strip()

    # ---------- Internals ----------

    def _chunk_text(self, text: str, chunk_size: int, max_chunks: int) -> List[str]:
        parts: List[str] = []
        buf: List[str] = []
        size = 0

        def flush():
            nonlocal buf, size
            if buf:
                parts.append(" ".join(buf).strip())
                buf = []
                size = 0

        for token in re.split(r"(\n+|[.!؟\?])", text):
            if not token:
                continue
            t = token.strip()
            if not t:
                continue
            if size + len(t) + 1 > chunk_size:
                flush()
                if len(parts) >= max_chunks:
                    break
            buf.append(t)
            size += len(t) + 1

        if len(parts) < max_chunks:
            flush()

        return [p for p in parts if p]

    def _summarize_chunk(self, text: str, language: str, title: str) -> str:
        prompt = self._prompt_structured(text, language=language, title=title, compact=True)
        out = self._ollama_call(prompt)
        parsed = self._parse_json(out)
        if parsed and (parsed.get("summary") or "").strip():
            return str(parsed.get("summary")).strip()
        return self._fallback_summary(text)

    def _summarize_structured_once(self, text: str, language: str, title: str) -> SummaryResult:
        prompt = self._prompt_structured(text, language=language, title=title, compact=False)
        out = self._ollama_call(prompt)
        parsed = self._parse_json(out)

        if not parsed:
            return SummaryResult(summary=self._fallback_summary(text), topics=[], decisions=[], tasks=[], speakers=[])

        return SummaryResult(
            summary=str(parsed.get("summary") or "").strip(),
            topics=self._as_list(parsed.get("topics")),
            decisions=self._as_list(parsed.get("decisions")),
            tasks=self._as_list(parsed.get("tasks")),
            speakers=self._as_list(parsed.get("speakers")),
        )

    def _prompt_structured(self, text: str, language: str, title: str, compact: bool) -> str:
        if language.lower().startswith("ar"):
            style = "اكتب بالعربية الفصحى وبشكل رسمي."
            extra = "اجعل الملخص قصيراً." if compact else "اجعل الملخص واضحاً ومفصلاً."
        else:
            style = "Write in English, formal and clear."
            extra = "Keep it short." if compact else "Make it clear and detailed."

        return f"""
{style}
{extra}

Return ONLY valid JSON (no markdown).
Keys:
- summary: string
- topics: array of strings
- decisions: array of strings
- tasks: array of strings (include assignee if known)
- speakers: array of strings (if detectable, else empty)

Title: {title}

Transcript:
{text}
""".strip()

    def _ollama_call(self, prompt: str) -> str:
        payload_generate = {"model": self.model, "prompt": prompt, "stream": False}
        payload_chat = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "You are an expert meeting summarizer. Return only JSON."},
                {"role": "user", "content": prompt},
            ],
        }

        # try /api/chat then fallback /api/generate
        try:
            r = self._session.post(f"{self.base_url}/api/chat", json=payload_chat, timeout=self.timeout_sec)
            if r.status_code == 404:
                raise requests.HTTPError("chat_not_found", response=r)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message") or {}
            return str(msg.get("content") or "")
        except Exception:
            r2 = self._session.post(f"{self.base_url}/api/generate", json=payload_generate, timeout=self.timeout_sec)
            r2.raise_for_status()
            data2 = r2.json()
            return str(data2.get("response") or "")

    def _parse_json(self, s: str) -> Optional[Dict[str, Any]]:
        if not s:
            return None
        s = s.strip()
        try:
            return json.loads(s)
        except Exception:
            pass

        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            blob = m.group(0).strip()
            try:
                return json.loads(blob)
            except Exception:
                pass
        return None

    def _as_list(self, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            lines = [ln.strip(" -•\t") for ln in v.splitlines()]
            return [ln for ln in lines if ln]
        return [str(v).strip()] if str(v).strip() else []

    def _fallback_summary(self, text: str) -> str:
        sents = re.split(r"(?<=[.!؟\?])\s+", text.strip())
        sents = [s.strip() for s in sents if s.strip()]
        return " ".join(sents[:5])[:1200]