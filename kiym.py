# 🔥 ADMIN bo‘lsa darrov chiqaramiz
if update.effective_user.id == ADMIN_ID:

    found = False

    for p in products:
        if category in p["category"].lower():

            found = True

            keyboard = [
                [InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_{p['id']}")],
                [InlineKeyboardButton("❌ O‘chirish", callback_data=f"delete_{p['id']}")]
            ]

            await update.message.reply_photo(
                photo=p["photo"],
                caption=f"{p['name']}\n📏 {p['size']}\n📦 {p['count']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    if not found:
        await update.message.reply_text("❌ Mahsulot yo‘q")

    return


# 🔥 USER bo‘lsa razmer so‘raydi
context.user_data["filter_category"] = category
context.user_data["step"] = "write_size"

await update.message.reply_text("📏 Razmer yozing (masalan 44):")
return
