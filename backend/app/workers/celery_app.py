"""
إعداد Celery المركزي.

كل tasks يجب أن تكون مُسجَّلة هنا (autodiscover).
نستخدم Redis كـ broker و result backend.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init, worker_shutdown
from loguru import logger

from app.config import settings


celery_app = Celery(
    "insighthub",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.workers.analysis_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Tasks longer than 30 min تُلغى
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    # عامل واحد يأخذ مهمة واحدة في المرة (لأن PySpark + transformers ثقيلين)
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=20,  # restart worker بعد 20 مهمة لتفريغ الذاكرة
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # نتائج تُحفظ ليوم واحد
    result_expires=24 * 3600,
)


@worker_process_init.connect
def init_worker(**_):
    """تُستدعى عند بدء كل worker process."""
    logger.info("[celery] worker process initialized")


@worker_shutdown.connect
def shutdown_worker(**_):
    """تنظيف الموارد - إيقاف Spark session."""
    try:
        from app.spark.session import stop_spark
        stop_spark()
    except Exception as e:
        logger.warning(f"[celery] spark cleanup failed: {e}")
    logger.info("[celery] worker process shutting down")
