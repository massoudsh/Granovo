# Feedback Loop

> حلقه‌ی یادگیری پیوسته: نتیجه‌ی واقعی کیفیت هر دسته‌ی تولید به مدل بازخورد داده می‌شود
> تا [[entities/extruder-parameter-predictor]] با گذر زمان دقیق‌تر شود.

## مسئولیت‌ها
- ثبت نتیجه‌ی واقعی هر بچ (کیفیت خروجی، نرخ رد کالا) پس از اجرای تنظیمات پیشنهادی
- بازآموزی/به‌روزرسانی دوره‌ای مدل پیش‌بینی پارامتر با داده‌ی جدید
- تشکیل بلندمدت دیتاست «ترکیب ← پارامتر ← کیفیت» که [[concepts/data-moat]] را می‌سازد

## وابستگی‌ها
- [[entities/extruder-parameter-predictor]] — مصرف‌کننده‌ی خروجی این حلقه
- [[entities/quality-price-estimator]] — منبع سنجش کیفیت هر بچ

## وضعیت
نسخه‌ی MVP پیاده‌سازی شده است. اپراتور نتیجه‌ی بچ را با `quality_verified` تأیید می‌کند؛ `/api/feedback` داده‌های verified/pending و تاریخچه‌ی model runها را نشان می‌دهد. هر پیشنهاد یک `model_runs` audit record با fingerprint داده، تعداد training/holdout و MAE دارد. داده‌ی واجد شرایط فقط برای همان factory/machine/polymer و نرخ رد کمتر از ۵٪ وارد تخمین می‌شود. تغییر داده‌ی آموزشی پیشنهاد قبلی را برای تأیید منقضی می‌کند.

این هنوز بازآموزی زمان‌بندی‌شده یا مدل صنعتی نیست؛ job scheduler، آزمایشگاه مستقل، کیفیت چندشاخصی و آموزش روی داده‌ی واقعی کارخانه باید پیش از production اضافه شوند.
GitHub issue: #11 — MVP پیش رفته؛ اعتبارسنجی صنعتی باز است.

## منابع کد
- `backend/app.py:201` — تأیید کیفیت بچ
- `backend/app.py:269` — انتخاب داده‌ی واجد شرایط و ساخت model run
- `backend/app.py:286` — `/api/feedback` و وضعیت آماده‌بودن retraining
- `backend/app.py:318` — رد پیشنهاد stale
- `backend/db.py:62` — model_runs و audit metadata
- `tests/test_workflow.py:214` — audit و stale recommendation tests
