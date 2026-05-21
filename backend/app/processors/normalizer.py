"""
تطبيع النصوص العربية - بدون فقدان معلومات لازمة للـ NLP.

ملاحظة مهمة: التطبيع الذي يستخدمه نموذج المشاعر (CAMeL-BERT) داخلي
في الـ tokenizer، لذلك لا يجب الإفراط في التطبيع قبل التمرير للنموذج.
الدالة هنا للتطبيع الخاص بـ:
- إزالة المكررات (نفس النص بتشكيل مختلف يُعتبر نفس الشيء)
- topic modeling (تجميع الكلمات المتشابهة)
- البحث بالكلمات المفتاحية
"""

from __future__ import annotations

import re
import unicodedata


# الحركات والتشكيل العربي
ARABIC_DIACRITICS = re.compile(
    "[" "\u064B-\u065F"  # تنوين، فتحة، ضمة، كسرة، شدة، سكون...
    "\u0670"            # ألف خنجرية
    "\u0640"            # تطويل
    "]"
)

# توحيد الهمزات والياء والتاء المربوطة
LETTER_REPLACEMENTS = {
    "\u0623": "\u0627",  # أ -> ا
    "\u0625": "\u0627",  # إ -> ا
    "\u0622": "\u0627",  # آ -> ا
    "\u0671": "\u0627",  # ٱ -> ا
    "\u0629": "\u0647",  # ة -> ه
    "\u0649": "\u064A",  # ى -> ي
    "\u0624": "\u0648",  # ؤ -> و
    "\u0626": "\u064A",  # ئ -> ي
}

# الأرقام العربية والهندية
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def remove_diacritics(text: str) -> str:
    if not text:
        return ""
    return ARABIC_DIACRITICS.sub("", text)


def normalize_letters(text: str) -> str:
    if not text:
        return ""
    return "".join(LETTER_REPLACEMENTS.get(c, c) for c in text)


def normalize_digits(text: str) -> str:
    if not text:
        return ""
    return text.translate(ARABIC_INDIC_DIGITS)


def normalize_unicode(text: str) -> str:
    """NFC للتأكد من تركيب موحد للحروف المركبة."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def normalize_for_search(text: str) -> str:
    """
    التطبيع الكامل للبحث/المقارنة - يفقد المعنى البصري لكنه مثالي للمطابقة.
    """
    s = normalize_unicode(text)
    s = remove_diacritics(s)
    s = normalize_letters(s)
    s = normalize_digits(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def normalize_for_display(text: str) -> str:
    """تطبيع خفيف يحافظ على النص العربي مقروءاً."""
    s = normalize_unicode(text)
    s = re.sub(r"\s+", " ", s).strip()
    return s
