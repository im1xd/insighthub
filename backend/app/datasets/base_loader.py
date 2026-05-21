"""
الواجهة الأساسية لكل dataset loader.

كل loader يستلم DatasetMeta ويُرجع iterator يعطي صفوف موحَّدة
بالشكل القياسي:
{
  "text": str,          # النص الأصلي (إلزامي)
  "created_at": str,    # ISO timestamp أو None
  "user_id": str,       # معرّف المستخدم أو None
  "user_handle": str,   # @handle أو None
  "user_followers": int,
  "likes": int,
  "retweets": int,
  "replies": int,
  "lang": str,
  "label": Any,         # تصنيف من الـ dataset إن وُجد
  "source_dataset": str # id الـ dataset (يُضاف تلقائياً)
}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, Optional

from app.datasets.registry import DatasetMeta, FieldMapping


# الشكل القياسي لكل صف بعد التطبيع
CANONICAL_KEYS = [
    "text",
    "created_at",
    "user_id",
    "user_handle",
    "user_followers",
    "likes",
    "retweets",
    "replies",
    "lang",
    "label",
    "source_dataset",
]


def to_canonical(raw: Dict[str, Any], meta: DatasetMeta) -> Optional[Dict[str, Any]]:
    """
    يحوّل صفاً من الشكل الأصلي للـ dataset إلى الشكل القياسي.
    يُرجع None إذا كان النص فارغاً.
    """
    fm: FieldMapping = meta.fields
    text = raw.get(fm.text)
    if not text or not isinstance(text, str) or not text.strip():
        return None

    def _get(field: Optional[str], default: Any = None) -> Any:
        if not field:
            return default
        return raw.get(field, default)

    return {
        "text": text.strip(),
        "created_at": _get(fm.created_at),
        "user_id": _get(fm.user_id),
        "user_handle": _get(fm.user_handle),
        "user_followers": _safe_int(_get(fm.user_followers)),
        "likes": _safe_int(_get(fm.likes)),
        "retweets": _safe_int(_get(fm.retweets)),
        "replies": _safe_int(_get(fm.replies)),
        "lang": _get(fm.lang, meta.language),
        "label": _get(fm.label),
        "source_dataset": meta.id,
    }


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


class BaseLoader(ABC):
    """قاعدة كل loader - يجب تنفيذ stream()."""

    def __init__(self, meta: DatasetMeta):
        self.meta = meta

    @abstractmethod
    def stream(
        self,
        max_rows: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """يُنتج صفوفاً بالشكل القياسي. lazy - لا يحمّل كل شيء في الذاكرة."""

    def take(self, n: int) -> list[Dict[str, Any]]:
        """مساعد لجلب أول n صف."""
        out: list[Dict[str, Any]] = []
        for row in self.stream(max_rows=n):
            out.append(row)
            if len(out) >= n:
                break
        return out
