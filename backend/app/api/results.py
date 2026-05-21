"""
Endpoints لاسترجاع نتائج التحليل.

ملاحظة: الـ Frontend يقرأ مباشرة من Supabase، لذا هذه الـ endpoints
مفيدة فقط للاختبار من خلال curl أو لتطبيقات أخرى.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.database.supabase_client import get_request, get_results


router = APIRouter()


@router.get("/{request_id}")
def fetch_results(request_id: str) -> Dict[str, Any]:
    request = get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    results = get_results(request_id)
    if results is None:
        return {
            "request_id": request_id,
            "status": request.get("status"),
            "progress": request.get("progress"),
            "ready": False,
        }

    return {
        "request_id": request_id,
        "status": request.get("status"),
        "progress": request.get("progress"),
        "ready": True,
        "results": results,
    }
