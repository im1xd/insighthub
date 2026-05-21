"""
تحليل المشاعر بالعربية باستخدام CAMeL-BERT.

النموذج الافتراضي:
  CAMeL-Lab/bert-base-arabic-camelbert-da-sentiment

يُرجع labels: positive | negative | neutral
بعض النسخ ترجع label_0/1/2، نُطبِّعها لـ POSITIVE/NEUTRAL/NEGATIVE.

التصميم:
- نموذج singleton (يُحمَّل مرة واحدة لكل process)
- batched inference لتسريع الأداء
- timeline عبر الأيام (إذا كان created_at متوفراً)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings


_pipeline = None


def _label_to_class(label: str) -> str:
    """يطبّع label من النموذج إلى positive/neutral/negative."""
    if not label:
        return "neutral"
    s = label.strip().lower()
    if "pos" in s or s in {"label_2", "2"}:
        return "positive"
    if "neg" in s or s in {"label_0", "0"}:
        return "negative"
    return "neutral"


def get_pipeline():
    """يحمّل/يعيد pipeline تحليل المشاعر."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        from transformers import pipeline
    except ImportError as e:
        logger.error(f"[sentiment] transformers not available: {e}")
        return None

    device = -1
    if settings.nlp_device == "cuda":
        device = 0
    elif settings.nlp_device == "mps":
        device = "mps"

    logger.info(
        f"[sentiment] loading model {settings.sentiment_model} on device={settings.nlp_device}"
    )
    try:
        _pipeline = pipeline(
            task="sentiment-analysis",
            model=settings.sentiment_model,
            device=device,
            truncation=True,
            max_length=128,
        )
        logger.info("[sentiment] model loaded")
        return _pipeline
    except Exception as e:
        logger.error(f"[sentiment] failed to load model: {e}")
        return None


def _fallback_score(text: str) -> Dict[str, Any]:
    """احتياطي بسيط جداً عند فشل تحميل النموذج - lexicon-based."""
    pos_kws = {"ممتاز", "رائع", "جميل", "أحب", "احب", "حلو", "مذهل", "تمام", "زين", "good", "great", "love"}
    neg_kws = {"سيء", "سيئ", "أكره", "اكره", "زفت", "خايب", "فظيع", "مقرف", "bad", "hate", "terrible"}
    s = (text or "").lower()
    p = sum(1 for k in pos_kws if k in s)
    n = sum(1 for k in neg_kws if k in s)
    if p > n:
        return {"label": "positive", "score": min(0.5 + 0.1 * (p - n), 0.95)}
    if n > p:
        return {"label": "negative", "score": min(0.5 + 0.1 * (n - p), 0.95)}
    return {"label": "neutral", "score": 0.55}


def predict_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """يُرجع تنبؤات لكل نص: [{label, score}]."""
    if not texts:
        return []
    pipe = get_pipeline()
    if pipe is None:
        return [_fallback_score(t) for t in texts]

    out: List[Dict[str, Any]] = []
    bs = settings.sentiment_batch_size
    try:
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            preds = pipe(batch, batch_size=len(batch))
            for p in preds:
                out.append({"label": _label_to_class(p["label"]), "score": float(p["score"])})
    except Exception as e:
        logger.error(f"[sentiment] inference failed, fallback: {e}")
        return [_fallback_score(t) for t in texts]
    return out


def _parse_day(timestamp: Optional[str]) -> Optional[str]:
    """يحاول parsing لـ timestamp ويُرجع YYYY-MM-DD أو None."""
    if not timestamp:
        return None
    try:
        # عدة تنسيقات شائعة
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%a %b %d %H:%M:%S +0000 %Y"):
            try:
                return datetime.strptime(timestamp[:25], fmt).date().isoformat()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def analyze_sentiment(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Input:  list من posts (كل واحد فيه cleaned_text و created_at)
    Output: {
      "positive": float,    # نسبة 0-100
      "neutral":  float,
      "negative": float,
      "timeline": [{"day": "YYYY-MM-DD", "positive": int, "negative": int, "neutral": int}],
      "per_post": [{"text": str, "label": str, "score": float}]
    }
    """
    if not posts:
        return {
            "positive": 0.0, "neutral": 0.0, "negative": 0.0,
            "timeline": [], "per_post": []
        }

    texts = [p.get("cleaned_text") or p.get("text") or "" for p in posts]
    preds = predict_batch(texts)

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    timeline: Dict[str, Dict[str, int]] = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    per_post: List[Dict[str, Any]] = []

    for post, pred in zip(posts, preds):
        cls = pred["label"]
        counts[cls] += 1
        per_post.append({
            "text": (post.get("cleaned_text") or post.get("text") or "")[:200],
            "label": cls,
            "score": pred["score"],
        })
        day = _parse_day(post.get("created_at"))
        if day:
            timeline[day][cls] += 1

    total = sum(counts.values()) or 1

    timeline_list = [
        {"day": day, **vals}
        for day, vals in sorted(timeline.items())
    ]

    return {
        "positive": round(100.0 * counts["positive"] / total, 2),
        "neutral":  round(100.0 * counts["neutral"]  / total, 2),
        "negative": round(100.0 * counts["negative"] / total, 2),
        "timeline": timeline_list,
        "per_post": per_post,
    }
