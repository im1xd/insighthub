"""
PySpark Filters - فلترة الـ DataFrame بالكلمات المفتاحية والتاريخ.

نُجري هنا أثقل عملية في الـ pipeline على Spark:
- توحيد النص العربي (أحرف الهمزة، التشكيل)
- البحث عن أي keyword (case/diacritic insensitive)
- فلترة بالتاريخ إن وُجد عمود created_at
- إزالة المكررات بناءً على hash النص

النتيجة: DataFrame مفلتر يحتوي فقط على المنشورات ذات الصلة.
"""

from __future__ import annotations

from typing import List, Optional


# الحقول الأساسية في الـ DataFrame القياسي
SCHEMA_FIELDS = [
    "text", "created_at", "user_id", "user_handle", "user_followers",
    "likes", "retweets", "replies", "lang", "label", "source_dataset",
]


def build_dataframe_from_rows(rows: List[dict]):
    """يحوّل قائمة rows إلى Spark DataFrame مع schema موحَّد."""
    from pyspark.sql.types import (
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    from app.spark.session import get_spark

    spark = get_spark()
    schema = StructType([
        StructField("text",           StringType(),  True),
        StructField("created_at",     StringType(),  True),
        StructField("user_id",        StringType(),  True),
        StructField("user_handle",    StringType(),  True),
        StructField("user_followers", IntegerType(), True),
        StructField("likes",          IntegerType(), True),
        StructField("retweets",       IntegerType(), True),
        StructField("replies",        IntegerType(), True),
        StructField("lang",           StringType(),  True),
        StructField("label",          StringType(),  True),
        StructField("source_dataset", StringType(),  True),
    ])

    # ضمان أن كل صف يحتوي كل المفاتيح ومن النوع الصحيح
    normalized = []
    for r in rows:
        normalized.append({
            "text": str(r.get("text") or ""),
            "created_at": _to_str(r.get("created_at")),
            "user_id": _to_str(r.get("user_id")),
            "user_handle": _to_str(r.get("user_handle")),
            "user_followers": _to_int(r.get("user_followers")),
            "likes": _to_int(r.get("likes")),
            "retweets": _to_int(r.get("retweets")),
            "replies": _to_int(r.get("replies")),
            "lang": _to_str(r.get("lang")),
            "label": _to_str(r.get("label")),
            "source_dataset": _to_str(r.get("source_dataset")),
        })
    return spark.createDataFrame(normalized, schema=schema)


def _to_str(v):
    if v is None:
        return None
    return str(v)


def _to_int(v):
    if v is None:
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


# =====================================================================
# UDF: تطبيع عربي للبحث (لا يعدّل النص الأصلي - فقط لمطابقة الكلمات)
# =====================================================================

def _arabic_search_normalize(text: Optional[str]) -> str:
    """تطبيع نص عربي لمقارنة آمنة (يُستخدم داخل UDF)."""
    if not text:
        return ""
    s = text
    # إزالة التشكيل
    diacritics = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670"
    s = "".join(c for c in s if c not in diacritics)
    # توحيد الهمزات
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    return s.lower()


def filter_by_keywords(df, keywords: List[str]):
    """
    يُبقي فقط الصفوف التي تحتوي على إحدى الكلمات المفتاحية.
    المقارنة تتم على نسخة مُطبَّعة (بدون تشكيل، بدون أحرف همزة منفصلة).
    """
    if not keywords:
        return df

    from pyspark.sql.functions import udf
    from pyspark.sql.types import BooleanType

    norm_kws = [_arabic_search_normalize(k) for k in keywords if k and k.strip()]
    if not norm_kws:
        return df

    def matches(text: Optional[str]) -> bool:
        norm = _arabic_search_normalize(text)
        return any(kw in norm for kw in norm_kws)

    matches_udf = udf(matches, BooleanType())
    return df.filter(matches_udf(df["text"]))


def filter_by_date_range(df, date_from: Optional[str], date_to: Optional[str]):
    """
    يُبقي الصفوف ضمن النطاق الزمني. إذا الـ dataset لا يحتوي على
    created_at (أو كل القيم null)، نُرجع df كما هو دون فلترة.
    """
    from pyspark.sql.functions import col, to_date

    if not date_from and not date_to:
        return df

    # تحقق إن كان عمود created_at يحتوي بيانات
    non_null = df.filter(col("created_at").isNotNull()).limit(1).count()
    if non_null == 0:
        return df  # الـ dataset بدون تواريخ - نتخطى الفلترة

    # نحوّل إلى تاريخ ونُقارن
    df = df.withColumn("_date", to_date(col("created_at")))
    if date_from:
        df = df.filter((col("_date") >= date_from) | col("_date").isNull())
    if date_to:
        df = df.filter((col("_date") <= date_to) | col("_date").isNull())
    return df.drop("_date")


def deduplicate_by_text_hash(df):
    """يزيل التكرار النصي (نفس النص بعد التطبيع)."""
    from pyspark.sql.functions import sha2, udf
    from pyspark.sql.types import StringType

    norm_udf = udf(_arabic_search_normalize, StringType())
    return (
        df.withColumn("_norm", norm_udf(df["text"]))
        .withColumn("_hash", sha2(df["text"], 256))
        .dropDuplicates(["_hash"])
        .drop("_norm", "_hash")
    )


def apply_full_filter(
    df,
    keywords: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    deduplicate: bool = True,
):
    """تشغيل سلسلة الفلاتر الكاملة على الـ DataFrame."""
    if deduplicate:
        df = deduplicate_by_text_hash(df)
    df = filter_by_keywords(df, keywords)
    df = filter_by_date_range(df, date_from, date_to)
    return df
