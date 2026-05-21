"""
منسّق تشغيل المهام داخل process الـ FastAPI.

المشكلة: BackgroundTasks لا يتحكم بالتوازي. لو وصلت 10 طلبات معاً
سنحاول تشغيل 10 pipelines متوازية وكل واحد يستهلك ~1.5 GB.

الحل: قائمة انتظار + مجموعة "قيد التنفيذ" + concurrency limit.
- نسجل request_id قبل بدء التنفيذ في in_progress
- يفحص poll_loop المجموعة قبل إرسال نفس الطلب مرتين
- ننهي بإزالة الـ id من المجموعة سواء نجح أم فشل
"""

from __future__ import annotations

import threading
from typing import Any, Dict

from loguru import logger


# الحد الأقصى للتحليلات المتوازية. يستهلك كل تحليل ذاكرة كبيرة
# (PySpark + CAMeL-BERT) لذلك واحد في المرة هو الأكثر أماناً على HF.
_MAX_CONCURRENT = 1
_semaphore = threading.BoundedSemaphore(_MAX_CONCURRENT)
_in_progress: set[str] = set()
_lock = threading.Lock()


def is_in_progress(request_id: str) -> bool:
    with _lock:
        return request_id in _in_progress


def claim(request_id: str) -> bool:
    """يحاول تسجيل الطلب. يُرجع False إن كان قيد التنفيذ بالفعل."""
    with _lock:
        if request_id in _in_progress:
            return False
        _in_progress.add(request_id)
        return True


def release(request_id: str) -> None:
    with _lock:
        _in_progress.discard(request_id)


def in_progress_count() -> int:
    with _lock:
        return len(_in_progress)


def run_with_concurrency(request_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper يستدعي run_analysis تحت قفل توازي.
    BackgroundTasks سيستدعي هذه الدالة (وليس run_analysis مباشرة).
    """
    from app.workers.analysis_worker import run_analysis

    # claim قد تم بالفعل قبل استدعاء البلوك (في api أو polling)
    # لكن للأمان نتحقق
    if not claim(request_id):
        logger.warning(f"[runner] {request_id} already in progress, skipping")
        return {"status": "skipped", "reason": "already_in_progress"}

    try:
        with _semaphore:
            logger.info(f"[runner] starting {request_id} (concurrent={in_progress_count()})")
            return run_analysis(request_id, request_data)
    finally:
        release(request_id)
        logger.info(f"[runner] released {request_id}")
