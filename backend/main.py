"""
InsightHub API - نقطة الدخول الرئيسية.

تشغّل:
    uvicorn main:app --reload --port 8000

لتشغيل العامل:
    celery -A app.workers.celery_app worker --loglevel=info
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


# =====================================================================
# Polling loop - يفحص طلبات pending ويُطلق Celery tasks
# =====================================================================

_polling_task: asyncio.Task | None = None


async def poll_loop():
    """
    حلقة فحص دورية. لا تعمل في الـ production إذا كان هناك
    webhook خارجي، لكنها مفيدة للتطوير ولـ Frontend الذي
    يكتب مباشرة في Supabase دون استدعاء /trigger.
    """
    from app.workers.analysis_worker import run_analysis

    interval = max(5, settings.poll_interval_seconds)
    logger.info(f"[poll] starting loop with interval={interval}s")
    while True:
        try:
            pending = get_pending_requests(limit=10)
            if pending:
                logger.info(f"[poll] found {len(pending)} pending requests")
            for req in pending:
                rid = str(req["id"])
                run_analysis.apply_async(args=[rid, req])
                logger.info(f"[poll] queued {rid}")
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
        logger.info("[lifespan] polling disabled")
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
        "يعمل على datasets عربية مفتوحة ويحلّلها بـ PySpark + Transformers."
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
