"""
URL Loader - يقرأ مباشرة من رابط HTTP/HTTPS.

يدعم:
- CSV  (مع أو بدون gzip)
- JSONL (سطر JSON واحد لكل صف)
- Parquet (يقرأ بـ pyarrow)

البيانات تُقرأ بشكل streaming قدر الإمكان لتقليل استهلاك الذاكرة.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from typing import Any, Dict, Iterator, Optional

import httpx
from loguru import logger

from app.config import settings
from app.datasets.base_loader import BaseLoader, to_canonical


class URLLoader(BaseLoader):
    def stream(
        self,
        max_rows: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        meta = self.meta
        if not meta.url:
            raise ValueError(f"Dataset {meta.id} has no URL")

        limit = max_rows or settings.max_rows_per_dataset
        fmt = (meta.file_format or "").lower()
        logger.info(f"[url-loader] streaming {meta.url} as {fmt} (limit={limit})")

        if fmt == "csv":
            yield from self._stream_csv(limit)
        elif fmt == "jsonl":
            yield from self._stream_jsonl(limit)
        elif fmt == "parquet":
            yield from self._stream_parquet(limit)
        else:
            raise ValueError(f"Unsupported file_format: {fmt}")

    # ---------- CSV ----------
    def _stream_csv(self, limit: int) -> Iterator[Dict[str, Any]]:
        with httpx.stream("GET", self.meta.url, timeout=120.0, follow_redirects=True) as r:
            r.raise_for_status()
            raw = r.iter_bytes()
            stream: io.IOBase
            if self.meta.url.endswith(".gz"):
                buf = io.BytesIO(b"".join(raw))
                stream = gzip.GzipFile(fileobj=buf, mode="rb")
            else:
                stream = io.BytesIO(b"".join(raw))

            text_stream = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream)
            yield from self._emit(reader, limit)

    # ---------- JSONL ----------
    def _stream_jsonl(self, limit: int) -> Iterator[Dict[str, Any]]:
        with httpx.stream("GET", self.meta.url, timeout=120.0, follow_redirects=True) as r:
            r.raise_for_status()
            buffer = b""
            count = 0
            for chunk in r.iter_bytes():
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    canonical = to_canonical(raw, self.meta)
                    if canonical is None:
                        continue
                    yield canonical
                    count += 1
                    if count >= limit:
                        return

    # ---------- Parquet ----------
    def _stream_parquet(self, limit: int) -> Iterator[Dict[str, Any]]:
        # parquet يحتاج تحميل كامل للملف (متعدد الـ row groups)
        # نستخدم pyarrow لقراءة في batches
        import pyarrow.parquet as pq

        with httpx.stream("GET", self.meta.url, timeout=300.0, follow_redirects=True) as r:
            r.raise_for_status()
            data = r.read()

        buf = io.BytesIO(data)
        table = pq.read_table(buf)
        count = 0
        for batch in table.to_batches(max_chunksize=1000):
            for raw in batch.to_pylist():
                canonical = to_canonical(raw, self.meta)
                if canonical is None:
                    continue
                yield canonical
                count += 1
                if count >= limit:
                    return

    # ---------- helper ----------
    def _emit(self, iterable, limit: int) -> Iterator[Dict[str, Any]]:
        count = 0
        for raw in iterable:
            canonical = to_canonical(dict(raw), self.meta)
            if canonical is None:
                continue
            yield canonical
            count += 1
            if count >= limit:
                return
