found = False

for p in products:
    try:
        if filter_check(p, context):

            found = True

            keyboard = [
                [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{p['id']}")]
            ]

            await update.message.reply_photo(
                photo=p["photo"],
                caption=f"{p['name']}\n📏 {p['size']}\n💰 {p['price']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        print("BROKEN PRODUCT:", p, "ERROR:", e)
        continue

if not found:
    await update.message.reply_text("❌ Mahsulot yo‘q")
