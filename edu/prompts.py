"""
AI uchun ko‘rsatmalar (prompt) va javob tuzilmasi (JSON schema).

Asosiy g‘oya (buyurtmachi talabi): bitta umumiy vaziyat (matn + rasm) ikkala fanga
birdaniga xizmat qiladi. Rasm bezak emas — undan kuzatish, sanash, gap tuzish uchun
foydalaniladi. Sanaladigan buyumlar soni aniq bo‘lishi uchun "count_groups" maydoni bor:
undan bot alohida "hisob kartasi" rasmini o‘zi chizadi (sonlar 100% to‘g‘ri chiqadi).
"""
from __future__ import annotations

from . import objects, subjects

# ───────────────────────── Dars JSON tuzilmasi ─────────────────────────


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required if required is not None else list(props.keys()),
        "properties": props,
    }


_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}


def lesson_schema() -> dict:
    count_group = _obj({
        "label": {"type": "string", "description": "Short Uzbek label of the group, e.g. 1-savat"},
        "where_en": {"type": "string", "description": "Where this group is in the picture, in English"},
        "object_key": {"type": "string", "enum": objects.keys()},
        "object_uz": {"type": "string", "description": "Uzbek name of the object"},
        "count": {"type": "integer"},
    })
    task = _obj({
        "title": _STR,
        "subjects": _STR,
        "instruction": _STR,
        "uses_image": {"type": "boolean"},
        "answer": _STR,
        "check_expression": {"type": "string", "description": "Arithmetic expression for checking, e.g. 6+4; empty if no calculation"},
        "check_result": {"type": "string", "description": "Plain number result of check_expression; empty if none"},
    })
    stage = _obj({
        "stage": _STR,
        "minutes": {"type": "integer"},
        "teacher": _STR,
        "students": _STR,
    })
    return _obj({
        "title": _STR,
        "summary": _STR,
        "objectives": _obj({
            "subject_a": _STR_LIST,
            "subject_b": _STR_LIST,
            "tarbiyaviy": _STR_LIST,
        }),
        "teacher_info": _STR,
        "key_points": _STR_LIST,
        "child_text": _STR,
        "integration": _obj({
            "idea": _STR,
            "subject_a_part": _STR,
            "subject_b_part": _STR,
        }),
        "vocabulary": {"type": "array", "items": _obj({"word": _STR, "meaning": _STR})},
        "materials": _STR_LIST,
        "image": _obj({
            "scene_en": _STR,
            "description_uz": _STR,
            "count_groups": {"type": "array", "items": count_group},
            "questions": _STR_LIST,
        }),
        "tasks": {"type": "array", "items": task},
        "lesson_plan": {"type": "array", "items": stage},
        "assessment": _STR_LIST,
        "differentiation": _obj({"support": _STR, "challenge": _STR}),
        "homework": _STR,
        "voice_text": _STR,
    })


