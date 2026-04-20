elif text == "💾 Saqlash":
    pid = context.user_data.get("edit_product_id")

    # 🔥 size ni tekshiramiz
    size = context.user_data.get("size")

    if not size:
        for p in products:
            if p["id"] == pid:
                size = p["size"]
                break

    cur.execute("""
    UPDATE products
    SET gender=%s, origin=%s, season=%s, category=%s, size=%s, count=%s
    WHERE id=%s
    """, (
        context.user_data.get("gender"),
        context.user_data.get("origin"),
        ",".join(context.user_data.get("seasons", [])),
        context.user_data.get("category"),
        size,  # 🔥 SHU YER O‘ZGARDI
        context.user_data.get("count"),
        pid
    ))

    conn.commit()
    load_products_from_db()
