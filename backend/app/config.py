"""
إعدادات المشروع - تُقرأ من ملف .env

كل القيم لها قيم افتراضية معقولة بحيث يمكن تشغيل المشروع بدون .env
أثناء التطوير، باستثناء مفاتيح Supabase التي يجب توفيرها يدوياً.
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Supabase ----------
    supabase_url: str = ""
    supabase_service_key: str = ""

    # ---------- Redis / Celery ----------
    redis_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ---------- App ----------
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # ---------- Polling ----------
    poll_interval_seconds: int = 30
    enable_polling: bool = True

    # ---------- Limits ----------
    max_posts_per_analysis: int = 20_000
    max_rows_per_dataset: int = 200_000
    min_posts_threshold: int = 20

    # ---------- PySpark ----------
    spark_app_name: str = "InsightHub"
    spark_master: str = "local[*]"
    spark_driver_memory: str = "2g"
    spark_executor_memory: str = "2g"
    spark_default_parallelism: int = 4

    # ---------- HuggingFace ----------
    huggingface_token: str = ""

    # ---------- NLP ----------
    sentiment_model: str = "CAMeL-Lab/bert-base-arabic-camelbert-da-sentiment"
    nlp_device: str = "cpu"
    sentiment_batch_size: int = 32

    # ---------- CORS ----------
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
