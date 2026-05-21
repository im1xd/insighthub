"""
اكتشاف المؤثرين.

السيناريوهات:
A) الـ dataset يحتوي على user metadata (followers, handle):
   نحسب influence_score مركّب من:
     - followers_count        (35%)
     - engagement_rate        (40%) = (likes+retweets+replies) / followers
     - posting_frequency       (15%)
     - mentions_received       (10%)

B) الـ dataset لا يحتوي metadata (شائع في datasets HF):
   نستخدم بدائل:
     - عدد المنشورات في الموضوع (proxy للنشاط)
     - عدد المرات التي ذُكر فيها author
     - تنوع المواضيع
   نُرجع قائمة "active authors" بدل influencers حقيقيين.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List


def detect_influencers(
    posts: List[Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """يُرجع أعلى المؤثرين أو الكتاب نشاطاً."""
    if not posts:
        return []

    # هل لدينا user metadata حقيقية؟
    has_users = any(p.get("user_id") or p.get("user_handle") for p in posts)
    has_followers = any((p.get("user_followers") or 0) > 0 for p in posts)

    if not has_users:
        return _frequency_based_authors(posts, top_n)

    # تجميع الإحصائيات لكل مستخدم
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "handle": None, "followers": 0, "posts": 0,
        "likes": 0, "retweets": 0, "replies": 0, "mentions_in": 0,
    })

    # إحصاء الـ mentions
    mention_counter: Counter = Counter()
    for p in posts:
        for m in p.get("mentions") or []:
            mention_counter[m] += 1

    for p in posts:
        uid = p.get("user_id") or p.get("user_handle")
        if not uid:
            continue
        s = stats[uid]
        s["handle"] = p.get("user_handle") or uid
        s["followers"] = max(s["followers"], int(p.get("user_followers") or 0))
        s["posts"] += 1
        s["likes"] += int(p.get("likes") or 0)
        s["retweets"] += int(p.get("retweets") or 0)
        s["replies"] += int(p.get("replies") or 0)

    # نُضيف mentions
    for uid, s in stats.items():
        handle = (s.get("handle") or "").lstrip("@").lower()
        s["mentions_in"] = mention_counter.get(handle, 0)

    if not stats:
        return _frequency_based_authors(posts, top_n)

    # نحسب influence_score
    max_followers = max((s["followers"] for s in stats.values()), default=1) or 1
    max_posts = max((s["posts"] for s in stats.values()), default=1) or 1
    max_mentions = max((s["mentions_in"] for s in stats.values()), default=1) or 1

    scored: List[Dict[str, Any]] = []
    for uid, s in stats.items():
        engagement_total = s["likes"] + s["retweets"] + s["replies"]
        engagement_rate = engagement_total / max(s["followers"], 1)

        # تطبيع كل مؤشر إلى 0-1
        f_norm = (s["followers"] / max_followers) if has_followers else 0
        e_norm = min(engagement_rate, 1.0)
        p_norm = s["posts"] / max_posts
        m_norm = s["mentions_in"] / max_mentions

        if has_followers:
            influence = 0.35 * f_norm + 0.40 * e_norm + 0.15 * p_norm + 0.10 * m_norm
        else:
            influence = 0.50 * p_norm + 0.30 * e_norm + 0.20 * m_norm

        scored.append({
            "handle": s["handle"] if str(s["handle"]).startswith("@") else f"@{s['handle']}",
            "followers": s["followers"],
            "influence": round(min(1.0, influence), 3),
            "total_posts": s["posts"],
            "avg_engagement": round(engagement_rate, 2),
        })

    scored.sort(key=lambda x: x["influence"], reverse=True)
    return scored[:top_n]


def _frequency_based_authors(posts: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """
    عند غياب metadata، نُرجع مؤلفين تركيبيين بناءً على
    تكرار الـ mentions ضمن النصوص نفسها.
    """
    mention_counter: Counter = Counter()
    for p in posts:
        for m in p.get("mentions") or []:
            mention_counter[m] += 1

    if not mention_counter:
        return []

    max_count = max(mention_counter.values()) or 1
    out = []
    for handle, cnt in mention_counter.most_common(top_n):
        out.append({
            "handle": f"@{handle}",
            "followers": 0,  # غير معروف
            "influence": round(cnt / max_count, 3),
            "total_posts": cnt,
            "avg_engagement": 0,
        })
    return out
