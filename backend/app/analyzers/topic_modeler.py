"""
استخراج المواضيع - حلين:

1) الافتراضي (سريع وموثوق): TF-IDF + n-grams + اختيار أعلى الكلمات.
   لا يحتاج تحميل نماذج ثقيلة، يعمل بكفاءة على بيانات محدودة.

2) المتقدم (BERTopic): إن كانت المكتبة مثبتة وحجم البيانات يكفي.
   يعطي مواضيع أنظف لكن يحتاج embeddings (ثقيل).

نُرجع تنسيقاً ثابتاً يطابق توقع الـ Frontend:
  [{"label": "السعر", "weight": 82}, ...]

حيث weight = أهمية نسبية 0-100.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.processors.normalizer import normalize_for_search


# قائمة كلمات إيقاف عربية شائعة
ARABIC_STOPWORDS = {
    "في","من","الى","إلى","على","عن","مع","هذا","هذه","ذلك","ذلكم",
    "التي","الذي","الذين","التى","ما","لا","لن","لم","قد","كل","كما",
    "ثم","او","أو","ام","أم","لكن","انا","أنا","انت","أنت","نحن","هم",
    "هي","هو","هما","انتم","أنتم","كان","كانت","يكون","تكون","يا",
    "ايضا","أيضا","حتى","عند","لدى","غير","حول","بين","فقط","جدا","جداً",
    "the","a","an","and","or","but","is","are","was","were","i","you",
    "he","she","we","they","it","of","to","in","on","at","with","for",
}


def _tokenize(text: str) -> List[str]:
    """تقسيم بسيط للنص بعد التطبيع."""
    s = normalize_for_search(text)
    tokens = re.findall(r"[\u0600-\u06FFa-z0-9]{2,}", s)
    return [t for t in tokens if t not in ARABIC_STOPWORDS and len(t) > 1]


def extract_topics_tfidf(
    texts: List[str],
    n_topics: int = 8,
    ngram_range: tuple = (1, 2),
) -> List[Dict[str, Any]]:
    """
    نهج TF-IDF: أعلى الكلمات/الثنائيات تكراراً مع وزن TF-IDF.
    هذا ليس topic modeling حقيقي بل keyphrase extraction، لكنه يعطي
    نتيجة قابلة للعرض ومفيدة في معظم الحالات.
    """
    if not texts:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        logger.error("[topics] sklearn not available")
        return []

    docs = [" ".join(_tokenize(t)) for t in texts if t]
    docs = [d for d in docs if d]
    if not docs:
        return []

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=ngram_range,
            max_features=2000,
            min_df=max(2, len(docs) // 100),
        )
        matrix = vectorizer.fit_transform(docs)
    except ValueError:
        # min_df فشل لقلة البيانات - نسترخي
        vectorizer = TfidfVectorizer(ngram_range=ngram_range, max_features=2000, min_df=1)
        matrix = vectorizer.fit_transform(docs)

    scores = matrix.sum(axis=0).A1
    vocab = vectorizer.get_feature_names_out()

    pairs = sorted(zip(vocab, scores), key=lambda x: x[1], reverse=True)
    pairs = pairs[: n_topics * 3]  # نأخذ أكثر للفلترة بعد ذلك

    # نتفادى المواضيع التي هي subset/superset من بعضها
    chosen: List[tuple] = []
    for term, sc in pairs:
        if any(term in c[0] or c[0] in term for c in chosen):
            continue
        chosen.append((term, sc))
        if len(chosen) >= n_topics:
            break

    if not chosen:
        return []

    max_score = chosen[0][1] or 1.0
    return [
        {"label": term, "weight": int(round(100.0 * sc / max_score))}
        for term, sc in chosen
    ]


def extract_topics_bertopic(texts: List[str], n_topics: int = 8) -> List[Dict[str, Any]]:
    """نهج BERTopic - يحتاج عدد كبير من الوثائق."""
    try:
        from bertopic import BERTopic
    except ImportError:
        logger.warning("[topics] BERTopic not installed, fallback to TF-IDF")
        return extract_topics_tfidf(texts, n_topics)

    if len(texts) < 100:
        return extract_topics_tfidf(texts, n_topics)

    try:
        model = BERTopic(language="multilingual", calculate_probabilities=False, verbose=False)
        topics, _ = model.fit_transform(texts)
        info = model.get_topic_info()
        if info.empty:
            return extract_topics_tfidf(texts, n_topics)
        # نستبعد topic -1 (outliers)
        info = info[info["Topic"] != -1].head(n_topics)
        max_count = info["Count"].max() or 1
        out = []
        for _, row in info.iterrows():
            label = " ".join([w for w, _ in model.get_topic(row["Topic"])][:2])
            weight = int(round(100.0 * row["Count"] / max_count))
            out.append({"label": label, "weight": weight})
        return out
    except Exception as e:
        logger.warning(f"[topics] BERTopic failed: {e}, fallback to TF-IDF")
        return extract_topics_tfidf(texts, n_topics)


def extract_topics(texts: List[str], n_topics: int = 8, method: str = "tfidf") -> List[Dict[str, Any]]:
    """نقطة الدخول - method = tfidf | bertopic."""
    if method == "bertopic":
        return extract_topics_bertopic(texts, n_topics)
    return extract_topics_tfidf(texts, n_topics)
