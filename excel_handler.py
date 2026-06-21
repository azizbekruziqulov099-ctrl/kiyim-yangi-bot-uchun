"""
Bu faylni kiym.py ga qo'shing:

1) photo_handler funksiyasini quyidagi bilan ALMASHTIRING
2) excel_import_handler ni handlers ga qo'shing
3) app.add_handler qatorlariga quyidagini qo'shing:
   app.add_handler(MessageHandler(filters.Document.ALL, excel_import_handler))
"""

import openpyxl
import io

# ─────────────────────────────────────────────
# RASM → file_id qaytaruvchi handler
# ─────────────────────────────────────────────
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ── Admin mahsulot qo'shayotgan bo'lsa (eski logika) ──
    if user_id == ADMIN_ID and not context.user_data.get("get_id_mode"):
        context.user_data.clear()
        context.user_data["photo"] = update.message.photo[-1].file_id
        context.user_data["step"] = "gender"
        keyboard = [["👦 O'g'il", "👧 Qiz"]]
        await update.message.reply_text(
            "Kim uchun?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ── /get_id rejimi ──
    file_id = update.message.photo[-1].file_id
    await update.message.reply_text(
        f"📋 file_id:\n\n<code>{file_id}</code>\n\nExcel jadvalga ko'chiring",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /get_id buyrug'i — faqat admin
# ─────────────────────────────────────────────
async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data["get_id_mode"] = True
    await update.message.reply_text(
        "📸 Endi rasm yuboring — har bir rasm uchun file_id qaytaraman.\n"
        "Tugagach /done yuboring."
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("get_id_mode", None)
    await update.message.reply_text(
        "✅ file_id rejimi tugadi.",
        reply_markup=ADMIN_MENU if update.effective_user.id == ADMIN_ID else MAIN_MENU
    )


# ─────────────────────────────────────────────
# EXCEL O'QUVCHI — .xlsx faylni botga yuborganda
# ─────────────────────────────────────────────
FASL_OPTIONS = {"yozgi", "qishki", "bahor", "kuz"}
VALID_CATEGORIES = {
    "2 talik kiyim", "3 talik kiyim", "futbolka", "shim",
    "qalin kiyim", "shortik", "oyoq kiyim", "bosh kiyim", "ichki kiyim"
}

async def excel_import_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    doc = update.message.document
    if not doc.file_name.endswith(".xlsx"):
        return  # faqat xlsx

    await update.message.reply_text("⏳ Excel o'qilmoqda...")

    # Faylni yuklab olish
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
        ws = wb["Mahsulotlar"]
    except Exception as e:
        await update.message.reply_text(f"❌ Fayl o'qilmadi: {e}")
        return

    added = 0
    errors = []

    # 4-qatordan boshlab (1=sarlavha, 2=izoh, 3=namuna)
    for row_num, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        # Bo'sh qatorni o'tkazib yuborish
        if not row[0] and not row[1]:
            continue

        # Namuna qatorini o'tkazib yuborish
        if row[0] and "NAMUNA" in str(row[0]).upper():
            continue

        photo    = str(row[0]).strip() if row[0] else ""
        name     = str(row[1]).strip() if row[1] else ""
        gender   = str(row[2]).strip() if row[2] else ""
        origin   = str(row[3]).strip() if row[3] else ""
        season   = str(row[4]).strip() if row[4] else ""
        category = str(row[5]).strip().lower() if row[5] else ""
        size     = str(row[6]).strip() if row[6] else ""
        price_raw= str(row[7]).strip() if row[7] else ""
        cost_raw = str(row[8]).strip() if row[8] else "0"
        count_raw= str(row[9]).strip() if row[9] else ""
        colors   = str(row[10]).strip() if row[10] else ""

        # ── Majburiy maydonlar tekshiruvi ──
        missing = []
        if not photo:   missing.append("photo")
        if not name:    missing.append("nom")
        if not gender:  missing.append("jins")
        if not origin:  missing.append("fabrika")
        if not season:  missing.append("fasl")
        if not category: missing.append("kategoriya")
        if not size:    missing.append("razmer")
        if not price_raw: missing.append("narx")
        if not count_raw: missing.append("soni")

        if missing:
            errors.append(f"Qator {row_num}: {', '.join(missing)} yetishmaydi")
            continue

        # ── Narx va son tekshiruvi ──
        try:
            price_int = int(''.join(filter(str.isdigit, price_raw)))
            price_str = f"{price_int:,}".replace(",", " ") + " so'm"
        except:
            errors.append(f"Qator {row_num}: narx noto'g'ri ({price_raw})")
            continue

        try:
            cost_int = int(''.join(filter(str.isdigit, cost_raw))) if cost_raw else 0
        except:
            cost_int = 0

        try:
            count_int = int(''.join(filter(str.isdigit, count_raw)))
        except:
            errors.append(f"Qator {row_num}: soni noto'g'ri ({count_raw})")
            continue

        # ── Faslni tekshirish ──
        season_parts = [s.strip().capitalize() for s in season.replace(",", " ").split()]
        valid_seasons = [s for s in season_parts if s.lower() in FASL_OPTIONS]
        if not valid_seasons:
            errors.append(f"Qator {row_num}: fasl noto'g'ri ({season})")
            continue
        season_db = ",".join(valid_seasons)

        # ── Kategoriya tekshiruvi ──
        if category not in VALID_CATEGORIES:
            errors.append(f"Qator {row_num}: kategoriya noto'g'ri ({category})")
            continue

        # ── DB ga yozish ──
        try:
            cur.execute("""
                INSERT INTO products
                    (photo, gender, origin, season, category, name, size, price, count, reserved, cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
            """, (
                photo, gender, origin, season_db,
                category, name, size, price_str,
                count_int, cost_int
            ))
            added += 1
        except Exception as e:
            errors.append(f"Qator {row_num}: DB xato — {e}")
            conn.rollback()
            continue

    conn.commit()
    load_products_from_db()

    # ── Natija ──
    msg = f"✅ {added} ta mahsulot qo'shildi!"
    if errors:
        err_text = "\n".join(errors[:10])
        if len(errors) > 10:
            err_text += f"\n... va yana {len(errors)-10} ta xato"
        msg += f"\n\n⚠️ Xatolar:\n{err_text}"

    await update.message.reply_text(msg)


# ─────────────────────────────────────────────
# app.add_handler ga qo'shing (kiym.py oxirida):
# ─────────────────────────────────────────────
# app.add_handler(CommandHandler("get_id", get_id_command))
# app.add_handler(CommandHandler("done", done_command))
# app.add_handler(MessageHandler(filters.Document.ALL, excel_import_handler))
