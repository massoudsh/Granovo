# Production Workflow

> MVP ثبت داده، داشبورد اپراتور و پایش نرخ رد برای کارخانه‌های مستقل.

## قرارداد داده و جریان

- هر ثبت‌نام کارخانه‌ی مستقل می‌سازد؛ عضویت تیمی/نقش مدیر هنوز وجود ندارد. نشست ۱۲ساعته، رمز scrypt، کوکی Secure/HttpOnly و CSRF در نوشتن اجباری‌اند. تمام queryهای عملیاتی با factory_id حساب محدود می‌شوند.
- دستگاه: نام، سازنده، مدل، machine_type در extruder/pelletizer/washer و حدود دما، سرعت و فشار که کاربر از مشخصات تأییدشده وارد می‌کند.
- بچ: code یکتا در کارخانه، produced_on، phase=baseline/pilot، machine_id/operator_id، polymer=PE/PP/PET/PS/PVC/ABS، purity_pct، moisture_pct، temperature_c، screw_rpm، pressure_bar، total_kg و rejected_kg.
- تاریخ آینده، مقادیر غیرمتناهی، rejected_kg بیشتر از کل و تنظیمات خارج از حدود دستگاه رد می‌شوند. تأیید کیفیت جداگانه با quality_verified_by/at ثبت می‌شود؛ ورود CSV خودکار تأیید نمی‌شود.
- CSV: UTF-8، هدر دقیق مطابق Batch، حداکثر ۵۰۰ ردیف/۱MB؛ تراکنش همه یا هیچ. قالب از داشبورد دریافت می‌شود.
- KPI: sum(rejected_kg)/sum(total_kg)*100، جدا برای خط مبنا/پایلوت. آرایه‌ی daily همین محاسبه‌ی وزن‌دار را به تفکیک تاریخ و مرحله به UI جدول روند می‌دهد. بدون داده مقدار null است، نه صفر. هدف واقعاً کمتر از ۵٪ و کاهش به واحد درصد است. start/end/machine_id روی KPI و تاریخچه یکسان‌اند؛ KPI کل نتایج را حساب می‌کند، نه فقط ۲۰۰ ردیف تاریخچه.
- داشبورد فارسی `/dashboard/`: ثبت حساب/دستگاه/بچ، ورود CSV، تأیید دستی کیفیت، فیلتر عملکرد و [[entities/extruder-parameter-predictor]] با تأیید اپراتور. `/api/feedback` وضعیت داده‌ی verified/pending و مدل‌ران‌ها را برای audit/retraining نشان می‌دهد. هیچ داده‌ی demo seed نمی‌شود.

## ذخیره‌سازی و استقرار

SQLAlchemy schema برای PostgreSQL+psycopg و SQLite توسعه. `python -m backend.db` فقط schema اولیه را idempotent می‌سازد؛ تغییرات آینده به migration نیاز دارند. `DATABASE_URL` در تنظیمات استقرار نگه‌داری می‌شود، نه گیت. `python -m backend` برنامه‌ی API و static را هم‌مبدأ سرو می‌کند. production به HTTPS، Host حفظ‌شده و forwarding scheme از loopback مورد اعتماد نیاز دارد. `--allow-http` فقط توسعه‌ی ایزوله است.

فایل SQLite و دیتابیس‌های تست از گیت مستثنا هستند. `tests/run_postgres.py` یک cluster موقت socket-only با دسترسی مالک می‌سازد، تست‌ها را روی PostgreSQL 17 واقعی و SQLite اجرا و dump/restore داده‌ی آزمایشی را با شمارش بچ‌ها بررسی می‌کند؛ در پایان cluster متوقف و حذف می‌شود. `/ready` اتصال و تمام جدول‌های schema را چک می‌کند و در نقص دیتابیس بدون افشای جزئیات ۵۰۳ می‌دهد؛ `/health` فقط liveness است. مرورگر، استقرار و فرایند دائمی ایجاد نشده‌اند.

## محدودیت‌ها

این MVP جایگزین مصاحبه/پایلوت واقعی، آزمایش کیفیت، مدل صنعتی یا کنترل PLC نیست. ترکیب چندجزئی، تصویر/طیف، نقش‌های تیمی، بازیابی رمز و limiter مشترک هنوز وجود ندارند. قبل از production، اتصال سرور پروژه، HTTPS، پشتیبان‌گیری واقعی، بازبینی امنیت و تست بصری لازم‌اند. #14 با روند کیفیت پیش رفته ولی بخش انرژی/فروش آن انجام نشده است. جزئیات مسیرها، CSV، راه‌اندازی و موانع هر issue در `outputs/granovo-technical-foundation.md` است.

## منابع کد

- `backend/db.py:38` — schema بچ‌ها؛ `backend/db.py:62` — پیشنهادها
- `backend/app.py:36` — app factory و کنترل‌های امنیتی؛ `backend/app.py:74` — احراز هویت/CSRF
- `backend/app.py:166` — حدود دستگاه؛ `backend/app.py:213` — CSV اتمیک؛ `backend/app.py:245` — KPI وزن‌دار
- `backend/schemas.py:45` — قرارداد ورودی بچ
- `landing/dashboard/dashboard.js:104` — کارت KPI/روند روزانه؛ `landing/dashboard/dashboard.js:172` — ورود به workspace
- `backend/app.py:309` — readiness اتصال و schema؛ `tests/run_postgres.py:1` — cluster ایزوله و بازیابی backup
- `tests/test_workflow.py:1` و `tests/dashboard.test.cjs:1` — آزمون‌های backend و UI بدون مرورگر
