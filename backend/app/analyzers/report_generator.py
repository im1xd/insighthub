"""
توليد ملخص نصي وتوصيات.

نهج قاعدي (template-based) لا يحتاج LLM خارجي. النتائج محتراِفة
كافية لمشروع ماستر، ويمكن لاحقاً ربط GPT/Claude لتحسين الجودة.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _dominant_sentiment(s: Dict[str, float]) -> str:
    pairs = [("positive", s.get("positive", 0)),
             ("neutral",  s.get("neutral",  0)),
             ("negative", s.get("negative", 0))]
    return max(pairs, key=lambda x: x[1])[0]


def _format_topics(topics: List[Dict[str, Any]], max_n: int = 5) -> str:
    if not topics:
        return ""
    items = [t.get("label", "") for t in topics[:max_n] if t.get("label")]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "، ".join(items[:-1]) + " و" + items[-1]


def generate_summary(data: Dict[str, Any]) -> str:
    sentiment = data.get("sentiment", {})
    topics = data.get("topics", [])
    influencers = data.get("influencers", [])
    total_posts = data.get("total_posts", 0)
    total_users = data.get("total_users", 0)
    keywords = data.get("keywords", [])

    if total_posts == 0:
        return "لم يتم العثور على بيانات كافية للتحليل."

    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)
    neu = sentiment.get("neutral", 0)
    dom = _dominant_sentiment(sentiment)
    dom_ar = {"positive": "إيجابية", "neutral": "محايدة", "negative": "سلبية"}[dom]

    lines: List[str] = []
    kw_text = "، ".join(f'"{k}"' for k in keywords[:5]) if keywords else "الموضوع المختار"
    lines.append(
        f"تحليل {total_posts:,} منشور حول {kw_text} من {total_users:,} مصدر مختلف."
    )
    lines.append(
        f"النبرة العامة {dom_ar} حيث بلغت المشاعر الإيجابية {pos:.1f}% "
        f"والسلبية {neg:.1f}% والمحايدة {neu:.1f}%."
    )

    topics_str = _format_topics(topics)
    if topics_str:
        lines.append(f"أبرز المحاور التي تكررت في النقاش هي: {topics_str}.")

    if influencers:
        top = influencers[0]
        lines.append(
            f"الحساب الأكثر تأثيراً هو {top.get('handle')} "
            f"بمؤشر تأثير {top.get('influence', 0):.2f}."
        )

    return " ".join(lines)


def generate_recommendations(data: Dict[str, Any]) -> List[str]:
    """قائمة توصيات عملية بناءً على الأرقام."""
    sentiment = data.get("sentiment", {})
    topics = data.get("topics", [])
    influencers = data.get("influencers", [])
    total_posts = data.get("total_posts", 0)

    recs: List[str] = []

    if total_posts < 100:
        recs.append(
            "حجم البيانات محدود — يُنصح بتوسيع نطاق الكلمات المفتاحية أو "
            "إضافة datasets إضافية للحصول على نتائج أكثر تمثيلاً."
        )

    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)

    if neg > 35:
        topic_hint = topics[0]["label"] if topics else "الموضوع الرئيسي"
        recs.append(
            f"المشاعر السلبية مرتفعة ({neg:.1f}%) — يُستحسن مراجعة "
            f"النقاشات حول '{topic_hint}' ومعالجة أسباب عدم الرضا."
        )
    elif pos > 60:
        recs.append(
            f"المشاعر الإيجابية مرتفعة ({pos:.1f}%) — استثمر هذا الزخم "
            f"عبر حملات تسويقية تستند إلى الرسائل المحببة لدى الجمهور."
        )

    if influencers:
        top3 = influencers[:3]
        handles = "، ".join([i.get("handle", "") for i in top3 if i.get("handle")])
        if handles:
            recs.append(
                f"تواصل مع المؤثرين الأعلى تأثيراً ({handles}) "
                f"لتعزيز الوصول والمصداقية."
            )

    if topics and len(topics) >= 3:
        focus = ", ".join([t["label"] for t in topics[:3] if t.get("label")])
        recs.append(
            f"ركّز محتوى التواصل القادم على المحاور التالية: {focus}، "
            f"فهي الأكثر اهتماماً لدى الجمهور."
        )

    timeline = sentiment.get("timeline", [])
    if len(timeline) >= 3:
        recs.append(
            "راقب اتجاه المشاعر عبر الزمن — التغيرات المفاجئة قد تشير "
            "إلى أحداث تستدعي استجابة سريعة."
        )

    if not recs:
        recs.append("استمر في رصد النقاش بانتظام للوقوف على التحولات في رأي الجمهور.")

    return recs
