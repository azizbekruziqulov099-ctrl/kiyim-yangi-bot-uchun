# 🔥 size (SAFE VERSION)
if context.user_data.get("filter_size"):
    size_text = context.user_data.get("filter_size")

    # filter size noto‘g‘ri bo‘lsa — tekshirmaymiz (crash yo‘q)
    if not str(size_text).isdigit():
        return True

    size = int(size_text)

    raw = str(p.get("size") or "").lower().replace("sm", "").strip()

    if raw == "":
        return False

    # diapazon: "80-85"
    if "-" in raw:
        parts = raw.split("-")
        if len(parts) < 2:
            return False

        s1 = parts[0].strip()
        s2 = parts[1].strip()

        if not s1.isdigit() or not s2.isdigit():
            return False

        s1, s2 = int(s1), int(s2)

        if not (s1 <= size <= s2):
            return False

    else:
        if not raw.isdigit():
            return False

        p_size = int(raw)

        if abs(p_size - size) > 1:
            return False
