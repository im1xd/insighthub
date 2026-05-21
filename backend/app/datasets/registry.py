"""
سجل الـ Datasets العربية المتاحة للتحليل.

كل dataset يحمل metadata تصف:
- مصدره (HuggingFace أو URL مباشر)
- الحقول المتوفرة (نص، تاريخ، مستخدم، تفاعلات)
- حدود الحجم لتفادي تحميل بيانات أكثر من اللازم

هذه القائمة قابلة للتوسعة - فقط أضف عنصر جديد للـ DATASETS list.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class DatasetSource(str, Enum):
    HUGGINGFACE = "huggingface"
    URL = "url"


class DatasetDomain(str, Enum):
    SOCIAL_MEDIA = "social_media"
    NEWS = "news"
    REVIEWS = "reviews"
    GENERAL = "general"


@dataclass(frozen=True)
class FieldMapping:
    """
    خريطة الحقول لتوحيد الـ schema بين كل الـ datasets.
    أي dataset يُحوَّل لشكل قياسي:
      text, created_at, user_id, user_handle, user_followers,
      likes, retweets, replies, lang, label
    """

    text: str
    created_at: Optional[str] = None
    user_id: Optional[str] = None
    user_handle: Optional[str] = None
    user_followers: Optional[str] = None
    likes: Optional[str] = None
    retweets: Optional[str] = None
    replies: Optional[str] = None
    lang: Optional[str] = None
    label: Optional[str] = None


@dataclass(frozen=True)
class DatasetMeta:
    id: str
    name: str
    name_ar: str
    source: DatasetSource
    domain: DatasetDomain

    # HuggingFace
    hf_id: Optional[str] = None
    hf_config: Optional[str] = None
    hf_split: str = "train"

    # URL
    url: Optional[str] = None
    file_format: Optional[str] = None  # "csv" | "jsonl" | "parquet"

    fields: FieldMapping = field(default_factory=lambda: FieldMapping(text="text"))

    # خصائص للقدرات
    has_timestamp: bool = False
    has_user_metadata: bool = False
    has_engagement: bool = False

    # حجم تقريبي وتفاصيل
    size_estimate_rows: int = 0
    language: str = "ar"
    license: str = "unknown"
    description_ar: str = ""
    homepage: str = ""

    @property
    def supports_influencers(self) -> bool:
        return self.has_user_metadata

    @property
    def supports_network(self) -> bool:
        return self.has_user_metadata

    @property
    def supports_timeline(self) -> bool:
        return self.has_timestamp

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        d["domain"] = self.domain.value
        return d


# =====================================================================
# قائمة الـ Datasets الجاهزة
#
# ملاحظات الاختيار:
# 1. كل الـ datasets عامة ولا تحتاج auth (ما عدا تلك المعلَّمة gated)
# 2. الاسم الكامل (hf_id) موثَّق على https://huggingface.co/datasets
# 3. حقول الـ FieldMapping مطابقة للـ schema الفعلي
# 4. has_timestamp/has_user_metadata/has_engagement تعكس الواقع
#    معظم الـ datasets العربية المتاحة هي labeled corpora بدون metadata
#    اجتماعية - لذلك النتائج ستركّز على المشاعر والمواضيع
# =====================================================================

DATASETS: List[DatasetMeta] = [
    # ----- 1) AJGT - Arabic Jordanian General Tweets -----
    DatasetMeta(
        id="ajgt",
        name="Arabic Jordanian General Tweets",
        name_ar="تغريدات عربية أردنية عامة",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.SOCIAL_MEDIA,
        hf_id="ajgt_twitter_ar",
        hf_split="train",
        fields=FieldMapping(text="text", label="label"),
        size_estimate_rows=1_800,
        license="Custom (research)",
        description_ar=(
            "مجموعة تغريدات أردنية معلَّمة للمشاعر "
            "(إيجابي/سلبي). صغيرة الحجم لكنها لهجة قريبة."
        ),
        homepage="https://huggingface.co/datasets/ajgt_twitter_ar",
    ),

    # ----- 2) Arabic Sentiment Twitter Corpus (arbml) -----
    DatasetMeta(
        id="arabic_sentiment_corpus",
        name="Arabic Sentiment Twitter Corpus",
        name_ar="مجمع تغريدات المشاعر العربية",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.SOCIAL_MEDIA,
        hf_id="arbml/Arabic_Sentiment_Twitter_Corpus",
        hf_split="train",
        fields=FieldMapping(text="tweet", label="label"),
        size_estimate_rows=58_000,
        license="MIT",
        description_ar=(
            "حوالي 58 ألف تغريدة عربية معلَّمة للمشاعر، "
            "مناسبة للتدريب والتقييم على نموذج المشاعر."
        ),
        homepage="https://huggingface.co/datasets/arbml/Arabic_Sentiment_Twitter_Corpus",
    ),

    # ----- 3) HARD - Hotel Arabic Reviews Dataset -----
    DatasetMeta(
        id="hard",
        name="Hotel Arabic Reviews Dataset",
        name_ar="مجمع تقييمات الفنادق العربية",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.REVIEWS,
        hf_id="hard",
        hf_split="train",
        fields=FieldMapping(text="text", label="label"),
        size_estimate_rows=370_000,
        license="Apache-2.0",
        description_ar=(
            "أكثر من 370 ألف تقييم فندق بالعربية مع نجوم. "
            "ممتاز لاختبار التحليل على بيانات حقيقية وفيرة."
        ),
        homepage="https://huggingface.co/datasets/hard",
    ),

    # ----- 4) LABR - Large Arabic Book Reviews -----
    DatasetMeta(
        id="labr",
        name="Large-scale Arabic Book Reviews",
        name_ar="مجمع تقييمات الكتب العربية الكبير",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.REVIEWS,
        hf_id="labr",
        hf_config="plain_text",
        hf_split="train",
        fields=FieldMapping(text="review", label="label"),
        size_estimate_rows=63_000,
        license="GPL-2.0",
        description_ar=(
            "63 ألف مراجعة كتاب باللغة العربية مع تقييمات. "
            "متنوع المحتوى ويغطي مواضيع كثيرة."
        ),
        homepage="https://huggingface.co/datasets/labr",
    ),

    # ----- 5) Tweets-Sentiment (arbml/tweets) -----
    DatasetMeta(
        id="metooma",
        name="Metooma Arabic Tweets",
        name_ar="تغريدات Metooma العربية",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.SOCIAL_MEDIA,
        hf_id="metooma",
        hf_split="train",
        fields=FieldMapping(text="text", label="label"),
        size_estimate_rows=10_000,
        license="Custom",
        description_ar=(
            "مجموعة تغريدات عربية متنوعة المواضيع. "
            "مفيدة لتجربة التحليل على نصوص تويتر فعلية."
        ),
        homepage="https://huggingface.co/datasets/metooma",
    ),

    # ----- 6) OCLAR - Opinion Corpus Lebanese Arabic -----
    DatasetMeta(
        id="oclar",
        name="Opinion Corpus for Lebanese Arabic Reviews",
        name_ar="مجمع آراء التقييمات اللبنانية العربية",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.REVIEWS,
        hf_id="oclar",
        hf_split="train",
        fields=FieldMapping(text="pred_0", label="pred_1"),
        size_estimate_rows=3_900,
        license="Apache-2.0",
        description_ar=(
            "مجمع تقييمات بالعامية اللبنانية. مفيد لاختبار "
            "النموذج على لهجة شامية مغايرة للفصحى."
        ),
        homepage="https://huggingface.co/datasets/oclar",
    ),

    # ----- 7) Arabic Reviews (Souq) -----
    DatasetMeta(
        id="brad",
        name="Books Reviews in Arabic Dataset",
        name_ar="مجمع تقييمات الكتب العربية الموسّع",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.REVIEWS,
        hf_id="brad",
        hf_split="train",
        fields=FieldMapping(text="review", label="rating"),
        size_estimate_rows=510_000,
        license="MIT",
        description_ar=(
            "مجمع كبير لتقييمات الكتب العربية (>500 ألف) "
            "مع تصنيفات نجمية. مناسب لإثبات قدرة Big Data."
        ),
        homepage="https://huggingface.co/datasets/brad",
    ),

    # ----- 8) Arabic News (SANAD) -----
    DatasetMeta(
        id="sanad",
        name="Single-Label Arabic News Articles",
        name_ar="مقالات إخبارية عربية مصنّفة",
        source=DatasetSource.HUGGINGFACE,
        domain=DatasetDomain.NEWS,
        hf_id="arbml/SANAD",
        hf_split="train",
        fields=FieldMapping(text="text", label="label"),
        size_estimate_rows=190_000,
        license="MIT",
        description_ar=(
            "190 ألف مقال إخباري عربي من 7 فئات. "
            "يوفّر سياقاً إخبارياً للكلمات المفتاحية."
        ),
        homepage="https://huggingface.co/datasets/arbml/SANAD",
    ),
]


# =====================================================================
# دوال البحث والوصول
# =====================================================================

_BY_ID: Dict[str, DatasetMeta] = {d.id: d for d in DATASETS}


def get_dataset(dataset_id: str) -> Optional[DatasetMeta]:
    """يرجع dataset بالـ id، أو None إن لم يوجد."""
    return _BY_ID.get(dataset_id)


def list_datasets(
    domain: Optional[DatasetDomain] = None,
    source: Optional[DatasetSource] = None,
    only_with_timestamp: bool = False,
    only_with_user_metadata: bool = False,
) -> List[DatasetMeta]:
    """يرجع كل الـ datasets المتاحة مع فلترة اختيارية."""
    items = list(DATASETS)
    if domain:
        items = [d for d in items if d.domain == domain]
    if source:
        items = [d for d in items if d.source == source]
    if only_with_timestamp:
        items = [d for d in items if d.has_timestamp]
    if only_with_user_metadata:
        items = [d for d in items if d.has_user_metadata]
    return items


def default_dataset_ids() -> List[str]:
    """
    الـ datasets الافتراضية إذا لم يحدد المستخدم. نختار الأخف
    والأكثر تنوعاً لتجربة سريعة وموثوقة.
    """
    return ["ajgt", "arabic_sentiment_corpus", "metooma"]


def datasets_by_domain(domain: DatasetDomain) -> List[DatasetMeta]:
    return list_datasets(domain=domain)
