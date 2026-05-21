---
title: InsightHub Backend
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: تحليل وسائل التواصل الاجتماعي العربية بـ PySpark + CAMeL-BERT
---

<div dir="rtl">

# InsightHub Backend

منصّة تحليل وسائل التواصل الاجتماعي - خدمة الـ Backend المنشورة على Hugging Face Spaces.

تسحب الخدمة datasets عربية مفتوحة من HuggingFace **بدون تخزينها محلياً**، وتُحلّلها باستخدام **PySpark + Transformers (CAMeL-BERT)**، ثم تحفظ النتائج فقط في **Supabase** لكي يقرأها الـ Frontend مباشرة.

---

## المعمارية

```
┌──────────────┐                        ┌────────────────┐
│   Netlify    │ ─── يكتب طلب ────────►│   Supabase     │
│  (Frontend)  │                        │  PostgreSQL    │
│  HTML/JS     │ ◄── يقرأ النتائج ─────│                │
└──────────────┘                        └───────┬────────┘
                                                │ polling
                                                │  كل 30s
                                                ▼
                              ┌──────────────────────────────┐
                              │   HuggingFace Space          │
                              │   FastAPI + PySpark + Torch  │
                              │   + BackgroundTasks runner   │
                              └──────────┬───────────────────┘
                                         │
                                  HF Hub Streaming
                                         │
                                         ▼
                              [ 8 datasets عربية، 1.2M+ منشور ]
```

---

## النشر على Hugging Face Spaces (خطوة بخطوة)

### 1. إنشاء Space جديد

اذهب إلى https://huggingface.co/new-space واملأ:

| الحقل | القيمة |
|---|---|
| **Owner** | حسابك |
| **Space name** | `insighthub-backend` |
| **License** | MIT |
| **Select the Space SDK** | **Docker** (اختر Blank template) |
| **Space hardware** | CPU basic - free (16 GB RAM) |
| **Visibility** | Public |

اضغط **Create Space**.

### 2. رفع الكود

عندك خياران:

#### الخيار A: Git push مباشر
```bash
# في حاسوبك بعد سحب فرع الـ PR
cd insighthub/backend
git init
git remote add hf https://huggingface.co/spaces/USERNAME/insighthub-backend
git add .
git commit -m "initial deploy"
git push hf main:main
# سيطلب username + token
# token من https://huggingface.co/settings/tokens (نوع write)
```

#### الخيار B: ربط GitHub
في صفحة الـ Space، اضغط **Settings** → **Linked Repositories** → اربط GitHub repo. اختر مجلد `backend/` فقط.

### 3. ضبط المتغيّرات السرّية

في صفحة الـ Space اضغط **Settings** → **Variables and secrets**:

| النوع | الاسم | القيمة |
|---|---|---|
| Secret | `SUPABASE_URL` | `https://mckhttjxpflppzndoavy.supabase.co` |
| Secret | `SUPABASE_SERVICE_KEY` | service_role من Supabase Dashboard |
| Variable | `CORS_ORIGINS` | `https://magnificent-smakager-e0e69f.netlify.app` |
| Variable | `NLP_DEVICE` | `cpu` |
| Variable | `MAX_POSTS_PER_ANALYSIS` | `10000` |

### 4. الانتظار

سترى في تبويب **Logs** مراحل البناء:
1. Building Docker image (~5 دقائق أول مرة)
2. Installing Python deps (~3 دقائق)
3. Starting uvicorn

عند ظهور `Application startup complete` الخدمة جاهزة على:
```
https://USERNAME-insighthub-backend.hf.space
```

### 5. ربط الـ Frontend

في ملفات `frontend/*.html` أضف ثابتاً:
```javascript
const BACKEND_URL = 'https://USERNAME-insighthub-backend.hf.space';
```

(الـ polling loop سيلتقط الطلبات تلقائياً، لكن يُفضّل استدعاء `/api/v1/analysis/trigger` بعد إنشاء طلب جديد للسرعة)

---

## بنية المشروع

```
backend/
├── main.py                    # FastAPI + lifespan polling
├── requirements.txt           # PySpark + Transformers
├── Dockerfile                 # HF Spaces compatible
├── .env.example               # نموذج للمتغيّرات
├── README.md                  # هذا الملف (مع HF frontmatter)
│
└── app/
    ├── config.py              # pydantic-settings
    │
    ├── api/
    │   ├── analysis.py        # /trigger /status /retry
    │   ├── results.py         # GET نتائج
    │   └── datasets.py        # قائمة datasets المتاحة
    │
    ├── database/
    │   ├── supabase_client.py # CRUD على Supabase
    │   └── models.py          # Pydantic models
    │
    ├── workers/
    │   ├── runner.py          # تحكم بالتوازي + claim/release
    │   └── analysis_worker.py # pipeline 11 خطوة
    │
    ├── datasets/              # سحب datasets بدون تخزين
    │   ├── registry.py        # 8 datasets عربية
    │   ├── base_loader.py
    │   ├── huggingface_loader.py
    │   ├── url_loader.py
    │   └── stream_manager.py
    │
    ├── spark/                 # PySpark
    │   ├── session.py
    │   ├── filters.py
    │   └── aggregations.py
    │
    ├── processors/            # تنظيف وتطبيع
    │   ├── cleaner.py
    │   ├── normalizer.py
    │   └── deduplicator.py
    │
    └── analyzers/             # NLP
        ├── sentiment_analyzer.py
        ├── topic_modeler.py
        ├── influencer_detector.py
        ├── network_analyzer.py
        └── report_generator.py
```

