"""
تجميعات Spark - حساب الإحصائيات الكلية بشكل موزَّع.

تُستخدم بعد الفلترة لحساب:
- total_posts, total_users, total_reach
- توزيع المنصات
- إحصائيات بسيطة للـ dataset_breakdown
"""

from __future__ import annotations

from typing import Any, Dict


def compute_overall_stats(df) -> Dict[str, Any]:
    """يحسب الإحصائيات الإجمالية على Spark DataFrame."""
    from pyspark.sql.functions import countDistinct, sum as spark_sum

    if df is None:
        return {"total_posts": 0, "total_users": 0, "total_reach": 0}

    total_posts = df.count()
    if total_posts == 0:
        return {"total_posts": 0, "total_users": 0, "total_reach": 0}

    row = df.agg(
        countDistinct("user_id").alias("uniq_users"),
        spark_sum("user_followers").alias("reach"),
        spark_sum("likes").alias("likes"),
        spark_sum("retweets").alias("retweets"),
        spark_sum("replies").alias("replies"),
    ).collect()[0]

    uniq_users = int(row["uniq_users"] or 0)
    reach = int(row["reach"] or 0)

    # إذا لم يكن هناك user_id، نستخدم total_posts كمؤشر تقريبي
    if uniq_users == 0:
        uniq_users = total_posts

    # إذا لم يكن هناك followers، نقدّر reach من likes+retweets
    if reach == 0:
        likes = int(row["likes"] or 0)
        retweets = int(row["retweets"] or 0)
        replies = int(row["replies"] or 0)
        reach = (likes + retweets + replies) * 10  # تقدير محافظ

    return {
        "total_posts": int(total_posts),
        "total_users": uniq_users,
        "total_reach": reach,
    }


def dataset_breakdown(df) -> Dict[str, int]:
    """عدد الصفوف من كل dataset بعد الفلترة."""
    if df is None:
        return {}
    rows = df.groupBy("source_dataset").count().collect()
    return {r["source_dataset"]: int(r["count"]) for r in rows if r["source_dataset"]}
