"""
Pydantic models لجداول Supabase.

تستخدم للتحقق من البيانات داخل الـ API endpoints والـ workers.
الأسماء وأنواع الحقول مطابقة تماماً للـ schema في Supabase.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """صف من جدول analysis_requests."""

    id: UUID
    user_id: UUID
    title: str
    keywords: List[str]
    platforms: List[str] = Field(default_factory=lambda: ["twitter"])
    analysis_type: str  # reputation | campaign | audience | influencer | strategic
    date_from: date
    date_to: date
    status: str = "pending"
    progress: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # حقل اختياري نضيفه نحن: قائمة dataset ids للتحليل
    dataset_ids: Optional[List[str]] = None


class AnalysisResults(BaseModel):
    """صف من جدول analysis_results - الشكل المتوقع من الـ Frontend."""

    request_id: UUID
    total_posts: int = 0
    total_users: int = 0
    total_reach: int = 0
    sentiment_positive: float = 0.0
    sentiment_neutral: float = 0.0
    sentiment_negative: float = 0.0
    top_topics: List[dict] = Field(default_factory=list)
    top_influencers: List[dict] = Field(default_factory=list)
    sentiment_timeline: List[dict] = Field(default_factory=list)
    network_nodes: List[dict] = Field(default_factory=list)
    network_edges: List[dict] = Field(default_factory=list)
    summary: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)


class TriggerRequest(BaseModel):
    request_id: UUID
    user_id: Optional[UUID] = None


class StatusResponse(BaseModel):
    request_id: UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    spark_available: bool = False
    supabase_configured: bool = False


class DatasetInfo(BaseModel):
    """معلومات dataset لإرجاعها للـ Frontend."""

    id: str
    name: str
    name_ar: str
    domain: str
    source: str
    size_estimate_rows: int
    has_timestamp: bool
    has_user_metadata: bool
    has_engagement: bool
    description_ar: str = ""
    homepage: str = ""
