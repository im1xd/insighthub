"""
InsightHub API - نقطة الدخول الرئيسية.

النشر على Hugging Face Spaces:
    HF يبني الـ Dockerfile تلقائياً ويشغّل:
    uvicorn main:app --host 0.0.0.0 --port 7860

التشغيل المحلي:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import analysis, datasets, results
from app.config import settings
from app.database.models import HealthResponse
from app.database.supabase_client import get_pending_requests, is_configured
from app.workers.runner import (
    claim,
    in_progress_count,
    is_in_progress,
    run_with_concurrency,
)


# =====================================================================
# Polling loop - يفحص طلبات pending ويُطلقها كـ background tasks
#
# الفائدة الرئيسية: الـ Frontend يكتب مباشرة في Supabase ولا يستدعي
# /trigger. لذا نحتاج آلية تلتقط الطلبات الجديدة تلقائياً.
# =====================================================================

_polling_task: asyncio.Task | None = None


async def poll_loop():
    interval = max(5, settings.poll_interval_seconds)
    logger.info(f"[poll] starting loop with interval={interval}s")
    loop = asyncio.get_event_loop()
    while True:
        try:
            pending = get_pending_requests(limit=10)
            for req in pending:
                rid = str(req["id"])
                if is_in_progress(rid):
                    continue
                if not claim(rid):
                    continue
                logger.info(f"[poll] dispatching {rid}")
                # نشغّل في thread منفصل (daemon) لأن run_with_concurrency ثقيلة
                import threading
                t = threading.Thread(
                    target=run_with_concurrency,
                    args=(rid, req),
                    daemon=True,
                    name=f"worker-{rid[:8]}",
                )
                t.start()
                # ننتظر فقط لطلب واحد في كل دورة polling
                break
        except Exception as e:
            logger.error(f"[poll] error: {e}")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _polling_task
    if settings.enable_polling and is_configured():
        _polling_task = asyncio.create_task(poll_loop())
        logger.info("[lifespan] polling enabled")
    else:
        logger.info(
            "[lifespan] polling disabled "
            f"(enable_polling={settings.enable_polling}, "
            f"supabase_configured={is_configured()})"
        )
    yield
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        logger.info("[lifespan] polling stopped")


# =====================================================================
# FastAPI app
# =====================================================================

app = FastAPI(
    title="InsightHub API",
    version="1.0.0",
    description=(
        "Backend لمنصة تحليل وسائل التواصل الاجتماعي. "
        "يسحب datasets عربية مفتوحة من HuggingFace ويحلّلها بـ "
        "PySpark + Transformers، ويحفظ النتائج في Supabase."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(results.router,  prefix="/api/v1/results",  tags=["results"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["datasets"])


@app.get("/")
def root():
    return {
        "name": "InsightHub API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "concurrent_analyses": in_progress_count(),
    }


@app.get("/health", response_model=HealthResponse)
def health():
    spark_available = False
    try:
        from app.spark.session import get_spark
        get_spark()
        spark_available = True
    except Exception:
        pass
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        spark_available=spark_available,
        supabase_configured=is_configured(),
    )
