elif context.user_data.get("step") == "size_category" and "(" in text:

    category = text.split("(")[0]
    category = category.replace("👕","").replace("👖","").replace("🧥","") \
               .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()
    context.user_data["filter_category"] = category

    if "2 talik" in category:
        category = "2 talik kiyim"
    elif "3 talik" in category:
        category = "3 talik kiyim"
    elif "futbolka" in category:
        category = "futbolka"
    elif "shim" in category:
        category = "shim"
    elif "qalin" in category:
        category = "qalin kiyim"
    elif "shortik" in category:
        category = "shortik"
    elif "oyoq" in category:
        category = "oyoq kiyim"
    elif "bosh" in category:
        category = "bosh kiyim"
    elif "ichki" in category:
        category = "ichki kiyim"

    found = False

    for i, p in enumerate(products):
        if (
            p["size"] == context.user_data.get("filter_size")
            and category == p["category"].lower()
            and filter_check(p, context)   # 🔥 ENG MUHIM QO‘SHILDI
        ):
            found = True

            if update.effective_user.id == ADMIN_ID:
                keyboard = [
                    [InlineKeyboardButton("❌ O‘chirish", callback_data=f"delete_{p['id']}")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{p['id']}")]
                ]

            await update.message.reply_photo(
                photo=p["photo"],
                caption=f"{p['name']}\n{p['size']}\n{p['price']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    if not found:
        await update.message.reply_text("❌ Mos mahsulot yo‘q")
