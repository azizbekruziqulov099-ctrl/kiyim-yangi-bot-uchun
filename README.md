# Fanlar integratsiyasi — darsga tayyorlovchi Telegram bot

Boshlang‘ich sinf (1–4) o‘qituvchisi uchun bot: ikki fanni bitta mavzu orqali bog‘lab, darsga tayyorlab beradi.
Kiyim botining asosi (python-telegram-bot, PostgreSQL, admin panel, reklama, Madina ovozi) saqlangan,
do‘kon qismi olib tashlangan.

**Fanlar juftliklari (9 ta):** Ona tili + Matematika · Tabiiy fan + Matematika · Ona tili + Tabiiy fan ·
Texnologiya + Matematika · Texnologiya + Ona tili · O‘qish + Matematika · O‘qish + Ona tili · O‘qish + Tabiiy fan ·
O‘qish + Texnologiya.

## Nimalar bor

- **📗 Miya — 216 ta tayyor dars** (9 juftlik × 6 mavzu × 4 sinf). AI’siz, bepul, darhol ochiladi.
  Fayl: `data/Fanlar_Miya.xlsx`. Bot har ishga tushganda faylni tekshiradi va o‘zgargan bo‘lsa bazaga yozadi.
- **🤖 AI dars** — ro‘yxatda yo‘q mavzu uchun (OpenAI yoki Gemini, model avtomatik tanlanadi).
- **🧮 Ko‘rgazma kartasi** — bot o‘zi chizadi: «6 ta olma» → aniq 6 ta olma rasmi; o‘lchovlar → diagramma.
- **🎨 AI rasm** — ixtiyoriy; sonlari tekshiriladi; tayyor dars rasmi bir marta chizilib, hammaga bepul ko‘rinadi.
- **✅ Javoblar** — hisoblar bot tomonidan qayta tekshiriladi (`6+4=10` ✅).
- **📄 Word** — dars ishlanmasi (karta, rasm, dars borishi jadvali, javoblar alohida sahifada).
- **🔊 Ovoz** — matn va topshiriqlarni o‘qiydi (bo‘laklab, qayta urinish, Madina ↔ Sardor); **🎤 ovozli xabar** bilan mavzu aytish.
- **👑 Admin** — statistika, reklama, sozlamalar (limitlar, rasm, ovoz), AI holati, miya import/eksport, bloklash.
- **ℹ️ Yordam** — botning o‘zida bo‘limlarga ajratilgan qo‘llanma.

## Ishga tushirish (Railway)

1. @BotFather’dan yangi bot tokenini oling.
2. Shu fayllarni GitHub reposiga yuklang (eski `excel_import_handler` kerak emas).
3. Railway → Deploy from GitHub → PostgreSQL qo‘shing.
4. Variables: `TOKEN`, `ADMIN_ID` (majburiy); `OPENAI_API_KEY` yoki `GEMINI_API_KEY` (ixtiyoriy).
   To‘liq ro‘yxat — `.env.example`.
5. Start: `python main.py`. Logda `Miya yuklandi: 216 ta dars` chiqadi.

Kompyuterda sinash: `pip install -r requirements.txt`, so‘ng `TOKEN=... ADMIN_ID=... python main.py`
(`DATABASE_URL` bo‘lmasa `bot.db` SQLite fayli yaratiladi).

## Miyani yangilash

- **Git orqali:** `data/Fanlar_Miya.xlsx` ni tahrirlab qayta yuklang — bot o‘zi yangilaydi.
- **Bot orqali:** admin `/miya_import` → Excel yuboradi → tekshiruv → «✅ Tasdiqlash». Yuklab olish: `/miya_export`.
- Excel qoidalari fayl ichidagi «Yoriqnoma» varag‘ida.

## Buyruqlar

| Kimga | Buyruq |
| --- | --- |
| Hamma | `/start`, `/dars`, `/darslar`, `/yordam`, `/bekor` |
| Admin | `/admin`, `/stat`, `/miya_import`, `/miya_export`, `/block <id>`, `/unblock <id>` |

## Tuzilma

```
main.py                 — ishga tushirish
edu/app.py              — handlerlarni ulash, miyani yuklash
edu/handlers.py         — foydalanuvchi bosqichlari, tayyor/AI dars, ovoz, yordam
edu/admin.py            — admin panel
edu/pipeline.py         — dars va rasm tayyorlash jarayoni (orqa fonda)
edu/miya.py             — Excel ↔ baza (miya)
edu/ai.py, prompts.py   — OpenAI / Gemini, ko‘rsatmalar
edu/lesson.py           — formatlash, hisob tekshiruvi
edu/card.py             — ko‘rgazma kartalari; edu/docx_export.py — Word; edu/tts.py — ovoz
edu/db.py               — PostgreSQL / SQLite (jadvallar edu_ bilan boshlanadi)
data/Fanlar_Miya.xlsx   — 216 ta tayyor dars
assets/                 — shrift (Poppins, OFL) va buyum rasmlari (Noto Emoji, Apache 2.0)
tests/                  — 60 ta sinov (pip install -r requirements-dev.txt; pytest)
```
