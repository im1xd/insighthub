"""
إزالة المكررات بطريقتين:
- exact: نفس النص بعد التطبيع (سريع، O(n))
- near: تشابه نصي عالٍ (TF-IDF cosine، أبطأ لكنه يلتقط المكررات شبه المطابقة)

نوصي بـ exact للـ pipelines السريعة، near للجودة العالية.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.processors.normalizer import normalize_for_search


def deduplicate_exact(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """يحتفظ بأول نسخة من كل نص مُطبَّع."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for post in posts:
        text = post.get("cleaned_text") or post.get("text") or ""
        key = normalize_for_search(text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(post)
    return out


def deduplicate_near(
    posts: List[Dict[str, Any]],
    threshold: float = 0.92,
    max_posts: int = 5_000,
) -> List[Dict[str, Any]]:
    """
    إزالة المكررات شبه المطابقة. مكلفة - تستخدم فقط على
    عينة محدودة (max_posts) لأن التعقيد O(n²) في حالة المصفوفة الكثيفة.
    """
    if len(posts) <= 1:
        return posts

    # نشتغل على عينة محدودة لتفادي الانفجار
    posts = posts[:max_posts]
    texts = [normalize_for_search(p.get("cleaned_text") or p.get("text") or "") for p in posts]

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return deduplicate_exact(posts)

    valid_idx = [i for i, t in enumerate(texts) if t]
    if len(valid_idx) <= 1:
        return [posts[i] for i in valid_idx]

    vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1, 2), max_features=10_000)
    matrix = vectorizer.fit_transform([texts[i] for i in valid_idx])
    sim = cosine_similarity(matrix)

    keep = [True] * len(valid_idx)
    for i in range(len(valid_idx)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(valid_idx)):
            if keep[j] and sim[i][j] >= threshold:
                keep[j] = False

    return [posts[valid_idx[i]] for i, k in enumerate(keep) if k]
