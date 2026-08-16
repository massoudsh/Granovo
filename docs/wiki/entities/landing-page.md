# Landing Page

> لندینگ‌پیج استاتیک معرفی Granovo — مسئله، راه‌حل، ستون‌های AI، بازارگاه، و CTA تماس.

## مسئولیت‌ها
- معرفی برند Granovo و پیام اصلی («از آزمون‌وخطا تا تولید داده‌محور»)
- نمایش مسئله (نرخ رد کالا ~۲۵٪) و هدف (زیر ۵٪)
- معرفی چهار ستون AI (لینک به entityهای مربوطه در همین wiki)
- CTA تماس (`mailto:hello@granovo.ir` — placeholder، باید با ایمیل واقعی جایگزین شود)

## وابستگی‌ها
- محتوای این صفحه از [[overview]] و `outputs/granovo-product-brief.md` گرفته شده

## قراردادها / Edge cases
- استاتیک محض (بدون backend/فرم واقعی) — فرم تماس فعلاً فقط mailto است.
- فونت Vazirmatn از Google Fonts CDN لود می‌شود؛ اگر نیاز به offline بود باید self-host شود.
- راست‌چین (`dir="rtl"`, `lang="fa"`)، ریسپانسیو با CSS Grid/Flexbox خالص (بدون فریم‌ورک).

## منابع کد
- `landing/index.html` — ساختار صفحه
- `landing/assets/style.css` — تم بصری (گرادیان teal→blue مطابق برند Granovo)
- `landing/assets/script.js` — منوی موبایل + سال فوتر