SYSTEM_PROMPT = """You are an experienced methodologist of primary education in Uzbekistan (boshlang‘ich ta’lim metodisti).
You design INTEGRATED lessons (fanlararo integratsiya) for grades 1–4 that follow the spirit of Uzbekistan’s national curriculum (Milliy o‘quv dasturi).
The user is a primary-school teacher or a future teacher (student) preparing for a real lesson. Your JSON is shown to them directly and used in class.

LANGUAGE
- Every field except those ending in "_en" must be in correct literary Uzbek, Latin script, modern orthography: write o‘ and g‘ with the ‘ sign, and the tutuq belgisi as ’ (ta’lim, she’r, ma’no). No Cyrillic, no Russian or English words where an Uzbek word exists.
- Child-facing texts (child_text, task instructions, image questions, voice_text) must match the grade: short clear sentences, familiar words, friendly tone.

THE CORE OF INTEGRATION
- Build the whole lesson around ONE shared situation (a short story, a scene from life, a fairy-tale moment, an observation). The same text and the same picture serve BOTH subjects at once.
- Do NOT write two separate mini-lessons. Every task must require knowledge or skills from BOTH subjects together (for example: compose a sentence about the picture AND solve the problem, then write the answer as a full sentence).
- integration.idea explains the shared situation; subject_a_part and subject_b_part say concretely what each subject practises through it.

THE PICTURE IS A TEACHING TOOL, NOT DECORATION
- A picture will be drawn from image.scene_en. Tasks and image.questions must refer to it (observe, count, compare, describe, compose sentences, find details).
- scene_en: a precise English description for an illustrator: setting, characters, every important object with its exact number and position. Keep it simple and uncluttered (one scene, 2–4 object groups). Never ask for written text, letters or numbers in the picture.
- image.count_groups lists the exact quantities that appear in the picture and are used in tasks. For pairs with Matematika give 1–4 groups; otherwise give groups only if counting is really used (an empty list is fine).
- object_key must be one of the allowed keys given by the user, and the story must use exactly that object (choose the story objects from the list). Keep each picture group at 10 objects or fewer; larger numbers belong in the text, not in the picture. label is a short Uzbek name of the group (1-savat, Chap shoxda, Aziz), where_en says where the group is in the picture.
- The numbers in child_text, count_groups, tasks and answers must agree with each other.

MATHEMATICS MUST BE CORRECT
- Use only numbers and operations that fit the grade.
- Every task that contains a calculation must have check_expression (digits, + - * / and parentheses only, for example (6+4)-3) and check_result (one plain number, for example 7). Double-check them. Tasks without calculation have empty strings in both fields.

TASKS
- 6–8 tasks from easy to harder, varied: observation of the picture, oral speech, writing, calculation, word problem, practical or creative work, pair/group work, a short game.
- title: 2–4 words. subjects: e.g. "Ona tili + Matematika". instruction: addressed to pupils, clear, imperative. answer: the expected answer or assessment criteria for the teacher.

LESSON PLAN (lesson_plan)
- 5–7 stages in the usual order (Tashkiliy qism, Motivatsiya/takrorlash, Yangi mavzu, Mustahkamlash, Amaliy ish, Baholash va refleksiya, Uyga vazifa). The minutes must add up EXACTLY to the lesson duration.
- teacher and students describe concrete actions: when the picture is shown, which task numbers are used, how the teacher summarises.

OTHER FIELDS
- teacher_info: 5–9 sentences of accurate, useful information on the topic for the teacher, connected to both subjects. key_points: 3–6 short facts or examples for pupils.
- objectives: 2–3 items for each subject and 1–2 upbringing (tarbiyaviy) aims.
- vocabulary: 3–6 new words with child-friendly meanings. materials: what the teacher needs.
- assessment: 3–5 criteria. differentiation.support: help for weaker pupils; differentiation.challenge: an extra task for stronger pupils.
- voice_text: a warm narration (at most 900 characters) that the bot will read aloud to pupils, usually based on child_text.

CULTURE AND SAFETY
- Uzbek context: names like Aziz, Malika, Sardor, Zarina, Jasur, Nilufar; local fruits, bog‘, mahalla, bozor; money in so‘m. Positive values (mehnat, do‘stlik, tabiatni asrash, kattalarni hurmat qilish). No brands, no violence, nothing unsuitable for children.
- Facts must be accurate. If the topic is vague, interpret it sensibly for primary school. If it is unsuitable for children, choose a close safe topic and say so in summary.

EXAMPLE OF THE INTEGRATION STYLE (grade 2, Ona tili + Matematika, topic "Bog‘dagi hosil") — shows depth and style, do not copy it:
child_text: "Kuz keldi. Aziz va Malika bog‘dan olma terishdi. Aziz birinchi savatga 6 ta olma soldi. Malika ikkinchi savatga 4 ta olma soldi."
count_groups: [{"label": "1-savat", "where_en": "in the left basket", "object_key": "apple", "object_uz": "olma", "count": 6}, {"label": "2-savat", "where_en": "in the right basket", "object_key": "apple", "object_uz": "olma", "count": 4}]
task: {"title": "Kuzat, gapir, hisobla", "subjects": "Ona tili + Matematika", "instruction": "Rasmni kuzating. Har bir savat haqida bittadan gap tuzing. Ikkala savatdagi olmalar sonini hisoblang va javobni to‘liq gap bilan yozing.", "uses_image": true, "answer": "Masalan: «Birinchi savatda 6 ta olma bor.» 6 + 4 = 10. «Ikkala savatda jami 10 ta olma bor.»", "check_expression": "6+4", "check_result": "10"}

Return ONLY one JSON object that matches the schema. No markdown, no comments."""


