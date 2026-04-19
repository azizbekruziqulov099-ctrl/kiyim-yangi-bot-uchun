elif context.user_data.get("step") == "search_category" and "(" in text:

    category = text.split("(")[0]
    category = category.replace("👕","").replace("👖","").replace("🧥","") \
        .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()

    context.user_data["filter_category"] = category

    found = False

    for p in products:
        # 🔥 HAMMA FILTER ISHLAYDI
        if not filter_check(p, context):
            continue

        # 🔥 SIZE LOGIKA
        try:
            user_size = int(context.user_data["filter_size"])

            if "-" in p["size"]:
                start, end = map(int, p["size"].split("-"))
                ok = start <= user_size <= end
            else:
                ps = int(p["size"])
                ok = abs(ps - user_size) <= 1

        except:
            ok = False

        if not ok:
            continue

        found = True

        keyboard = [
            [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{p['id']}")]
        ]

        await update.message.reply_photo(
            photo=p["photo"],
            caption=f"{p['name']}\n📏 {p['size']}\n💰 {p['price']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    if not found:
        await update.message.reply_text("❌ Mos mahsulot topilmadi")

    context.user_data.clear()
