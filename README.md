<div dir="rtl">

# InsightHub

منصّة تحليل وسائل التواصل الاجتماعي - مشروع ماستر تحليل البيانات الضخمة، جامعة الجزائر.

## بنية المستودع

```
insighthub/
├── frontend/       # 3 صفحات HTML (Landing + User + Admin Dashboards)
└── backend/        # FastAPI + PySpark + Transformers (HF Space)
```

## النشر

| الجزء | المنصة | التكلفة |
|---|---|---|
| Frontend | Netlify (موجود) | مجاني |
| Backend | Hugging Face Spaces (Docker SDK، CPU basic) | مجاني |
| Database | Supabase | مجاني (Free tier) |

### نشر الـ Frontend
ارفع محتوى `frontend/` على Netlify (أو أي CDN ثابت).

### نشر الـ Backend
انظر [backend/README.md](./backend/README.md) - الخطوات التفصيلية لنشره على Hugging Face Spaces.

ملخص:
1. أنشئ Space جديد على https://huggingface.co/new-space باختيار **Docker SDK**
2. ادفع محتوى `backend/` إلى الـ Space repo
3. اضبط المتغيّرات السرّية: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CORS_ORIGINS`
4. الـ URL سيكون: `https://USERNAME-insighthub-backend.hf.space`
5. عدّل ملفات HTML ليستخدما هذا الرابط

## التقنيات

| طبقة | الأداة |
|---|---|
| Frontend | HTML/JS + Tailwind + Chart.js |
| Database | Supabase (PostgreSQL + REST) |
| API | FastAPI + uvicorn |
| Async | FastAPI BackgroundTasks (لا Celery، لا Redis) |
| Big Data | PySpark 3.5 |
| NLP | HuggingFace Transformers + CAMeL-BERT العربي |
| Datasets | 8 مجاميع عربية مفتوحة (1.2M+ منشور) |

## الميزات

- ✅ سحب datasets عربية بدون تخزين محلي (streaming من HF Hub)
- ✅ تحليل المشاعر بـ CAMeL-BERT (دارجة عربية)
- ✅ استخراج المواضيع بـ TF-IDF
- ✅ اكتشاف المؤثرين (heuristic مع fallback)
- ✅ تحليل شبكة التفاعلات (NetworkX)
- ✅ توليد ملخص + توصيات عربية
- ✅ مراقبة التقدّم في الزمن الحقيقي

</div>
