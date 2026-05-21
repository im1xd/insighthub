"""
تنظيف النصوص العربية المأخوذة من بيانات وسائل التواصل.

نُزيل/نستبدل ما لا يفيد التحليل:
- روابط URL
- mentions (مع الاحتفاظ بقائمة منفصلة لتحليل الشبكة)
- hashtags (نحوّلها إلى نص عادي للحفاظ على المعنى)
- emojis (نُزيلها افتراضياً)
- HTML entities

نُرجع dict بالنص النظيف + metadata مستخرجة من النص الأصلي.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List

from app.processors.normalizer import normalize_for_display


URL_RE = re.compile(r"https?://\S+|www\.\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@([A-Za-z0-9_\u0621-\u064A]{2,30})")
HASHTAG_RE = re.compile(r"#([A-Za-z0-9_\u0621-\u064A]{2,50})")
RT_PREFIX_RE = re.compile(r"^RT\s+@\w+:\s*", flags=re.IGNORECASE)
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)
MULTI_PUNCT_RE = re.compile(r"([!؟?.])\1{2,}")
NON_ARABIC_LATIN_RE = re.compile(
    r"[^\u0600-\u06FF\u0750-\u077Fa-zA-Z0-9\s@#_.,!?؟،؛:'\"\-]"
)


def extract_mentions(text: str) -> List[str]:
    return list({m.lower() for m in MENTION_RE.findall(text or "")})


def extract_hashtags(text: str) -> List[str]:
    return list({h.lower() for h in HASHTAG_RE.findall(text or "")})


def is_retweet(text: str) -> bool:
    return bool(RT_PREFIX_RE.match(text or ""))


def clean_text(
    text: str,
    *,
    remove_emojis: bool = True,
    keep_hashtag_text: bool = True,
    keep_mention_text: bool = False,
) -> str:
    """
    ينظّف النص للاستخدام في النماذج.
    keep_hashtag_text=True يحوّل #كلمة إلى "كلمة" بدل حذفها.
    """
    if not text:
        return ""

    s = html.unescape(text)
    s = RT_PREFIX_RE.sub("", s)
    s = URL_RE.sub(" ", s)

    if keep_mention_text:
        s = MENTION_RE.sub(r"\1", s)
    else:
        s = MENTION_RE.sub(" ", s)

    if keep_hashtag_text:
        s = HASHTAG_RE.sub(lambda m: m.group(1).replace("_", " "), s)
    else:
        s = HASHTAG_RE.sub(" ", s)

    if remove_emojis:
        s = EMOJI_RE.sub(" ", s)

    s = MULTI_PUNCT_RE.sub(r"\1", s)
    s = NON_ARABIC_LATIN_RE.sub(" ", s)
    s = normalize_for_display(s)
    return s


def clean_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    ينظّف منشور كاملاً ويُرجع نسخة موسَّعة بـ metadata مستخرجة.
    لا يعدّل الـ post الأصلي.
    """
    raw_text = post.get("text") or ""
    out = dict(post)
    out["raw_text"] = raw_text
    out["mentions"] = extract_mentions(raw_text)
    out["hashtags"] = extract_hashtags(raw_text)
    out["is_retweet"] = is_retweet(raw_text)
    out["cleaned_text"] = clean_text(raw_text)
    return out


def is_valid_for_analysis(post: Dict[str, Any], min_chars: int = 8) -> bool:
    """يقرر إن كان المنشور مناسباً للتحليل بعد التنظيف."""
    text = post.get("cleaned_text") or post.get("text") or ""
    if len(text.strip()) < min_chars:
        return False
    # يجب أن يحتوي على حرفين عربيين على الأقل
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return arabic_chars >= 3
