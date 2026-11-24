# Competitive Parity Features

> پنج قابلیت اقتباس‌شده از رقبای بین‌المللی و ایرانی، و مرزهای صادقانه‌ی هرکدام.

## منشأ

تحلیل کامل در `outputs/granovo-competitor-analysis.md`. رقبا: EREMA PredictOn، TOMRA/PolyPerception،
Cirplus، Recyda، EverestLabs Navigator؛ و در ایران Bazmand، GAIN، Pakdoon، پلتفرم دانشگاه شریف،
Iran Recycling System.

## قابلیت‌ها

1. **نگهداشت پیشگیرانه** — `downtime_events` (`downtime`/`maintenance`/`quality_drift`) و
   `/api/availability` با بازه‌ی ۱–۳۶۵ روز. دسترس‌پذیری = (پنجره − توقف) / پنجره؛ MTBF = پنجره‌ی
   سالم / تعداد رویداد. **OEE نیست**: ساعت تولید برنامه‌ریزی‌شده و کیفیت خروجی مدل نمی‌شود.
2. **کتاب قیمت و هزینه‌ی ضایعات** — `polymer_prices` یکتا per (factory, polymer)؛
   `/api/value-report` = mass × price. **ارزها هرگز جمع نمی‌شوند** و گزارش per-currency است.
   مبنای فاکتور یا نرخ بازار نیست.
3. **گذرنامه‌ی کیفیت** — `passports` با `snapshot` و `content_hash` (SHA-256). صدور فقط برای بچ
   `quality_verified` و idempotent per batch. صفحه‌ی عمومی `/public/passports/{token}` بدون نشست،
   هش را دوباره حساب می‌کند و در صورت تغییر `status: tampered` می‌دهد. فقط code/date/polymer/
   purity/moisture/mass/verified منتشر می‌شود — بدون factory_id، operator_id یا ایمیل.
   **گواهی قانونی، آزمایشگاهی یا محتوای بازیافتی نیست.**
4. **امتیاز آمادگی راه‌اندازی** — `/api/readiness` با هفت آیتم (دستگاه، بچ، baseline، ۸ بچ تأییدشده،
   کتاب قیمت، توقف، گذرنامه). فقط کامل‌بودن داده را می‌سنجد، نه کیفیت محصول یا موفقیت پایلوت.
5. **اطمینان پیشنهاد** — `predict()` افزون بر settings، `confidence` (high/medium/low) و
   `expected_range` (min/max تنظیمات سه همسایه‌ی نزدیک) برمی‌گرداند؛ gate داده و تأیید اپراتور
   بدون تغییر باقی است و هیچ کنترل ماشینی اضافه نشده.

## قراردادها و edge cases

- مسیرهای `PUT /api/prices` و `POST /api/downtime` مانند بقیه‌ی نوشتن‌ها CSRF و same-origin لازم دارند؛ تست‌ها این را پوشش می‌دهند.
- `minutes` بین ۱ و ۲۰۱۶۰ (دو هفته) و `started_on` نمی‌تواند در آینده باشد.
- توقف قدیمی‌تر از پنجره در دسترس‌پذیری حساب نمی‌شود و `mtbf_minutes` بدون رویداد `null` است.
- توقف بیشتر از پنجره در سقف پنجره بریده می‌شود تا دسترس‌پذیری منفی نشود.
- گذرنامه فقط پس از تأیید کیفیت صادر می‌شود؛ تغییر snapshot در DB باعث `tampered` می‌شود.
- `/public/` تنها مسیری است که `Access-Control-Allow-Origin: *` می‌گیرد.

## منابع کد

- `backend/db.py` — جدول‌های `downtime_events`، `polymer_prices`، `passports`
- `backend/app.py` — `/api/downtime`، `/api/availability`، `/api/prices`، `/api/value-report`،
  `/api/batches/{id}/passport`، `/api/passports`، `/public/passports/{token}`، `/api/readiness`
- `backend/predictor.py` — `confidence` و `expected_range`
- `landing/dashboard/dashboard.js` — `renderReadiness`، `renderValue`، `renderAvailability`، `renderPassports`
- `tests/test_workflow.py` — تست‌های downtime/prices/passport/readiness
- `tests/dashboard.test.cjs` — تست‌های رندر UI
