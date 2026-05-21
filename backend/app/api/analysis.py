"""
Endpoints لإدارة طلبات التحليل.

POST /api/v1/analysis/trigger     - إطلاق تحليل لطلب موجود
GET  /api/v1/analysis/{id}/status - حالة طلب
GET  /api/v1/analysis/pending     - طلبات pending
POST /api/v1/analysis/{id}/retry  - إعادة تشغيل طلب فشل

التشغيل يتم داخل process الـ FastAPI نفسه عبر BackgroundTasks
مع تحكم بالتوازي عبر app.workers.runner (واحد في المرة).
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database.models import StatusResponse, TriggerRequest
from app.database.supabase_client import (
    get_pending_requests,
    get_request,
    update_request_status,
)
from app.workers.runner import (
    claim,
    in_progress_count,
    is_in_progress,
    run_with_concurrency,
)


router = APIRouter()


@router.post("/trigger")
def trigger_analysis(
    payload: TriggerRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    يضع المهمة في طابور التنفيذ. الطلب يجب أن يكون موجوداً
    في analysis_requests مسبقاً (ينشئه الـ Frontend).
    """
    request_id = str(payload.request_id)
    request_data = get_request(request_id)
    if request_data is None:
        raise HTTPException(status_code=404, detail="Analysis request not found")

    if request_data.get("status") == "completed":
        return {"status": "already_completed", "request_id": request_id}

    if is_in_progress(request_id):
        return {"status": "already_processing", "request_id": request_id}

    current_status = request_data.get("status")
    if current_status in {"collecting", "analyzing"}:
        return {"status": "already_processing", "request_id": request_id}

    if not claim(request_id):
        return {"status": "already_processing", "request_id": request_id}

    update_request_status(request_id, "pending", 5)
    background_tasks.add_task(run_with_concurrency, request_id, request_data)

    return {
        "status": "queued",
        "request_id": request_id,
        "in_progress_count": in_progress_count(),
    }


@router.get("/{request_id}/status", response_model=StatusResponse)
def status(request_id: str) -> StatusResponse:
    data = get_request(request_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Analysis request not found")
    return StatusResponse(
        request_id=data["id"],
        status=data.get("status", "unknown"),
        progress=int(data.get("progress") or 0),
        error_message=data.get("error_message"),
        updated_at=data.get("updated_at"),
    )


@router.get("/pending")
def list_pending(limit: int = 20) -> List[Dict[str, Any]]:
    return get_pending_requests(limit=limit)


@router.post("/{request_id}/retry")
def retry_analysis(
    request_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    data = get_request(request_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Analysis request not found")

    if is_in_progress(request_id):
        return {"status": "already_processing", "request_id": request_id}

    if not claim(request_id):
        return {"status": "already_processing", "request_id": request_id}

    update_request_status(request_id, "pending", 0, error_message=None)
    background_tasks.add_task(run_with_concurrency, request_id, data)
    return {"status": "queued", "request_id": request_id}
