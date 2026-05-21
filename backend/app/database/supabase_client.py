"""
Supabase Client Wrapper - كل التفاعلات مع Supabase تمر من هنا.

يستخدم Service Role Key لتجاوز RLS أثناء معالجة الـ backend.
كل الدوال متزامنة (sync) لأن مكتبة supabase-py الحالية متزامنة،
ولأن Celery workers تعمل sync بطبيعتها.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings


_client = None


def get_client():
    """يُنشئ أو يعيد Supabase client (singleton)."""
    global _client
    if _client is not None:
        return _client

    if not settings.supabase_url or not settings.supabase_service_key:
        logger.warning(
            "[supabase] missing SUPABASE_URL or SUPABASE_SERVICE_KEY - "
            "client will not be functional"
        )
        return None

    from supabase import create_client

    _client = create_client(settings.supabase_url, settings.supabase_service_key)
    logger.info("[supabase] client initialized")
    return _client


def is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Analysis Requests
# =====================================================================

def get_pending_requests(limit: int = 20) -> List[Dict[str, Any]]:
    """يجلب الطلبات بحالة pending مرتبة حسب الأقدمية."""
    client = get_client()
    if client is None:
        return []
    try:
        resp = (
            client.table("analysis_requests")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"[supabase] get_pending_requests failed: {e}")
        return []


def get_request(request_id: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    if client is None:
        return None
    try:
        resp = (
            client.table("analysis_requests")
            .select("*")
            .eq("id", request_id)
            .single()
            .execute()
        )
        return resp.data
    except Exception as e:
        logger.error(f"[supabase] get_request({request_id}) failed: {e}")
        return None


def update_request_status(
    request_id: str,
    status: str,
    progress: int,
    error_message: Optional[str] = None,
) -> bool:
    """
    يُحدّث حالة الطلب وتقدّمه. عند status=completed يحفظ completed_at.
    """
    client = get_client()
    if client is None:
        logger.info(f"[supabase][noop] {request_id} -> {status} ({progress}%)")
        return False

    payload: Dict[str, Any] = {
        "status": status,
        "progress": progress,
        "updated_at": _now_iso(),
    }
    if error_message is not None:
        payload["error_message"] = error_message
    if status == "completed":
        payload["completed_at"] = _now_iso()
        payload["progress"] = 100

    try:
        client.table("analysis_requests").update(payload).eq("id", request_id).execute()
        logger.info(f"[supabase] request {request_id} -> {status} ({progress}%)")
        return True
    except Exception as e:
        logger.error(f"[supabase] update_request_status failed: {e}")
        return False


# =====================================================================
# Analysis Results
# =====================================================================

def save_results(request_id: str, results: Dict[str, Any]) -> bool:
    """
    يحفظ نتائج التحليل. إذا كانت موجودة مسبقاً (في حالة retry) يُحدّثها.
    """
    client = get_client()
    if client is None:
        logger.info(f"[supabase][noop] would save results for {request_id}")
        return False

    payload = {**results, "request_id": request_id}

    try:
        # نحاول delete + insert للسلامة (Supabase upsert يحتاج primary key)
        client.table("analysis_results").delete().eq("request_id", request_id).execute()
        client.table("analysis_results").insert(payload).execute()
        logger.info(f"[supabase] results saved for {request_id}")
        return True
    except Exception as e:
        logger.error(f"[supabase] save_results failed: {e}")
        return False


def get_results(request_id: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    if client is None:
        return None
    try:
        resp = (
            client.table("analysis_results")
            .select("*")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.error(f"[supabase] get_results failed: {e}")
        return None


# =====================================================================
# Notifications
# =====================================================================

def create_notification(
    user_id: str,
    title: str,
    body: str,
    notif_type: str = "analysis_complete",
    link: Optional[str] = None,
) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.table("notifications").insert({
            "user_id": user_id,
            "type": notif_type,
            "title": title,
            "body": body,
            "link": link,
            "is_read": False,
        }).execute()
        return True
    except Exception as e:
        logger.error(f"[supabase] create_notification failed: {e}")
        return False


# =====================================================================
# Audit Log
# =====================================================================

def log_audit(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    actor_id: Optional[str] = None,
) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.table("audit_logs").insert({
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
        }).execute()
        return True
    except Exception as e:
        # audit logging يجب ألا يُفشل العملية الأصلية
        logger.warning(f"[supabase] log_audit failed: {e}")
        return False
