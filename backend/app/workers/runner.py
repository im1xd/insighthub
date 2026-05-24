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
    يُستدعى من poll_loop أو BackgroundTasks.

    ملاحظة: claim() يجب أن تكون قد استُدعيت مسبقاً من poll_loop أو api.
    هذه الدالة لا تُعيد claim — فقط تُنفّذ وتحرّر.
    """
    from app.workers.analysis_worker import run_analysis

    try:
        logger.info(f"[runner] starting {request_id} (concurrent={in_progress_count()})")
        with _semaphore:
            return run_analysis(request_id, request_data)
    except Exception as e:
        logger.error(f"[runner] {request_id} crashed: {e}")
        return {"status": "failed", "request_id": request_id, "error": str(e)}
    finally:
        release(request_id)
        logger.info(f"[runner] released {request_id}")
