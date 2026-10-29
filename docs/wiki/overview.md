# Overview

**Granovo** — بستر هوش مصنوعی بهینه‌سازی بازیافت پلاستیک (AI-First Plastic-Recycling
Optimization Platform).

## مسئله
کیفیت مواد پلاستیک ورودی به کارخانه‌های بازیافت ثابت نیست. اپراتورها برای تنظیم اکسترودر
(دما/سرعت/فشار) به آزمون‌وخطا متکی‌اند، که باعث نرخ رد کالای بالا (~۲۵٪)، مصرف انرژی زیاد،
توقف خط و کیفیت ناپایدار گرانول خروجی می‌شود.

## راه‌حل — چهار ستون AI
1. [[entities/polymer-identification]] — شناسایی پلیمر با تصویربرداری طیفی/بینایی ماشین
2. [[entities/extruder-parameter-predictor]] — پیش‌بینی پارامتر بهینه اکسترودر (هسته‌ی تمایز)
3. [[entities/feedback-loop]] — یادگیری پیوسته از نتیجه‌ی هر دسته تولید
4. [[entities/quality-price-estimator]] — برآورد کیفیت و قیمت‌گذاری گرانول

به‌علاوه [[entities/marketplace]] برای فروش مستقیم B2B گرانول بازیافتی.

## هدف قابل‌اندازه‌گیری
کاهش نرخ رد کالا از **~۲۵٪** به **زیر ۵٪**.

## مفاهیم کلیدی
- [[concepts/data-moat]] — مزیت رقابتی از داده‌ی بومی کارخانه‌های ایران
- [[concepts/business-model]] — مدل درآمدی SaaS + کمیسیون بازارگاه
- [[concepts/roadmap-phases]] — ۵ فاز توسعه، هرکدام Milestone روی GitHub

## وضعیت فعلی پروژه
مرحله‌ی MVP محلی/پیش از پایلوت. ساخته شده:
- [[entities/landing-page]] — لندینگ معرفی محصول با فرم mailto و لینک داشبورد
- [[concepts/production-workflow]] — API احراز هویت‌شده و جداسازی کارخانه، schema PostgreSQL/SQLite، ثبت دستگاه/بچ و CSV، داشبورد اپراتور و KPI وزن‌دار/روند روزانه
- [[entities/feedback-loop]] — ثبت تأیید کیفیت، model run audit، fingerprint/MAE و gate داده برای تخمین بعدی
- [[entities/extruder-parameter-predictor]] — پیشنهاد آزمایشی همسایه‌ی تاریخی با gate داده، ارزیابی داخلی و تأیید اپراتور؛ بدون کنترل ماشین
- hardening فنی شامل CI، CodeQL، gitleaks، SBOM، Dependabot، README، معماری، threat model، لاگ ساختاری و OpenTelemetry API در ریشه‌ی repo

۱۷ تست backend محلی و ۸ تست Node، به‌علاوه ۳۲ تست backend روی PostgreSQL 17 و SQLite و backup/restore داده‌ی آزمایشی پاس شده‌اند. تست بصری مرورگر، استقرار و پایلوت صنعتی هنوز انجام نشده‌اند؛ issueهای باز صنعتی/بازارگاه همچنان نیازمند داده، شریک یا سرویس بیرونی‌اند.

> این ویکی طبق «Vault Recipe» نگه‌داری می‌شود (نگاه کنید `schema.md` و `CLAUDE.md` در ریشه‌ی
> ریپو). هر تغییر معنایی در کد باید همین‌جا هم منعکس شود.