def build_lesson_prompt(grade: int, pair_key: str, topic: str, minutes: int,
                        extra: str = "", with_image: bool = True) -> str:
    a, b = subjects.pair_subjects(pair_key)
    name_a, _, desc_a = subjects.SUBJECTS[a]
    name_b, _, desc_b = subjects.SUBJECTS[b]
    lines = [
        "Prepare an integrated lesson.",
        f"Grade: {grade}-sinf. {subjects.GRADE_NOTES.get(grade, '')}",
        f"Subjects: {name_a} + {name_b}",
        f"Subject A (objectives.subject_a, integration.subject_a_part) — {name_a}: {desc_a}",
        f"Subject B (objectives.subject_b, integration.subject_b_part) — {name_b}: {desc_b}",
        f"Topic (mavzu): «{topic}»",
        f"Lesson duration: {minutes} minutes — lesson_plan minutes must add up to exactly {minutes}.",
        f"Teacher's extra wishes: {extra.strip() if extra and extra.strip() else 'none'}",
    ]
    if with_image:
        lines.append("Picture: an illustration will be generated from image.scene_en and shown in class.")
    else:
        lines.append("Picture: the teacher does not need an AI illustration this time, but still fill the "
                     "image fields; the bot draws an exact counting card from image.count_groups.")
    if subjects.pair_has_math(pair_key):
        lines.append("Because Matematika is one of the subjects, image.count_groups must contain 1–4 groups "
                     "and at least 3 tasks must contain calculations with check_expression.")
    lines.append("Allowed object_key values: " + ", ".join(objects.keys()))
    lines.append("Return JSON only.")
    return "\n".join(lines)


# ───────────────────────── Rasm uchun prompt ─────────────────────────

IMAGE_STYLE = (
    "Style: bright, friendly children's textbook illustration, flat vector style with soft shading, "
    "clean outlines, warm cheerful colours, simple uncluttered light background. "
    "Central Asian (Uzbek) everyday setting where it fits; children look kind and are modestly dressed. "
    "Absolutely no text, letters, numbers, captions, labels, watermarks or logos anywhere in the image."
)


def _plural_en(name: str, n: int) -> str:
    if n == 1:
        return name
    if name.endswith(("s", "sh", "ch", "x")):
        return name + "es"
    if name.endswith("y") and not name.endswith(("ay", "ey", "oy", "uy")):
        return name[:-1] + "ies"
    return name + "s"


def drawable_groups(lesson: dict) -> list[dict]:
    """Rasmda aniq chizish mumkin bo‘lgan (10 tagacha) guruhlar."""
    return [g for g in lesson.get("image", {}).get("count_groups", []) if 1 <= g.get("count", 0) <= 10]


def build_image_prompt(lesson: dict, grade: int, strict: bool = False) -> str:
    image = lesson.get("image", {})
    scene = (image.get("scene_en") or "").strip() or f"A scene about {lesson.get('title', '')}"
    parts = [
        f"Illustration for an Uzbek primary school lesson (grade {grade}).",
        f"Scene: {scene}",
    ]
    groups = drawable_groups(lesson)
    if groups:
        items = []
        for g in groups:
            name = objects.en_name(g["object_key"])
            where = (g.get("where_en") or "").strip()
            items.append(f"exactly {g['count']} {_plural_en(name, g['count'])}" + (f" {where}" if where else ""))
        parts.append(
            "Countable objects — draw EXACTLY these numbers, each object fully visible, clearly separated, "
            "not overlapping, easy for a child to count: " + "; ".join(items) + "."
        )
        if strict:
            parts.append("Counting accuracy is the most important requirement: do not add extra copies of these "
                         "objects anywhere else in the picture.")
    parts.append(IMAGE_STYLE)
    return "\n".join(parts)


# ───────────────────────── Rasmni tekshirish ─────────────────────────


def vision_schema() -> dict:
    return _obj({
        "groups": {"type": "array", "items": _obj({"index": {"type": "integer"}, "counted": {"type": "integer"}})},
        "has_text": {"type": "boolean"},
    })


def build_vision_prompt(groups: list[dict]) -> str:
    lines = [
        "You check an illustration for a primary-school counting task.",
        "Count very carefully, object by object, how many of each item are visible in the described place:",
    ]
    for i, g in enumerate(groups, start=1):
        name = objects.en_name(g["object_key"])
        where = (g.get("where_en") or "").strip()
        lines.append(f"{i}) {_plural_en(name, 2)}{(' ' + where) if where else ''}")
    lines.append("Also report whether the picture contains any written text, letters or digits.")
    lines.append('Return JSON: {"groups": [{"index": 1, "counted": 0}], "has_text": false}')
    return "\n".join(lines)
