"""
AI qaytargan dars JSONini tozalash, tekshirish va Telegram uchun formatlash.

- uz_fix: o‘/g‘ va tutuq belgisini bir xil yozuvga keltiradi.
- check_math: har bir hisob topshirig‘ining ifodasini o‘zimiz hisoblab, javob bilan solishtiramiz.
- fix_minutes: dars bosqichlari daqiqalari yig‘indisi dars vaqtiga teng bo‘lishini ta’minlaydi.
"""
from __future__ import annotations

import ast
import html
import re
from fractions import Fraction
from typing import Any

from . import objects, subjects

LETTER_APOS = "‘"   # o‘, g‘
TUTUQ = "’"          # ta’lim, she’r

_OG_RE = re.compile(r"([oOgG])['`‘’ʻʼ´]")
_TUTUQ_RE = re.compile(r"(?<=[A-Za-z])['`ʻʼ´](?=[A-Za-z])")


def uz_fix(text: Any) -> str:
    """O‘zbekcha matndagi apostroflarni bir xil ko‘rinishga keltiradi va bo‘shliqlarni tartiblaydi."""
    if text is None:
        return ""
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    s = _OG_RE.sub(lambda m: m.group(1) + LETTER_APOS, s)
    s = _TUTUQ_RE.sub(TUTUQ, s)
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _s(value: Any, limit: int = 4000) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return ""
    text = uz_fix(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _list(value: Any, max_items: int = 10, limit: int = 700) -> list[str]:
    if isinstance(value, str):
        value = [line for line in value.split("\n")]
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _s(item, limit)
        text = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", text)
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+", value)
        if m:
            return int(m.group(0))
    return default


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


# ───────────────────────── Matematik tekshiruv ─────────────────────────

_EXPR_CHARS = re.compile(r"^[0-9\s.,+\-*/()xX×÷:·∙−–=]+$")
_NUM_RE = re.compile(r"-?\d+(?:[  ]\d{3})*(?:[.,]\d+)?(?:/\d+)?")


def safe_eval(expr: str) -> Fraction | None:
    """Faqat sonlar va + - * / ( ) dan iborat ifodani xavfsiz hisoblaydi."""
    s = (expr or "").strip()
    if not s or len(s) > 120 or not _EXPR_CHARS.match(s):
        return None
    s = s.split("=")[0]
    for a, b in (("×", "*"), ("x", "*"), ("X", "*"), ("·", "*"), ("∙", "*"), ("÷", "/"), (":", "/"),
                 ("−", "-"), ("–", "-")):
        s = s.replace(a, b)
    s = re.sub(r"(?<=\d)[  ](?=\d{3}\b)", "", s)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    try:
        tree = ast.parse(s.strip(), mode="eval")
    except SyntaxError:
        return None

    def ev(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ZeroDivisionError
            return left / right
        raise ValueError("ruxsat etilmagan ifoda")

    try:
        return ev(tree)
    except (ValueError, ZeroDivisionError, TypeError, RecursionError):
        return None


def parse_number(text: str) -> Fraction | None:
    m = _NUM_RE.search(text or "")
    if not m:
        return None
    raw = m.group(0).replace(" ", "").replace(" ", "")
    try:
        if "/" in raw:
            a, b = raw.split("/")
            return Fraction(Fraction(a.replace(",", ".")), Fraction(b))
        return Fraction(raw.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


def fmt_num(value: Fraction) -> str:
    if value.denominator == 1:
        n = value.numerator
        text = f"{abs(n):,}".replace(",", " ") if abs(n) >= 10000 else str(abs(n))
        return ("-" if n < 0 else "") + text
    as_float = float(value)
    if (value * 1000).denominator == 1:
        return f"{as_float:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{value.numerator}/{value.denominator}"


def pretty_expr(expr: str) -> str:
    s = expr.split("=")[0].strip()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[*×xX·∙]", " × ", s)
    s = re.sub(r"[/:÷]", " : ", s)
    s = s.replace("+", " + ")
    s = re.sub(r"(?<=[\d)])[-−–]", " − ", s)
    return re.sub(r"\s+", " ", s).strip()


_LEFT_CHARS = set("0123456789 ()+-−–×xX*:/·∙.,\u00a0")
_RIGHT_RE = re.compile(r"\s*(-?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?)")
_HAS_OP = re.compile(r"\d\s*\)?\s*[+\-−–×xX*:/·∙]\s*\(?\s*\d")


def find_equations(text: str) -> list[tuple[str, str]]:
    """Matndagi «6+4=10», «(360+240):4=150» kabi hisoblarni topadi: [(ifoda, natija)]."""
    found: list[tuple[str, str]] = []
    for m in re.finditer("=", text or ""):
        i = m.start()
        j = i
        while j > 0 and text[j - 1] in _LEFT_CHARS:
            j -= 1
        left = text[j:i]
        for sep in (", ", "; ", ". "):
            if sep in left:
                left = left.rsplit(sep, 1)[1]
        left = left.strip().lstrip("+-−–×xX*:/·∙.,) ")
        while left.count("(") > left.count(")") and left.startswith("("):
            left = left[1:].lstrip()
        right = _RIGHT_RE.match(text[i + 1:])
        if not left or not right or not _HAS_OP.search(left):
            continue
        found.append((left, right.group(1)))
    return found


def _check(expr: str, stated_text: str) -> dict | None:
    value = safe_eval(expr)
    if value is None:
        return None
    stated = parse_number(stated_text)
    return {"expr": pretty_expr(expr), "value": fmt_num(value), "stated": (stated_text or "").strip(),
            "ok": None if stated is None else stated == value}


def check_math(lesson: dict) -> None:
    """Har bir topshiriqqa 'checks' qo‘shadi: javobdagi hisoblar o‘zimiz qayta hisoblab tekshiriladi."""
    for task in lesson.get("tasks", []):
        checks: list[dict] = []
        seen: set[str] = set()
        expr = task.get("check_expression") or ""
        stated_text = task.get("check_result") or ""
        if "=" in expr and not stated_text:
            stated_text = expr.split("=", 1)[1]
        candidates = [(expr.split("=")[0], stated_text)] if expr else []
        candidates += find_equations(task.get("answer") or "")
        for left, right in candidates:
            item = _check(left, right)
            if item and item["expr"] not in seen:
                seen.add(item["expr"])
                checks.append(item)
        task["checks"] = checks


def math_problems(lesson: dict) -> list[int]:
    """Javobi hisobga mos kelmagan topshiriqlar raqamlari (1 dan boshlab)."""
    return [i for i, t in enumerate(lesson.get("tasks", []), start=1)
            if any(c["ok"] is False for c in t.get("checks") or [])]


# ───────────────────────── Dars vaqti ─────────────────────────

def fix_minutes(plan: list[dict], total: int) -> list[dict]:
    if not plan or total <= 0:
        return plan
    current = [max(0, p.get("minutes", 0)) for p in plan]
    if sum(current) == total:
        return plan
    if sum(current) <= 0:
        current = [1] * len(plan)
    scale = total / sum(current)
    scaled = [max(1, round(m * scale)) for m in current]
    diff = total - sum(scaled)
    order = sorted(range(len(plan)), key=lambda i: scaled[i], reverse=True)
    i = 0
    while diff != 0 and i < 10 * len(plan):
        idx = order[i % len(order)]
        if diff > 0:
            scaled[idx] += 1
            diff -= 1
        elif scaled[idx] > 1:
            scaled[idx] -= 1
            diff += 1
        i += 1
    for p, m in zip(plan, scaled):
        p["minutes"] = m
    return plan


# ───────────────────────── Normalizatsiya ─────────────────────────

class LessonError(ValueError):
    pass


def normalize_lesson(raw: dict, *, grade: int, pair_key: str, topic: str, minutes: int) -> dict:
    if not isinstance(raw, dict):
        raise LessonError("AI javobi obyekt emas")
    lesson: dict[str, Any] = {}
    lesson["title"] = _s(raw.get("title"), 150) or uz_fix(topic)
    lesson["summary"] = _s(raw.get("summary"), 900)

    obj = _dict(raw.get("objectives"))
    lesson["objectives"] = {
        "subject_a": _list(obj.get("subject_a"), 5),
        "subject_b": _list(obj.get("subject_b"), 5),
        "tarbiyaviy": _list(obj.get("tarbiyaviy"), 3),
    }
    lesson["teacher_info"] = _s(raw.get("teacher_info"), 3500)
    lesson["key_points"] = _list(raw.get("key_points"), 8)
    lesson["child_text"] = _s(raw.get("child_text"), 3000)

    integ = _dict(raw.get("integration"))
    lesson["integration"] = {
        "idea": _s(integ.get("idea"), 1500),
        "subject_a_part": _s(integ.get("subject_a_part"), 1200),
        "subject_b_part": _s(integ.get("subject_b_part"), 1200),
    }

    vocab = []
    for item in raw.get("vocabulary") or []:
        item = _dict(item)
        word, meaning = _s(item.get("word"), 60), _s(item.get("meaning"), 300)
        if word:
            vocab.append({"word": word, "meaning": meaning})
    lesson["vocabulary"] = vocab[:8]
    lesson["materials"] = _list(raw.get("materials"), 10, 200)

    image = _dict(raw.get("image"))
    groups = []
    for g in (image.get("count_groups") or [])[:6]:
        g = _dict(g)
        key = str(g.get("object_key") or "").strip()
        if not objects.exists(key):
            key = objects.guess_key(str(g.get("object_uz") or ""), key) or ""
        count = _int(g.get("count"))
        if not key or not (1 <= count <= 100000):
            continue
        groups.append({
            "label": _s(g.get("label"), 40) or f"{len(groups) + 1}-guruh",
            "where_en": str(g.get("where_en") or "").strip()[:200],
            "object_key": key,
            "object_uz": _s(g.get("object_uz"), 40) or objects.uz_name(key),
            "count": count,
        })
    lesson["image"] = {
        "scene_en": str(image.get("scene_en") or "").strip()[:1800],
        "description_uz": _s(image.get("description_uz"), 900),
        "count_groups": groups,
        "questions": _list(image.get("questions"), 6, 300),
    }

    tasks = []
    for t in (raw.get("tasks") or [])[:12]:
        t = _dict(t)
        instruction = _s(t.get("instruction"), 1500)
        if not instruction:
            continue
        tasks.append({
            "title": _s(t.get("title"), 80) or f"{len(tasks) + 1}-topshiriq",
            "subjects": _s(t.get("subjects"), 80) or subjects.pair_label(pair_key),
            "instruction": instruction,
            "uses_image": bool(t.get("uses_image")),
            "answer": _s(t.get("answer"), 1500),
            "check_expression": str(t.get("check_expression") or "").strip()[:120],
            "check_result": str(t.get("check_result") or "").strip()[:60],
        })
    lesson["tasks"] = tasks

    plan = []
    for st in (raw.get("lesson_plan") or [])[:9]:
        st = _dict(st)
        name = _s(st.get("stage"), 80)
        if not name:
            continue
        plan.append({
            "stage": name,
            "minutes": max(0, _int(st.get("minutes"))),
            "teacher": _s(st.get("teacher"), 1200),
            "students": _s(st.get("students"), 1000),
        })
    lesson["lesson_plan"] = fix_minutes(plan, minutes)

    lesson["assessment"] = _list(raw.get("assessment"), 6, 300)
    diff = _dict(raw.get("differentiation"))
    lesson["differentiation"] = {"support": _s(diff.get("support"), 800), "challenge": _s(diff.get("challenge"), 800)}
    lesson["homework"] = _s(raw.get("homework"), 800)
    lesson["voice_text"] = _s(raw.get("voice_text"), 1500) or lesson["child_text"][:1500]
    lesson["meta"] = {"grade": grade, "pair": pair_key, "topic": uz_fix(topic), "minutes": minutes}
    lesson["origin"] = "ai"

    if not tasks or not (lesson["child_text"] or lesson["teacher_info"]):
        raise LessonError("AI javobida topshiriqlar yoki matn yo‘q")
    check_math(lesson)
    return lesson


# ───────────────────────── Telegram formatlash (HTML) ─────────────────────────

LEVEL_BADGE = {"oson": "🟢 oson", "o‘rta": "🟡 o‘rta", "murakkab": "🔴 murakkab"}
STORY_HEADERS = ("O‘QISH UCHUN MUALLIFLIK HIKOYASI", "O‘QISH UCHUN MUALLIFLIK MATNI")


def h(text: Any) -> str:
    return html.escape(str(text or ""), quote=False)


def is_ready(lesson: dict) -> bool:
    return lesson.get("origin") == "miya"


def header(lesson: dict) -> str:
    m = lesson["meta"]
    badge = "📗 Tayyor dars" if is_ready(lesson) else "🤖 AI darsi"
    return (f"📚 <b>{h(lesson['title'])}</b>\n"
            f"🏫 {m['grade']}-sinf · {h(subjects.pair_label(m['pair']))} · ⏱ {m['minutes']} daqiqa · {badge}")


def _bullets(items: list[str], mark: str = "•") -> str:
    return "\n".join(f"{mark} {h(x)}" for x in items if x)


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    return f"<b>{title}</b>\n{body}" if body else ""


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p and p.strip())


def _goal_block(name: str, emoji: str, items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return f"{emoji} <i>{h(name)}:</i> {h(items[0])}"
    return f"{emoji} <i>{h(name)}:</i>\n" + _bullets(items)


def _info_block(lesson: dict) -> str:
    """Ma’lumot matni. Tayyor darslarda hikoya sarlavhasi alohida ajratib ko‘rsatiladi."""
    text = lesson.get("teacher_info") or ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return ""
    first_lines = paragraphs[0].split("\n")
    if first_lines[0].strip().upper() in STORY_HEADERS:
        story = "\n".join(first_lines[1:]).strip()
        rest = paragraphs[1:]
        parts = [_section("📖 O‘qish uchun matn", f"<i>{h(story)}</i>")]
        if rest:
            parts.append(_section("📘 O‘qituvchiga", "\n\n".join(h(p) for p in rest)))
        return _join(*parts)
    return _section("📘 Mavzu bo‘yicha ma’lumot", "\n\n".join(h(p) for p in paragraphs))


def fmt_overview(lesson: dict) -> str:
    m = lesson["meta"]
    a, b = subjects.pair_subjects(m["pair"])
    obj = lesson["objectives"]
    goals = [
        _goal_block(subjects.subject_name(a), subjects.subject_emoji(a), obj.get("subject_a", [])),
        _goal_block(subjects.subject_name(b), subjects.subject_emoji(b), obj.get("subject_b", [])),
        _goal_block("Tarbiyaviy", "🌱", obj.get("tarbiyaviy", [])),
    ]
    vocab = "\n".join(f"• <b>{h(v['word'])}</b> — {h(v['meaning'])}" for v in lesson.get("vocabulary", []))
    keywords = lesson.get("keywords") or []
    return _join(
        header(lesson),
        h(lesson.get("summary")),
        _section("🎯 Dars maqsadlari", "\n".join(g for g in goals if g)),
        _info_block(lesson),
        _section("📌 Asosiy tushunchalar", _bullets(lesson.get("key_points", []))),
        _section("🗣 Yangi so‘zlar", vocab),
        f"🔑 <b>Kalit so‘zlar:</b> {h(', '.join(keywords))}" if keywords else "",
    )


def fmt_integration(lesson: dict) -> str:
    a, b = subjects.pair_subjects(lesson["meta"]["pair"])
    integ = lesson["integration"]
    parts = []
    if integ.get("idea"):
        parts.append(h(integ["idea"]))
    if integ.get("subject_a_part"):
        parts.append(f"{subjects.subject_emoji(a)} <b>{h(subjects.subject_name(a))}:</b> {h(integ['subject_a_part'])}")
    if integ.get("subject_b_part"):
        parts.append(f"{subjects.subject_emoji(b)} <b>{h(subjects.subject_name(b))}:</b> {h(integ['subject_b_part'])}")
    child = ""
    if not is_ready(lesson) and lesson.get("child_text"):
        child = _section("📖 O‘quvchilar uchun matn", f"<i>{h(lesson['child_text'])}</i>")
    return _join(
        child,
        _section("🔗 Fanlar qanday bog‘lanadi", "\n\n".join(parts)),
        _section("🧰 Jihozlar", _bullets(lesson.get("materials", []))),
    )


def fmt_tasks(lesson: dict) -> str:
    blocks = []
    ready = is_ready(lesson)
    for i, t in enumerate(lesson["tasks"], start=1):
        if ready:
            badge = LEVEL_BADGE.get(t.get("level", ""), h(t.get("level", "")))
            mark = " · 🧮 kartadan" if t.get("uses_image") else ""
            blocks.append(f"<b>{i}.</b> <i>{badge}{mark}</i>\n{h(t['instruction'])}")
        else:
            mark = " 🖼" if t.get("uses_image") else ""
            blocks.append(f"<b>{i}. {h(t['title'])}</b>{mark}\n<i>{h(t['subjects'])}</i>\n{h(t['instruction'])}")
    note = ("🧮 — ko‘rgazma kartasi bilan bajariladi." if ready else "🖼 — rasm bilan bajariladi.") + \
        " Javoblar «✅ Javoblar» tugmasida."
    return _join("<b>✍️ Integratsiyalashgan topshiriqlar</b>", *blocks, f"<i>{note}</i>")


def fmt_plan(lesson: dict) -> str:
    stages = []
    for st in lesson["lesson_plan"]:
        lines = [f"<b>▸ {h(st['stage'])}</b> — {st['minutes']} daqiqa"]
        if st.get("teacher"):
            lines.append(f"🧑‍🏫 {h(st['teacher'])}")
        if st.get("students"):
            lines.append(f"👧 {h(st['students'])}")
        stages.append("\n".join(lines))
    diff = lesson.get("differentiation") or {}
    diff_lines = []
    if diff.get("support"):
        diff_lines.append(f"• <i>Qiynalayotganlarga:</i> {h(diff['support'])}")
    if diff.get("challenge"):
        diff_lines.append(f"• <i>Kuchli o‘quvchilarga:</i> {h(diff['challenge'])}")
    assessment = [] if is_ready(lesson) else lesson.get("assessment", [])
    source = lesson.get("source") or ""
    return _join(
        "<b>🧑‍🏫 Dars borishi</b>",
        *stages,
        _section("📊 Baholash mezonlari", _bullets(assessment)),
        _section("🧩 Tabaqalashtirish", "\n".join(diff_lines)),
        _section("🏠 Uyga vazifa", h(lesson.get("homework"))),
        _section("⚠️ O‘qituvchi uchun eslatma", _bullets(lesson.get("teacher_notes", []))),
        f"<i>ℹ️ {h(source)}</i>" if source else "",
    )


def _check_line(chk: dict) -> str:
    if chk["ok"] is False:
        return (f"⚠️ Tekshiruv: {h(chk['expr'])} = {h(chk['value'])}, javobda «{h(chk['stated'])}» yozilgan — "
                f"iltimos, tekshirib oling.")
    return f"🧮 {h(chk['expr'])} = {h(chk['value'])} ✅"


def fmt_answers(lesson: dict) -> str:
    tasks = lesson["tasks"]
    criteria = {t.get("criteria") for t in tasks if t.get("criteria")}
    shared = criteria.pop() if len(criteria) == 1 and all(t.get("criteria") for t in tasks) else None
    blocks = []
    for i, t in enumerate(tasks, start=1):
        title = f"{i}-topshiriq" if is_ready(lesson) else f"{i}. {h(t['title'])}"
        lines = [f"<b>{title}</b>"]
        if t.get("answer"):
            lines.append(h(t["answer"]))
        if t.get("criteria") and not shared:
            lines.append(f"<i>📏 {h(t['criteria'])}</i>")
        lines += [_check_line(c) for c in t.get("checks") or []]
        blocks.append("\n".join(lines))
    tail = f"<i>📏 Baholash: {h(shared)}</i>" if shared else ""
    return _join(f"✅ <b>Javoblar</b> (o‘qituvchi uchun) — {h(lesson['title'])}", *blocks, tail)


def count_lines(lesson: dict) -> list[str]:
    exhibit = lesson.get("exhibit")
    if exhibit:
        return [f"{a}: {b}" for a, b in exhibit["rows"]]
    return [f"{g['label']}: {g['count']} ta {g['object_uz']}" for g in lesson["image"]["count_groups"]]


def has_card(lesson: dict) -> bool:
    return bool(lesson.get("exhibit") or lesson["image"].get("count_groups"))


def fmt_card_caption(lesson: dict) -> str:
    lines = "\n".join(f"• {h(x)}" for x in count_lines(lesson))
    exhibit = lesson.get("exhibit")
    if exhibit:
        note = exhibit.get("note") or "Kartadagi ma’lumotlardan topshiriqlarda foydalaning."
        return trim_caption(f"🧮 <b>Ko‘rgazma kartasi</b> — {h(exhibit['title'])}\n{lines}\n\n<i>{h(note)}</i>")
    return trim_caption(
        f"🧮 <b>Hisob kartasi</b> — sonlar aniq:\n{lines}\n\n"
        f"<i>Bolalar sanab chiqsin, so‘ng natijani shu sonlar bilan solishtiring.</i>"
    )


def fmt_image_caption(lesson: dict, note: str = "") -> tuple[str, bool]:
    """Rasm izohi. Qaytaradi: (izoh, savollar izohga sig‘dimi)."""
    desc = lesson["image"].get("description_uz") or ""
    questions = lesson["image"].get("questions") or []
    base = f"🖼 <b>Dars rasmi</b> — {h(lesson['title'])}"
    if desc:
        base += f"\n{h(desc)}"
    tail = f"\n\n{note}" if note else ""
    if questions:
        q_block = "\n\n<b>Rasm bilan ishlash:</b>\n" + "\n".join(f"{i}. {h(q)}" for i, q in enumerate(questions, 1))
        if len(base + q_block + tail) <= 1024:
            return base + q_block + tail, True
    return trim_caption(base + tail), not questions


def image_questions_text(lesson: dict) -> str:
    questions = lesson["image"].get("questions") or []
    if not questions:
        return ""
    return "<b>🖼 Rasm bilan ishlash savollari</b>\n" + "\n".join(f"{i}. {h(q)}" for i, q in enumerate(questions, 1))


def trim_caption(caption: str, limit: int = 1024) -> str:
    """Izoh 1024 belgidan oshsa — teglarsiz qisqartiriladi."""
    if len(caption) <= limit:
        return caption
    plain = html.unescape(re.sub(r"<[^>]+>", "", caption))
    cut = limit - 1
    while cut > 0 and len(h(plain[:cut])) + 1 > limit:
        cut -= 20
    return h(plain[:cut]).rstrip() + "…"


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Uzun xabarni Telegram chegarasiga (4096) moslab bo‘ladi. Teglar paragraf ichida yopiladi."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        pieces = [para]
        if len(para) > limit:
            pieces = []
            buf = ""
            for line in para.split("\n"):
                if len(line) > limit:
                    line = h(re.sub(r"<[^>]+>", "", html.unescape(line)))[: limit - 10] + "…"
                if len(buf) + len(line) + 1 > limit and buf:
                    pieces.append(buf)
                    buf = line
                else:
                    buf = f"{buf}\n{line}" if buf else line
            if buf:
                pieces.append(buf)
        for piece in pieces:
            if len(current) + len(piece) + 2 > limit and current:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def lesson_messages(lesson: dict) -> list[str]:
    """Dars matni: 1) umumiy + ma’lumot, 2) bog‘lanish + jihozlar, 3) topshiriqlar, 4) dars borishi."""
    out: list[str] = []
    first, second = fmt_overview(lesson), fmt_integration(lesson)
    if len(first) + len(second) + 2 <= 4000:
        out.extend(split_message(_join(first, second)))
    else:
        out.extend(split_message(first))
        out.extend(split_message(second))
    for block in (fmt_tasks(lesson), fmt_plan(lesson)):
        out.extend(split_message(block))
    return out


def tasks_voice_text(lesson: dict) -> str:
    ordinals = ["Birinchi", "Ikkinchi", "Uchinchi", "To‘rtinchi", "Beshinchi", "Oltinchi", "Yettinchi",
                "Sakkizinchi", "To‘qqizinchi", "O‘ninchi", "O‘n birinchi", "O‘n ikkinchi"]
    parts = [f"{lesson['title']}. Topshiriqlar."]
    for i, t in enumerate(lesson["tasks"]):
        name = ordinals[i] if i < len(ordinals) else f"{i + 1}-"
        parts.append(f"{name} topshiriq. {t['instruction']}")
    return "\n".join(parts)


def short_label(row_title: str, grade: int, pair_key: str, created: str) -> str:
    a, b = subjects.pair_subjects(pair_key) if subjects.is_valid_pair(pair_key) else ("", "")
    pair_short = f"{subjects.SUBJECTS[a][1]}{subjects.SUBJECTS[b][1]}" if a else ""
    label = f"{created} · {grade}-sinf {pair_short} {row_title}"
    return label if len(label) <= 60 else label[:59] + "…"


# ───────────────────────── Kirill → lotin (ovozdan matnga o‘tganda kerak bo‘lishi mumkin) ─────────────────────────

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "’", "ь": "", "ы": "i", "э": "e",
    "ю": "yu", "я": "ya", "ў": "o‘", "қ": "q", "ғ": "g‘", "ҳ": "h",
}
_VOWELS_CYR = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")


def cyr_to_lat(text: str) -> str:
    """O‘zbek kirill yozuvini lotinga o‘giradi (matnda kirill harflar ko‘p bo‘lsa)."""
    letters = [c for c in text if c.isalpha()]
    cyr = [c for c in letters if "Ѐ" <= c <= "ӿ"]
    if not letters or len(cyr) / len(letters) < 0.3:
        return text
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low == "е":
            prev = text[i - 1] if i > 0 else " "
            rep = "ye" if (not prev.isalpha() or prev in _VOWELS_CYR or prev in "ъьЪЬ") else "e"
        elif low in _CYR:
            rep = _CYR[low]
        else:
            out.append(ch)
            continue
        if ch.isupper() and rep:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            rep = rep.upper() if (nxt.isupper() and len(rep) > 1) else rep[0].upper() + rep[1:]
        out.append(rep)
    return "".join(out)
