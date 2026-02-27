# meetingtranscriber/core/summarizer.py
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple


AR_STOP = {
    "من", "إلى", "على", "عن", "في", "مع", "هذا", "هذه", "ذلك", "تلك", "هناك", "هنا",
    "هو", "هي", "هم", "هن", "أنا", "نحن", "انت", "أنت", "أنتِ", "أنتم", "أنتن",
    "كان", "كانت", "يكون", "تكون", "تم", "قد", "ثم", "لكن", "لأن", "إذا", "إن",
    "و", "أو", "كما", "أي", "أيضاً", "ايضا", "حتى", "كل", "بعض", "غير", "بدون",
    "بعد", "قبل", "بين", "ضمن", "حول", "عند", "مثل", "مثلاً", "مثلا",
}
EN_STOP = {
    "the", "a", "an", "to", "of", "in", "on", "at", "for", "with", "and", "or", "is", "are",
    "was", "were", "be", "been", "it", "this", "that", "these", "those", "as", "by", "from",
}

DECISION_KWS = [
    "تم الاتفاق", "اتفقنا", "تم اعتماد", "قررنا", "تم القرار", "قرار", "اعتماد",
    "approve", "approved", "we decided", "decision", "agreed",
]
TASK_KWS = [
    "مطلوب", "لازم", "يرجى", "يرجى من", "تكليف", "مسؤول", "على", "رح", "سوف", "سنقوم",
    "todo", "to do", "action", "task", "need to", "please",
]
TOPIC_HINTS = {
    "المقدمة والسياق": ["افتتاح", "مقدمة", "سياق", "هدف", "الغرض", "introduction", "context", "goal", "purpose"],
    "نقاط تقنية": ["نظام", "خادم", "سيرفر", "قاعدة", "بيانات", "API", "نموذج", "model", "pipeline", "deployment"],
    "العمل والخطة": ["خطة", "جدول", "deadline", "موعد", "مرحلة", "تسليم", "next", "plan", "timeline"],
    "مشاكل ومخاطر": ["مشكلة", "خطأ", "فشل", "خطر", "risk", "issue", "error", "blocked"],
    "النتائج والتوصيات": ["نتيجة", "استنتاج", "توصية", "recommendation", "outcome", "result"],
}

