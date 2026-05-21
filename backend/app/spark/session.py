"""
SparkSession Manager - singleton مع Lazy initialization.

PySpark غالي التهيئة (يحتاج JVM)، لذا نُهيِّئه مرة واحدة لكل process
ونعيد استخدامه. يستفيد منه workers الـ Celery عبر إعادة استخدام
نفس الـ JVM للـ tasks المتعاقبة.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from app.config import settings


_session = None


def get_spark():
    """يُنشئ أو يعيد SparkSession موحَّد."""
    global _session
    if _session is not None:
        return _session

    # استيراد كسول لتأخير تحميل JVM
    from pyspark.sql import SparkSession

    logger.info(
        f"[spark] starting session: app={settings.spark_app_name}, "
        f"master={settings.spark_master}, "
        f"driver_mem={settings.spark_driver_memory}, "
        f"parallelism={settings.spark_default_parallelism}"
    )

    builder = (
        SparkSession.builder.appName(settings.spark_app_name)
        .master(settings.spark_master)
        .config("spark.driver.memory", settings.spark_driver_memory)
        .config("spark.executor.memory", settings.spark_executor_memory)
        .config("spark.default.parallelism", str(settings.spark_default_parallelism))
        .config("spark.sql.shuffle.partitions", str(settings.spark_default_parallelism))
        # تقليل ضوضاء logs
        .config("spark.ui.showConsoleProgress", "false")
        # السماح بـ pyarrow للتحويل السريع pandas <-> spark
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        # دعم UTF-8 الكامل للنصوص العربية
        .config("spark.driver.extraJavaOptions", "-Dfile.encoding=UTF-8")
    )

    _session = builder.getOrCreate()
    _session.sparkContext.setLogLevel("WARN")
    logger.info("[spark] session ready")
    return _session


def stop_spark() -> None:
    """يوقف الـ session - يُستدعى عند إنهاء العامل."""
    global _session
    if _session is not None:
        try:
            _session.stop()
        finally:
            _session = None
            logger.info("[spark] session stopped")
