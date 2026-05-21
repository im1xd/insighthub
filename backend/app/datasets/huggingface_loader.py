"""
HuggingFace Datasets Loader - يستخدم وضع streaming.

streaming=True يعني:
- لا تحميل كامل للـ dataset على القرص
- يجلب الصفوف batch-by-batch من HuggingFace Hub
- يقطع عند الوصول لـ max_rows
- مثالي للـ datasets الضخمة (gigabytes)

ملاحظة: بعض الـ datasets قد تتطلب trust_remote_code=True
بسبب custom loading scripts. نُمكّنها افتراضياً للـ datasets العامة.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from loguru import logger

from app.config import settings
from app.datasets.base_loader import BaseLoader, to_canonical


class HuggingFaceLoader(BaseLoader):
    """يحمّل من HuggingFace Hub بشكل streaming."""

    def stream(
        self,
        max_rows: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        # استيراد كسول لتأخير تحميل المكتبة الثقيلة
        from datasets import load_dataset

        meta = self.meta
        if meta.hf_id is None:
            raise ValueError(f"Dataset {meta.id} has no hf_id")

        limit = max_rows or settings.max_rows_per_dataset
        logger.info(
            f"[hf-loader] streaming {meta.hf_id} "
            f"(config={meta.hf_config}, split={meta.hf_split}, limit={limit})"
        )

        kwargs: Dict[str, Any] = {
            "path": meta.hf_id,
            "split": meta.hf_split,
            "streaming": True,
            "trust_remote_code": True,
        }
        if meta.hf_config:
            kwargs["name"] = meta.hf_config
        if settings.huggingface_token:
            kwargs["token"] = settings.huggingface_token

        try:
            ds = load_dataset(**kwargs)
        except Exception as e:
            logger.error(f"[hf-loader] failed to load {meta.hf_id}: {e}")
            raise

        emitted = 0
        for raw in ds:
            canonical = to_canonical(raw, meta)
            if canonical is None:
                continue
            yield canonical
            emitted += 1
            if emitted >= limit:
                logger.info(f"[hf-loader] reached limit {limit} for {meta.id}")
                break

        logger.info(f"[hf-loader] emitted {emitted} rows from {meta.id}")