SPEAKER_PATTERNS = [
    r"^\s*(Speaker\s*\d+)\s*[:\-]\s*(.+)$",
    r"^\s*(المتحدث\s*\d+)\s*[:\-]\s*(.+)$",
    r"^\s*([A-Za-z][A-Za-z0-9_\- ]{1,25})\s*[:\-]\s*(.+)$",
    r"^\s*([اأإآء-ي][اأإآء-ي0-9_\- ]{1,25})\s*[:\-]\s*(.+)$",
]


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    # تقسيم عربي/إنكليزي بسيط
    parts = re.split(r"[\.!\?؟\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    # كلمات عربية/لاتينية
    tokens = re.findall(r"[A-Za-z]+|[اأإآء-ي]+", text)
    clean = []
    for t in tokens:
        if len(t) <= 2:
            continue
        if t in AR_STOP or t in EN_STOP:
            continue
        clean.append(t)
    return clean


def _top_keywords(sentences: List[str], k: int = 10) -> List[str]:
    c = Counter()
    for s in sentences:
        c.update(_tokenize(s))
    return [w for w, _ in c.most_common(k)]


def _detect_decisions(sentences: List[str]) -> List[str]:
    out = []
    for s in sentences:
        s2 = s.lower()
        if any(k.lower() in s2 for k in DECISION_KWS):
            out.append(s.strip())
    return out[:12]


def _detect_tasks(sentences: List[str]) -> List[str]:
    out = []
    for s in sentences:
        s2 = s.lower()
        if any(k.lower() in s2 for k in TASK_KWS):
            out.append(s.strip())
    return out[:15]


def _extract_numbers_dates(sentences: List[str]) -> List[str]:
    out = []
    pat = re.compile(r"(\d{1,4}[\/\-\.\:]\d{1,2}[\/\-\.\:]\d{1,4})|(\d{1,2}\s*(?:am|pm))|(\d+(?:\.\d+)?)")
    for s in sentences:
        if pat.search(s):
            out.append(s.strip())
    return out[:12]


def _group_by_topics(sentences: List[str]) -> Dict[str, List[str]]:
    # 1) تصنيف بالـ hints
    groups = {k: [] for k in TOPIC_HINTS.keys()}
    other = []
    for s in sentences:
        s2 = s.lower()
        matched = False
        for topic, hints in TOPIC_HINTS.items():
            if any(h.lower() in s2 for h in hints):
                groups[topic].append(s.strip())
                matched = True
                break
        if not matched:
            other.append(s.strip())

    # 2) إذا "أخرى" كبيرة، نطلع منها محاور بناء على كلمات مفتاحية
    if other:
        kw = _top_keywords(other, k=8)
        if kw:
            # نجمع بحسب أول كلمة مفتاحية تظهر
            dynamic = defaultdict(list)
            for s in other:
                s2 = s.lower()
                key = None
                for w in kw:
                    if w in s2:
                        key = w
                        break
                if key:
                    dynamic[f"محور: {key}"].append(s.strip())
                else:
                    dynamic["محاور أخرى"].append(s.strip())

            # خذ أهم 3 محاور ديناميكية
            dyn_items = sorted(dynamic.items(), key=lambda x: len(x[1]), reverse=True)[:4]
            for k2, lst in dyn_items:
                groups[k2] = lst

    # تنظيف: خذ أول 6 جمل من كل محور
    cleaned = {}
    for k, lst in groups.items():
        if lst:
            cleaned[k] = lst[:6]
    return cleaned


def _group_by_speakers(raw_text: str) -> Dict[str, List[str]]:
    lines = [ln.strip() for ln in (raw_text or "").splitlines() if ln.strip()]
    if not lines:
        return {}

    speaker_map: Dict[str, List[str]] = defaultdict(list)
    cur_speaker = None

    for ln in lines:
        hit = None
        for p in SPEAKER_PATTERNS:
            m = re.match(p, ln, flags=re.IGNORECASE)
            if m:
                hit = (m.group(1).strip(), m.group(2).strip())
                break
        if hit:
            cur_speaker = hit[0]
            speaker_map[cur_speaker].append(hit[1])
        else:
            # إذا ما في label: كمّل مع آخر متحدث
            if cur_speaker:
                speaker_map[cur_speaker].append(ln)

    # إذا ما طلع ولا متحدث فعلياً
    if len(speaker_map) <= 0:
        return {}

    # قص لكل متحدث
    out = {}
    for sp, lst in speaker_map.items():
        joined = " ".join(lst)
        sents = _split_sentences(joined)
        out[sp] = sents[:6] if sents else lst[:6]
    return out


@dataclass
class SmartSummary:
    bullets: List[str]
    topics: Dict[str, List[str]]
    speakers: Dict[str, List[str]]
    decisions: List[str]
    tasks: List[str]
    numbers_dates: List[str]
    keywords: List[str]


def build_smart_summary(full_text: str) -> SmartSummary:
    sentences = _split_sentences(full_text)
    keywords = _top_keywords(sentences, k=12)

    # bullets: أول جمل مهمة (أقصر + تحتوي كلمات مفتاحية)
    scored: List[Tuple[int, str]] = []
    for s in sentences:
        score = 0
        s2 = s.lower()
        for w in keywords[:8]:
            if w in s2:
                score += 2
        if any(k.lower() in s2 for k in DECISION_KWS):
            score += 3
        if any(k.lower() in s2 for k in TASK_KWS):
            score += 2
        score -= max(0, len(s) // 180)  # عقوبة للطول
        scored.append((score, s))

    top = [s for _, s in sorted(scored, key=lambda x: x[0], reverse=True)[:10]]
    # نظّف المكررات
    bullets = []
    seen = set()
    for s in top:
        key = s[:60]
        if key not in seen:
            seen.add(key)
            bullets.append(s)

    topics = _group_by_topics(sentences)
    decisions = _detect_decisions(sentences)
    tasks = _detect_tasks(sentences)
    numbers_dates = _extract_numbers_dates(sentences)

    # speakers يعتمد على raw full_text lines
    speakers = _group_by_speakers(full_text)

    return SmartSummary(
        bullets=bullets,
        topics=topics,
        speakers=speakers,
        decisions=decisions,
        tasks=tasks,
        numbers_dates=numbers_dates,
        keywords=keywords,
    )