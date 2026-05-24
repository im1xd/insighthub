<div dir="rtl">

# InsightHub

منصّة تحليل وسائل التواصل الاجتماعي العربية - مشروع ماستر تحليل البيانات الضخمة، جامعة الجزائر.

## بنية المستودع

```
insighthub/
├── netlify.toml    # ⚙️ إعدادات نشر الـ Frontend على Netlify
├── frontend/       # 3 صفحات HTML (Landing + User + Admin Dashboards)
└── backend/        # FastAPI + PySpark + Transformers (HF Space)
```

## النشر

| الجزء | المنصة | الطريقة | التكلفة |
|---|---|---|---|
| Frontend | Netlify | استيراد من GitHub | مجاني |
| Backend | Hugging Face Spaces | Docker SDK من GitHub | مجاني |
| Database | Supabase | Free tier | مجاني |

---

## الجزء الأول: نشر الـ Frontend على Netlify (من GitHub)

نعم، Netlify يدعم الاستيراد من GitHub بشكل كامل، وهي الطريقة الأفضل لأنها تُعيد النشر تلقائياً عند كل `git push`.

### الخطوات

1. اذهب إلى https://app.netlify.com وسجّل دخول (يُفضّل بحساب GitHub)
2. اضغط **Add new site** → **Import an existing project**
3. اختر **Deploy with GitHub** ثم وافق على الصلاحيات
4. اختر مستودع `im1xd/insighthub`
5. ستظهر صفحة الإعدادات - **لا تغيّر شيئاً**، الـ `netlify.toml` يحتوي كل شيء:
   - **Build command:** (فارغ)
   - **Publish directory:** `frontend`
6. اضغط **Deploy site**

سينشر Netlify الموقع خلال ~30 ثانية، وتحصل على رابط مثل `https://random-name-123.netlify.app`.

### تخصيص الدومين (اختياري)
- في **Site settings** → **Domain management** → **Options** → **Edit site name**
- مثلاً: `insighthub-dz.netlify.app`

### الاستفادة من Auto-Deploy
بعد الربط، أي `git push` على فرع `main` سينتج عنه نشر تلقائي خلال دقيقة. لا يلزم رفع ملفات يدوياً بعد الآن.

---

## الجزء الثاني: نشر الـ Backend على Hugging Face Spaces

التفاصيل الكاملة في [backend/README.md](./backend/README.md).

ملخّص:

1. أنشئ Space على https://huggingface.co/new-space
   - اختر **SDK: Docker**
   - **Hardware:** CPU basic - free (16 GB RAM)
2. ارفع محتوى مجلد `backend/` إلى الـ Space:
   ```bash
   cd backend
   git init
   git remote add hf https://huggingface.co/spaces/USERNAME/insighthub-backend
   git add . && git commit -m "deploy"
   git push hf main:main
   ```
3. اضبط الأسرار في **Space Settings → Variables and secrets**:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CORS_ORIGINS`

> **ملاحظة:** HF Spaces أيضاً يدعم Sync مع GitHub - في إعدادات الـ Space، اربطه بـ `im1xd/insighthub` وحدّد مجلد `backend/` كمصدر.

---

## ربط الجزأين

بعد نشر الـ Backend، عدّل ملفات `frontend/*.html` وأضف:

```javascript
// في أعلى script tag في كل ملف HTML
const BACKEND_URL = 'https://USERNAME-insighthub-backend.hf.space';
```

ثم استدعِ `/api/v1/analysis/trigger` بعد إنشاء طلب جديد:

```javascript
async function triggerBackendAnalysis(requestId) {
  await fetch(`${BACKEND_URL}/api/v1/analysis/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId })
  });
}
```

(هذا اختياري - الـ Backend يلتقط الطلبات تلقائياً عبر polling كل 30 ثانية)

---

## التقنيات

| طبقة | الأداة |
|---|---|
| Frontend | HTML/JS + Tailwind + Chart.js |
| Database | Supabase (PostgreSQL + REST) |
| API | FastAPI + uvicorn |
| Async | FastAPI BackgroundTasks (بدون Celery/Redis) |
| Big Data | PySpark 3.5 |
| NLP | HuggingFace Transformers + CAMeL-BERT العربي |
| Datasets | 8 مجاميع عربية مفتوحة (1.2M+ منشور) |

## الميزات الرئيسية

- ✅ Streaming مباشر من HF بدون تخزين محلي للـ datasets
- ✅ تحليل المشاعر بـ CAMeL-BERT للهجات العربية
- ✅ استخراج المواضيع، اكتشاف المؤثرين، تحليل الشبكات
- ✅ توليد ملخصات وتوصيات بالعربية
- ✅ مراقبة التقدّم في الزمن الحقيقي
- ✅ نشر مجاني بالكامل (Netlify + HF Spaces + Supabase)

</div>
