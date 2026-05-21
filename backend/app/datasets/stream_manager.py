"""
StreamManager - منسّق التحميل من المصادر المختلفة.

الفائدة:
- يُخفي تفاصيل الـ source خلف واجهة موحدة
- يدعم التحميل من عدة datasets في نفس الطلب
- يُطبّق حد أقصى عام (max_rows_per_analysis) لمنع تجاوز الذاكرة
- يُعيد iterator واحد يجمع كل الصفوف من كل الـ datasets المختارة

الاستخدام:
    manager = StreamManager()
    for row in manager.stream_many(["ajgt", "metooma"], max_total_rows=50000):
        process(row)
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from loguru import logger

from app.config import settings
from app.datasets.base_loader import BaseLoader
from app.datasets.huggingface_loader import HuggingFaceLoader
from app.datasets.registry import (
    DatasetMeta,
    DatasetSource,
    default_dataset_ids,
    get_dataset,
)
from app.datasets.url_loader import URLLoader


def loader_for(meta: DatasetMeta) -> BaseLoader:
    """Factory لاختيار الـ loader المناسب حسب المصدر."""
    if meta.source == DatasetSource.HUGGINGFACE:
        return HuggingFaceLoader(meta)
    if meta.source == DatasetSource.URL:
        return URLLoader(meta)
    raise ValueError(f"Unknown source: {meta.source}")


class StreamManager:
    def __init__(self):
        self.loaders_used: List[str] = []

    def resolve(self, dataset_ids: Optional[List[str]] = None) -> List[DatasetMeta]:
        """يحوّل قائمة ids إلى DatasetMeta، ويستخدم الافتراضي إن كانت فارغة."""
        ids = dataset_ids or default_dataset_ids()
        result: List[DatasetMeta] = []
        for did in ids:
            meta = get_dataset(did)
            if meta is None:
                logger.warning(f"[stream-manager] unknown dataset id: {did}")
                continue
            result.append(meta)
        if not result:
            raise ValueError("No valid datasets selected")
        return result

    def stream_many(
        self,
        dataset_ids: Optional[List[str]] = None,
        max_total_rows: Optional[int] = None,
        max_rows_per_dataset: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        يدمج صفوف عدة datasets في تيار واحد.

        التوزيع: نمشي round-robin غير مفروض - نأخذ صفوف من كل dataset
        على الترتيب وحتى الوصول للحد العام.
        """
        metas = self.resolve(dataset_ids)
        cap_total = max_total_rows or settings.max_posts_per_analysis
        cap_per = max_rows_per_dataset or settings.max_rows_per_dataset
        emitted_total = 0

        for meta in metas:
            if emitted_total >= cap_total:
                break
            remaining = cap_total - emitted_total
            per_cap = min(cap_per, remaining)
            self.loaders_used.append(meta.id)
            try:
                loader = loader_for(meta)
                for row in loader.stream(max_rows=per_cap):
                    yield row
                    emitted_total += 1
                    if emitted_total >= cap_total:
                        break
            except Exception as e:
                logger.error(f"[stream-manager] dataset {meta.id} failed: {e}")
                continue

        logger.info(
            f"[stream-manager] total emitted={emitted_total} "
            f"from datasets={self.loaders_used}"
        )

    def stream_to_pandas(
        self,
        dataset_ids: Optional[List[str]] = None,
        max_total_rows: Optional[int] = None,
    ):
        """مساعد لتحويل التيار إلى pandas DataFrame."""
        import pandas as pd

        rows = list(self.stream_many(dataset_ids, max_total_rows))
        return pd.DataFrame(rows)
