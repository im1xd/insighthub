# =====================================================================
# Dockerfile لـ Hugging Face Spaces (sdk: docker)
#
# ملاحظة: لا تحتاج لتشغيل هذا الـ Dockerfile محلياً. HF Spaces يبنيه
# تلقائياً عند كل push. تطلق فقط `git push` ويعمل.
#
# المتطلبات الخاصة بـ HF Spaces:
#  - المستخدم غير root (UID 1000) - سياسة أمان HF
#  - المنفذ 7860 افتراضي
#  - الذاكرة المخصّصة على cpu-basic: 16 GB (مجاني)
# =====================================================================

FROM python:3.11-slim

# Java 17 لـ PySpark + curl/git لتحميل النماذج
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# مستخدم غير root كما تطلب HF Spaces
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# تثبيت الاعتماديات أولاً للاستفادة من docker layer caching
COPY --chown=user:user requirements.txt .
USER user
RUN pip install --upgrade pip --user && pip install --user --no-cache-dir -r requirements.txt

# نسخ بقية الكود
COPY --chown=user:user . .

ENV PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/tmp/hf_cache \
    TRANSFORMERS_CACHE=/tmp/hf_cache \
    HF_DATASETS_CACHE=/tmp/hf_cache/datasets \
    PORT=7860

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
