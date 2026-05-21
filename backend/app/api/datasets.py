"""
Endpoints لاستعراض الـ datasets المتاحة.

GET /api/v1/datasets         - قائمة الـ datasets (للـ Frontend dropdown)
GET /api/v1/datasets/{id}    - تفاصيل dataset واحد
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.datasets.registry import get_dataset, list_datasets


router = APIRouter()


def _serialize(meta) -> Dict[str, Any]:
    return {
        "id": meta.id,
        "name": meta.name,
        "name_ar": meta.name_ar,
        "domain": meta.domain.value,
        "source": meta.source.value,
        "size_estimate_rows": meta.size_estimate_rows,
        "has_timestamp": meta.has_timestamp,
        "has_user_metadata": meta.has_user_metadata,
        "has_engagement": meta.has_engagement,
        "language": meta.language,
        "license": meta.license,
        "description_ar": meta.description_ar,
        "homepage": meta.homepage,
    }


@router.get("")
def list_all() -> List[Dict[str, Any]]:
    return [_serialize(m) for m in list_datasets()]


@router.get("/{dataset_id}")
def get_one(dataset_id: str) -> Dict[str, Any]:
    meta = get_dataset(dataset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _serialize(meta)
