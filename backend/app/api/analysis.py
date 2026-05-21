"""
Endpoints لإدارة طلبات التحليل.

POST /api/v1/analysis/trigger     - إطلاق تحليل لطلب موجود
GET  /api/v1/analysis/{id}/status - حالة طلب
GET  /api/v1/analysis/pending     - طلبات pending
POST /api/v1/analysis/{id}/retry  - إعادة تشغيل طلب فشل
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database.models import StatusResponse, TriggerRequest
from app.database.supabase_client import get_pending_requests, get_request, update_request_status
from app.workers.analysis_worker import run_analysis


router = APIRouter()


@router.post("/trigger")
def trigger_analysis(payload: TriggerRequest) -> Dict[str, Any]:
    """
    يضع المهمة في طابور Celery. يجب أن يكون الطلب موجوداً
    في analysis_requests مسبقاً.
    """
    request_id = str(payload.request_id)
    request_data = get_request(request_id)
    if request_data is None:
        raise HTTPException(status_code=404, detail="Analysis request not found")

    # نُعلِّم الطلب فوراً كـ pending للتجنّب الازدواجية
    if request_data.get("status") == "completed":
        return {"task_id": None, "status": "already_completed", "request_id": request_id}

    # إذا كان قيد المعالجة، نرفض إلا إذا أُجبر retry
    current_status = request_data.get("status")
    if current_status in {"collecting", "analyzing"}:
        return {"task_id": None, "status": "already_processing", "request_id": request_id}

    update_request_status(request_id, "pending", 0)
    task = run_analysis.apply_async(args=[request_id, request_data])
    return {"task_id": task.id, "status": "queued", "request_id": request_id}


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
def retry_analysis(request_id: str) -> Dict[str, Any]:
    data = get_request(request_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Analysis request not found")
    update_request_status(request_id, "pending", 0, error_message=None)
    task = run_analysis.apply_async(args=[request_id, data])
    return {"task_id": task.id, "status": "queued", "request_id": request_id}
