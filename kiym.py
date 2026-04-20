elif text == "💾 Saqlash":
    pid = context.user_data.get("edit_product_id")

    # size
    size = context.user_data.get("size")
    if not size:
        for p in products:
            if p["id"] == pid:
                size = p.get("size", "")
                break

    # count
    count = context.user_data.get("count")
    if count is None:
        for p in products:
            if p["id"] == pid:
                count = p.get("count", 0)
                break

    cur.execute("""
    UPDATE products
    SET gender=%s, origin=%s, season=%s, category=%s, size=%s, count=%s
    WHERE id=%s
    """, (
        context.user_data.get("gender"),
        context.user_data.get("origin"),
        ",".join(context.user_data.get("seasons") or []),
        context.user_data.get("category"),
        size,
        count,
        pid
    ))

    conn.commit()
    load_products_from_db()

    await update.message.reply_text("✅ Saqlandi")
