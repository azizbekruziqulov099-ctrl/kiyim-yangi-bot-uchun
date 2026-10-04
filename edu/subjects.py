"""
Fanlar, fan juftliklari (integratsiya) va sinflar bo‘yicha ma’lumotlar.
Buyurtmachi bergan 9 ta juftlik shu yerda.
"""
from __future__ import annotations

GRADES = (1, 2, 3, 4)

# kalit: (nomi, emoji, AI uchun qisqa izoh)
SUBJECTS: dict[str, tuple[str, str, str]] = {
    "ona": (
        "Ona tili", "📝",
        "Uzbek native language: sounds and letters, syllables, word formation, parts of speech "
        "(ot, sifat, son, fe’l, olmosh), sentence building, punctuation, spelling (imlo), "
        "writing short texts, speech development (nutq o‘stirish).",
    ),
    "oqish": (
        "O‘qish", "📖",
        "Reading literacy (O‘qish savodxonligi): fluent and expressive reading, comprehension "
        "questions, retelling (qayta hikoyalash), main idea, characters, poems, fairy tales, "
        "proverbs (maqollar), riddles (topishmoqlar), meaning of new words.",
    ),
    "mat": (
        "Matematika", "🔢",
        "Mathematics: counting, number composition, addition/subtraction, multiplication/division "
        "(by grade), word problems (masalalar), comparison, measurement (length, mass, time, money), "
        "geometric shapes, perimeter/area (grades 3–4), patterns, simple fractions (grade 4).",
    ),
    "tab": (
        "Tabiiy fan", "🌿",
        "Natural science: living and non-living nature, plants and animals, seasons and weather, "
        "water, air, soil, human body and health, ecology and protecting nature, simple observations "
        "and experiments.",
    ),
    "tex": (
        "Texnologiya", "✂️",
        "Technology (crafts and practical work): paper work (applikatsiya, origami), modelling with "
        "plasticine, natural materials, measuring, marking and cutting, simple sewing, construction, "
        "safe use of tools, design and decoration of useful objects.",
    ),
}

# Buyurtmachi ro‘yxati bo‘yicha 9 ta juftlik (tartib saqlangan)
PAIRS: list[tuple[str, str, str]] = [
    ("ona_mat", "ona", "mat"),
    ("tab_mat", "tab", "mat"),
    ("ona_tab", "ona", "tab"),
    ("tex_mat", "tex", "mat"),
    ("tex_ona", "tex", "ona"),
    ("oqish_mat", "oqish", "mat"),
    ("oqish_ona", "oqish", "ona"),
    ("oqish_tab", "oqish", "tab"),
    ("oqish_tex", "oqish", "tex"),
]
PAIR_MAP = {key: (a, b) for key, a, b in PAIRS}

TOPIC_SUGGESTIONS: dict[str, list[str]] = {
    "ona_mat": ["Bog‘dagi hosil", "Bozorga sayohat", "Kitob do‘konida", "Kuz fasli",
                "Mening oilam", "Sport musobaqasi"],
    "tab_mat": ["Uy hayvonlari", "Fasllar va ob-havo", "Suv — hayot manbai", "Mevali daraxtlar",
                "Qushlar", "Sog‘lom ovqatlanish"],
    "ona_tab": ["Bahor keldi", "Qishki tabiat", "O‘simliklar dunyosi", "Hayvonlar qishga tayyorlanadi",
                "Suvni tejaylik", "Tabiatni asraylik"],
    "tex_mat": ["Qog‘ozdan geometrik shakllar", "Plastilindan mevalar", "Rangli qog‘ozdan applikatsiya",
                "O‘lchash va kesish", "Tabiiy materiallardan buyum", "Sovg‘a qutisi yasaymiz"],
    "tex_ona": ["Origami: qush yasaymiz", "Bayram tabrik kartochkasi", "Kuzgi barglardan applikatsiya",
                "Kitob uchun xatcho‘p", "Mening ustaxonam", "Qo‘g‘irchoq teatri"],
    "oqish_mat": ["Ertakdagi hisob", "Topishmoqlar va sonlar", "Bo‘g‘irsoq ertagi", "Maqollarda sonlar",
                  "Sholg‘om ertagi", "Do‘stlik haqida hikoya"],
    "oqish_ona": ["Ona yurtim", "Kitob — bilim manbai", "Do‘stlik", "Navro‘z bayrami",
                  "Mehnat — baxt", "Ustoz"],
    "oqish_tab": ["Bahor she’rlari", "Qaldirg‘ochlar", "Ona tabiat", "Kuz manzarasi",
                  "Hayvonlar haqida ertak", "Gullar"],
    "oqish_tex": ["Ertak qahramonlarini yasaymiz", "Kitob uchun muqova", "Qo‘g‘irchoq teatri",
                  "Bayram bezaklari", "Ertak uyi maketi", "Hunarmand usta"],
}

# Sinf bo‘yicha AI uchun ko‘rsatma (dastur doirasi)
GRADE_NOTES: dict[int, str] = {
    1: ("Grade 1 (age 6–7). Numbers within 10 (at most 20); addition and subtraction within 10; "
        "simple shapes and comparison. Children are just learning to read and write: very short "
        "sentences (3–6 words), familiar words, one instruction per task, lots of picture work."),
    2: ("Grade 2 (age 7–8). Numbers within 100; addition and subtraction within 100; introduction "
        "to multiplication and division (tables of 2–5); length (sm, dm, m), time (soat), money "
        "(so‘m). Short texts of 4–8 simple sentences."),
    3: ("Grade 3 (age 8–9). Numbers within 1000; the full multiplication table; division with "
        "remainder; perimeter; mass (kg, g); time. Texts up to 10–12 sentences, simple analysis."),
    4: ("Grade 4 (age 9–10). Multi-digit numbers (up to 1 000 000); four operations; area; simple "
        "fractions; speed–time–distance problems. Texts up to 15 sentences, reasoning and "
        "explaining answers."),
}

DURATIONS = (45, 90)


def subject_name(key: str) -> str:
    return SUBJECTS[key][0]


def subject_emoji(key: str) -> str:
    return SUBJECTS[key][1]


def pair_subjects(pair_key: str) -> tuple[str, str]:
    return PAIR_MAP[pair_key]


def pair_label(pair_key: str, emoji: bool = False) -> str:
    a, b = PAIR_MAP[pair_key]
    if emoji:
        return f"{subject_emoji(a)} {subject_name(a)} + {subject_emoji(b)} {subject_name(b)}"
    return f"{subject_name(a)} + {subject_name(b)}"


def pair_has_math(pair_key: str) -> bool:
    return "mat" in PAIR_MAP.get(pair_key, ())


def is_valid_pair(pair_key: str) -> bool:
    return pair_key in PAIR_MAP