---

## الـ Datasets المسجَّلة (1.2M+ منشور عربي)

| ID | الاسم | الحجم | المجال |
|---|---|---|---|
| `ajgt` | تغريدات أردنية | 1,800 | تواصل |
| `arabic_sentiment_corpus` | تغريدات عربية | 58,000 | تواصل |
| `metooma` | تغريدات عربية متنوعة | 10,000 | تواصل |
| `hard` | تقييمات فنادق | 370,000 | تقييمات |
| `labr` | تقييمات كتب | 63,000 | تقييمات |
| `brad` | تقييمات كتب موسّع | 510,000 | تقييمات |
| `oclar` | تقييمات لبنانية | 3,900 | تقييمات |
| `sanad` | مقالات إخبارية | 190,000 | أخبار |

لإضافة dataset جديد، أضف عنصراً في `app/datasets/registry.py`.

---

## نقاط الواجهة

```http
GET  /                              معلومات الخدمة
GET  /health                        فحص صحة + توفر Spark/Supabase
GET  /docs                          Swagger UI

POST /api/v1/analysis/trigger       تشغيل تحليل لطلب موجود
GET  /api/v1/analysis/{id}/status   حالة التحليل
GET  /api/v1/analysis/pending       طلبات pending
POST /api/v1/analysis/{id}/retry    إعادة تشغيل طلب فشل

GET  /api/v1/results/{id}           نتائج التحليل (متى جاهزة)

GET  /api/v1/datasets               قائمة datasets المتاحة
GET  /api/v1/datasets/{id}          تفاصيل dataset
```

---

## تدفق العمل (Pipeline)

عند إنشاء طلب جديد:

```
1.  Frontend ينشئ صفاً في analysis_requests (status=pending)
2.  Polling loop داخل HF Space يلاحظ الطلب → يستدعي runner
3.  Runner يحجز slot التوازي (واحد في المرة)
4.  Worker يبدأ:
    [10%]  set status = collecting
    [25%]  StreamManager يسحب من HuggingFace (streaming، بدون تخزين)
    [35%]  Cleaner ينظّف النصوص + يستخرج mentions/hashtags
    [45%]  PySpark filtering: keywords + date + dedup
    [55%]  Sentiment Analysis (CAMeL-BERT)
    [70%]  Topic Modeling (TF-IDF)
    [80%]  Influencer Detection
    [88%]  Network Analysis (NetworkX)
    [95%]  Summary + Recommendations
    [100%] حفظ في analysis_results + إنشاء notification
5.  Frontend يلاحظ التحديث ويعرض النتائج
```

---

## التشغيل المحلي للتطوير

```bash
# يحتاج Java 17 + Python 3.11
sudo apt-get install openjdk-17-jre-headless    # Linux
brew install openjdk@17                          # macOS

cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # املأ SUPABASE_SERVICE_KEY

uvicorn main:app --reload --port 8000
```

ثم افتح http://localhost:8000/docs

---

## ملاحظات تقنية

### حول الذاكرة
- HF Spaces المجاني = 16 GB RAM (كافي جداً)
- CAMeL-BERT يحجز ~1.5 GB (يُحمَّل مرة واحدة عند أول طلب)
- PySpark يحجز ~1.5 GB (driver + executor)
- الذاكرة المتاحة للبيانات بعد ذلك: ~13 GB

### حول الأداء
- أول طلب بطيء (تحميل النموذج من HF) ~60 ثانية
- الطلبات اللاحقة (نفس process): ~30-90 ثانية حسب حجم البيانات
- HF Spaces لا ينام مع CPU basic - يبقى جاهزاً

### حول الـ Datasets
- معظم الـ datasets العربية المعلَّمة لا تحوي timestamps أو user metadata
- عند غيابها، الـ pipeline يتجاوز فلترة التاريخ ويُرجع شبكة فارغة
- النتائج الأساسية (sentiment + topics) تعمل دائماً

### حول الـ CORS
عدّل `CORS_ORIGINS` في إعدادات الـ Space ليشمل دومين Netlify الخاص بك:
```
CORS_ORIGINS=https://magnificent-smakager-e0e69f.netlify.app,http://localhost:3000
```

---

## استكشاف الأخطاء

| المشكلة | الحل |
|---|---|
| Build فشل بسبب timeout | HF يبني صورة كبيرة - أعد المحاولة، وفي المرة الثانية يستخدم cache |
| `JAVA_HOME not set` | تأكد أن `Dockerfile` يُثبّت `openjdk-17-jre-headless` |
| 503 على أول طلب | النموذج يُحمَّل، انتظر 60 ثانية وأعد |
| `Connection refused 6379` | Redis ليس مطلوباً في هذه النسخة، تجاهل |
| الـ Space "Sleeping" | في الـ free CPU، الـ Space يبقى نشطاً، لكن قد يدخل sleep بعد عدم استخدام طويل |
| Frontend يفشل CORS | تأكد من إضافة دومين Netlify في `CORS_ORIGINS` |

---

## الترخيص

MIT - مشروع ماستر تحليل البيانات الضخمة، جامعة الجزائر.

</div>
