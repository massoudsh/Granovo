# Production Workflow

> MVP ثبت داده، داشبورد اپراتور و پایش نرخ رد برای کارخانه‌های مستقل.

## قرارداد داده و جریان

- هر ثبت‌نام کارخانه‌ی مستقل می‌سازد؛ عضویت تیمی/نقش مدیر هنوز وجود ندارد. نشست ۱۲ساعته، رمز scrypt، کوکی Secure/HttpOnly و CSRF در نوشتن اجباری‌اند. تمام queryهای عملیاتی با factory_id حساب محدود می‌شوند.
- دستگاه: نام، temperature_min/max (°C)، rpm_max و pressure_max (bar). دستگاه دیگر کارخانه قابل انتخاب یا ثبت بچ نیست.
- بچ: code یکتا در کارخانه، produced_on، phase=baseline/pilot، machine_id/operator_id، polymer=PE/PP/PET/PS/PVC/ABS، purity_pct، moisture_pct، temperature_c، screw_rpm، pressure_bar، total_kg و rejected_kg.
- تاریخ آینده، مقادیر غیرمتناهی، rejected_kg بیشتر از کل و تنظیمات خارج از حدود دستگاه رد می‌شوند. تأیید کیفیت جداگانه با quality_verified_by/at ثبت می‌شود؛ ورود CSV خودکار تأیید نمی‌شود.
- CSV: UTF-8، هدر دقیق مطابق Batch، حداکثر ۵۰۰ ردیف/۱MB؛ تراکنش همه یا هیچ. قالب از داشبورد دریافت می‌شود.
- KPI: sum(rejected_kg)/sum(total_kg)*100، جدا برای خط مبنا/پایلوت. بدون داده مقدار null است، نه صفر. هدف واقعاً کمتر از ۵٪ و کاهش به واحد درصد است. start/end/machine_id روی KPI و تاریخچه یکسان‌اند؛ KPI کل نتایج را حساب می‌کند، نه فقط ۲۰۰ ردیف تاریخچه.
- داشبورد فارسی `/dashboard/`: ثبت حساب/دستگاه/بچ، ورود CSV، تأیید دستی کیفیت، فیلتر عملکرد و [[entities/extruder-parameter-predictor]] با تأیید اپراتور. هیچ داده‌ی demo seed نمی‌شود.

## ذخیره‌سازی و استقرار

SQLAlchemy schema برای PostgreSQL+psycopg و SQLite توسعه. `python -m backend.db` فقط schema اولیه را idempotent می‌سازد؛ تغییرات آینده به migration نیاز دارند. `DATABASE_URL` در تنظیمات استقرار نگه‌داری می‌شود، نه گیت. `python -m backend` برنامه‌ی API و static را هم‌مبدأ سرو می‌کند. production به HTTPS، Host حفظ‌شده و forwarding scheme از loopback مورد اعتماد نیاز دارد. `--allow-http` فقط توسعه‌ی ایزوله است.

فایل SQLite و دیتابیس‌های تست از گیت مستثنا هستند. تست‌ها SQLite واقعی و Node/VM دارند؛ PostgreSQL واقعی و مرورگر اجرا نشده‌اند. هیچ استقرار یا فرایند دائمی در این اجرا ایجاد نشده است.

## محدودیت‌ها

این MVP جایگزین مصاحبه/پایلوت واقعی، آزمایش کیفیت، مدل صنعتی یا کنترل PLC نیست. ترکیب چندجزئی، تصویر/طیف، نقش‌های تیمی، بازیابی رمز و limiter مشترک هنوز وجود ندارند. قبل از production، integration PostgreSQL، پشتیبان‌گیری، بازبینی امنیت و تست بصری لازم‌اند. جزئیات مسیرها، CSV و راه‌اندازی در `outputs/granovo-technical-foundation.md` است.

## منابع کد

- `backend/db.py:38` — schema بچ‌ها؛ `backend/db.py:62` — پیشنهادها
- `backend/app.py:36` — app factory و کنترل‌های امنیتی؛ `backend/app.py:74` — احراز هویت/CSRF
- `backend/app.py:166` — حدود دستگاه؛ `backend/app.py:213` — CSV اتمیک؛ `backend/app.py:245` — KPI وزن‌دار
- `backend/schemas.py:45` — قرارداد ورودی بچ
- `landing/dashboard/dashboard.js:104` — کارت KPI؛ `landing/dashboard/dashboard.js:164` — ورود به workspace
- `tests/test_workflow.py:1` و `tests/dashboard.test.cjs:1` — آزمون‌های backend و UI بدون مرورگر
