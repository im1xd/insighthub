"""
المهمة الأساسية - pipeline التحليل الكامل.

سابقاً كانت Celery task. الآن دالة عادية تُستدعى من
FastAPI BackgroundTasks عبر runner.run_with_concurrency.

تنفذ 11 خطوة وتحدّث progress في Supabase عند كل خطوة.
عند الفشل في أي خطوة، نُعلِّم الطلب بـ status=failed مع error_message.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.analyzers.influencer_detector import detect_influencers
from app.analyzers.network_analyzer import build_interaction_network
from app.analyzers.report_generator import generate_recommendations, generate_summary
from app.analyzers.sentiment_analyzer import analyze_sentiment
from app.analyzers.topic_modeler import extract_topics
from app.config import settings
from app.database.supabase_client import (
    create_notification,
    log_audit,
    save_results,
    update_request_status,
)
from app.datasets.registry import default_dataset_ids
from app.datasets.stream_manager import StreamManager
from app.processors.cleaner import clean_post, is_valid_for_analysis
from app.spark.aggregations import compute_overall_stats, dataset_breakdown
from app.spark.filters import apply_full_filter, build_dataframe_from_rows


def run_analysis(request_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    يُنفّذ pipeline تحليل واحد من البداية للنهاية.
    تُستدعى عادةً من FastAPI BackgroundTasks (داخل runner).

    request_data يحتوي ما تم قراءته من analysis_requests:
      id, user_id, title, keywords, platforms, analysis_type,
      date_from, date_to, ...
    اختياري:
      dataset_ids: list[str]  (إذا غاب، نستخدم default)

    يُرجع dict موجز عن النتيجة - لا يرفع استثناءات للأعلى.
    """
    started_at = datetime.utcnow()
    user_id = str(request_data.get("user_id") or "")
    title = request_data.get("title", "")
    keywords: List[str] = request_data.get("keywords") or []
    date_from = _to_iso_date(request_data.get("date_from"))
    date_to = _to_iso_date(request_data.get("date_to"))
    dataset_ids: Optional[List[str]] = request_data.get("dataset_ids") or default_dataset_ids()

    logger.info(
        f"[worker] analysis start id={request_id} kw={keywords} "
        f"datasets={dataset_ids} dates=[{date_from}, {date_to}]"
    )

    try:
        # ===== 1. Collecting =====
        update_request_status(request_id, "collecting", 10)

        # ===== 2. Stream datasets =====
        manager = StreamManager()
        raw_rows = list(manager.stream_many(
            dataset_ids=dataset_ids,
            max_total_rows=settings.max_posts_per_analysis,
        ))
        logger.info(f"[worker] streamed {len(raw_rows)} raw rows")
        update_request_status(request_id, "collecting", 25)

        if not raw_rows:
            return _fail(request_id, "لم يتم جلب أي بيانات من المصادر المحددة.")

        # ===== 3. Clean + validate =====
        cleaned = []
        for row in raw_rows:
            cp = clean_post(row)
            if is_valid_for_analysis(cp):
                cleaned.append(cp)
        logger.info(f"[worker] valid after cleaning: {len(cleaned)}")
        update_request_status(request_id, "analyzing", 35)

        if not cleaned:
            return _fail(request_id, "لم تتبق بيانات صالحة بعد التنظيف.")

        # ===== 4-5. Build Spark DataFrame + filter =====
        df = build_dataframe_from_rows(cleaned)
        df = apply_full_filter(
            df,
            keywords=keywords,
            date_from=date_from,
            date_to=date_to,
            deduplicate=True,
        )

        # نُعيد البيانات إلى Python للتحليل النصي
        filtered_rows = df.collect()
        # نحفظ الإحصائيات قبل تحويل الـ DataFrame
        overall = compute_overall_stats(df)
        breakdown = dataset_breakdown(df)
        update_request_status(request_id, "analyzing", 45)
        logger.info(
            f"[worker] after filter: posts={overall['total_posts']} "
            f"users={overall['total_users']} reach={overall['total_reach']}"
        )

        if overall["total_posts"] < settings.min_posts_threshold:
            return _fail(
                request_id,
                f"عدد المنشورات بعد الفلترة ({overall['total_posts']}) أقل من الحد الأدنى "
                f"({settings.min_posts_threshold}). جرّب كلمات مفتاحية أوسع أو datasets إضافية."
            )

        # نُحوّل Spark Rows إلى dicts نمط cleaned (مع mentions/hashtags المُستخرجة)
        filtered_texts_set = {r["text"] for r in filtered_rows}
        posts = [p for p in cleaned if p.get("cleaned_text") and p["cleaned_text"] in filtered_texts_set]
        if not posts:
            posts = cleaned

        # ===== 6. Sentiment =====
        update_request_status(request_id, "analyzing", 55)
        sentiment = analyze_sentiment(posts)
        logger.info(
            f"[worker] sentiment: pos={sentiment['positive']} "
            f"neu={sentiment['neutral']} neg={sentiment['negative']}"
        )
        update_request_status(request_id, "analyzing", 65)

        # ===== 7. Topics =====
        topics = extract_topics(
            [p["cleaned_text"] for p in posts if p.get("cleaned_text")],
            n_topics=8,
            method="tfidf",
        )
        logger.info(f"[worker] topics: {len(topics)} found")
        update_request_status(request_id, "analyzing", 75)

        # ===== 8. Influencers =====
        influencers = detect_influencers(posts, top_n=10)
        logger.info(f"[worker] influencers: {len(influencers)}")
        update_request_status(request_id, "analyzing", 82)

        # ===== 9. Network =====
        network = build_interaction_network(posts, max_nodes=50, max_edges=200)
        logger.info(
            f"[worker] network: nodes={len(network['nodes'])} "
            f"edges={len(network['edges'])}"
        )
        update_request_status(request_id, "analyzing", 90)

        # ===== 10. Summary + Recommendations =====
        analysis_data = {
            "sentiment": {
                "positive": sentiment["positive"],
                "neutral":  sentiment["neutral"],
                "negative": sentiment["negative"],
                "timeline": sentiment["timeline"],
            },
            "topics": topics,
            "influencers": influencers,
            "total_posts": overall["total_posts"],
            "total_users": overall["total_users"],
            "keywords": keywords,
        }
        summary = generate_summary(analysis_data)
        recommendations = generate_recommendations(analysis_data)

        # ===== 11. Save & notify =====
        results = {
            "total_posts":        int(overall["total_posts"]),
            "total_users":        int(overall["total_users"]),
            "total_reach":        int(overall["total_reach"]),
            "sentiment_positive": float(sentiment["positive"]),
            "sentiment_neutral":  float(sentiment["neutral"]),
            "sentiment_negative": float(sentiment["negative"]),
            "top_topics":         topics,
            "top_influencers":    influencers,
            "sentiment_timeline": sentiment["timeline"],
            "network_nodes":      network["nodes"],
            "network_edges":      network["edges"],
            "summary":            summary,
            "recommendations":    recommendations,
        }
        save_results(request_id, results)
        update_request_status(request_id, "completed", 100)

        if user_id:
            create_notification(
                user_id=user_id,
                title="اكتمل التحليل",
                body=f"تحليل '{title}' جاهز للمراجعة",
                notif_type="analysis_complete",
                link=f"#analysis-{request_id}",
            )

        log_audit(
            action="ANALYSIS_COMPLETED",
            entity_type="analysis_request",
            entity_id=request_id,
            metadata={
                "total_posts": overall["total_posts"],
                "duration_seconds": (datetime.utcnow() - started_at).total_seconds(),
                "datasets_used": breakdown,
            },
        )

        duration = (datetime.utcnow() - started_at).total_seconds()
        logger.info(f"[worker] analysis {request_id} completed in {duration:.1f}s")
        return {
            "status": "success",
            "request_id": request_id,
            "total_posts": overall["total_posts"],
            "duration_seconds": duration,
        }

    except Exception as exc:
        logger.exception(f"[worker] analysis {request_id} failed")
        return _fail(request_id, f"فشل التحليل: {str(exc)[:300]}")


# =====================================================================
# Helpers
# =====================================================================

def _fail(request_id: str, message: str) -> Dict[str, Any]:
    update_request_status(request_id, "failed", 0, error_message=message)
    log_audit(
        action="ANALYSIS_FAILED",
        entity_type="analysis_request",
        entity_id=request_id,
        metadata={"error": message},
    )
    return {"status": "failed", "request_id": request_id, "error": message}


def _to_iso_date(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        return value[:10]
    try:
        return value.isoformat()[:10]
    except Exception:
        return None
