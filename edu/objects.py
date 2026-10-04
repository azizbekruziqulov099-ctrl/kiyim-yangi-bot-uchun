"""
Hisob kartasi uchun buyumlar katalogi.

Har bir buyum: (kalit, o‘zbekcha nomi, inglizcha nomi).
Rasmi: assets/objects/<kalit>.png (Noto Emoji, Apache 2.0).
AI dars tuzganda sanaladigan buyumlarni faqat shu ro‘yxatdan tanlaydi —
shunda hisob kartasidagi rasm aniq chiqadi.
"""
from __future__ import annotations

import os
import re

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "objects")

OBJECTS: list[tuple[str, str, str]] = [
    ("apple", "olma", "red apple"),
    ("green_apple", "yashil olma", "green apple"),
    ("pear", "nok", "pear"),
    ("peach", "shaftoli", "peach"),
    ("cherries", "gilos", "cherries"),
    ("grapes", "uzum", "bunch of grapes"),
    ("watermelon", "tarvuz", "watermelon"),
    ("melon", "qovun", "melon"),
    ("lemon", "limon", "lemon"),
    ("tangerine", "mandarin", "tangerine"),
    ("banana", "banan", "banana"),
    ("strawberry", "qulupnay", "strawberry"),
    ("kiwi", "kivi", "kiwi fruit"),
    ("pineapple", "ananas", "pineapple"),
    ("blueberries", "chernika", "blueberries"),
    ("tomato", "pomidor", "tomato"),
    ("cucumber", "bodring", "cucumber"),
    ("carrot", "sabzi", "carrot"),
    ("potato", "kartoshka", "potato"),
    ("onion", "piyoz", "onion"),
    ("garlic", "sarimsoq", "garlic"),
    ("eggplant", "baqlajon", "eggplant"),
    ("corn", "makkajo‘xori", "ear of corn"),
    ("hot_pepper", "achchiq qalampir", "red hot pepper"),
    ("bell_pepper", "bulg‘or qalampiri", "bell pepper"),
    ("leafy_green", "ko‘kat", "leafy greens"),
    ("broccoli", "brokkoli", "broccoli"),
    ("mushroom", "qo‘ziqorin", "mushroom"),
    ("peanuts", "yeryong‘oq", "peanuts"),
    ("chestnut", "kashtan", "chestnut"),
    ("bread", "buxanka non", "bread loaf"),
    ("flatbread", "non", "round Uzbek flatbread"),
    ("egg", "tuxum", "egg"),
    ("milk", "sut", "glass of milk"),
    ("cookie", "pechenye", "cookie"),
    ("cake", "tort", "slice of cake"),
    ("candy", "konfet", "wrapped candy"),
    ("lollipop", "tayoqchali konfet", "lollipop"),
    ("honey", "asal", "honey pot"),
    ("cheese", "pishloq", "cheese wedge"),
    ("teacup", "piyola", "tea bowl"),
    ("teapot", "choynak", "teapot"),
    ("bowl", "kosa", "bowl with spoon"),
    ("spoon", "qoshiq", "spoon"),
    ("bird", "qush", "small bird"),
    ("chick", "jo‘ja", "baby chick"),
    ("hen", "tovuq", "hen"),
    ("rooster", "xo‘roz", "rooster"),
    ("duck", "o‘rdak", "duck"),
    ("goose", "g‘oz", "goose"),
    ("sheep", "qo‘y", "sheep"),
    ("ram", "qo‘chqor", "ram"),
    ("goat", "echki", "goat"),
    ("cow", "sigir", "cow"),
    ("ox", "ho‘kiz", "ox"),
    ("horse", "ot", "horse"),
    ("donkey", "eshak", "donkey"),
    ("rabbit", "quyon", "rabbit"),
    ("cat", "mushuk", "cat"),
    ("dog", "it", "dog"),
    ("fish", "baliq", "fish"),
    ("tropical_fish", "rangli baliq", "tropical fish"),
    ("butterfly", "kapalak", "butterfly"),
    ("bee", "ari", "honeybee"),
    ("ladybug", "xonqizi", "ladybug"),
    ("ant", "chumoli", "ant"),
    ("snail", "shilliqqurt", "snail"),
    ("frog", "baqa", "frog"),
    ("turtle", "toshbaqa", "turtle"),
    ("hedgehog", "tipratikan", "hedgehog"),
    ("squirrel", "olmaxon", "squirrel"),
    ("owl", "boyo‘g‘li", "owl"),
    ("dove", "kabutar", "dove"),
    ("eagle", "burgut", "eagle"),
    ("parrot", "to‘tiqush", "parrot"),
    ("swan", "oqqush", "swan"),
    ("penguin", "pingvin", "penguin"),
    ("bear", "ayiq", "bear"),
    ("fox", "tulki", "fox"),
    ("wolf", "bo‘ri", "wolf"),
    ("deer", "bug‘u", "deer"),
    ("camel", "tuya", "camel"),
    ("elephant", "fil", "elephant"),
    ("lion", "sher", "lion"),
    ("monkey", "maymun", "monkey"),
    ("mouse", "sichqon", "mouse"),
    ("giraffe", "jirafa", "giraffe"),
    ("zebra", "zebra", "zebra"),
    ("bug", "qo‘ng‘iz", "beetle"),
    ("worm", "chuvalchang", "worm"),
    ("pencil", "qalam", "pencil"),
    ("pen", "ruchka", "pen"),
    ("crayon", "rangli qalam", "crayon"),
    ("paintbrush", "mo‘yqalam", "paintbrush"),
    ("palette", "bo‘yoq (palitra)", "paint palette"),
    ("ruler", "chizg‘ich", "straight ruler"),
    ("triangle_ruler", "uchburchak chizg‘ich", "triangular ruler"),
    ("scissors", "qaychi", "scissors"),
    ("book", "kitob", "closed book"),
    ("books", "kitoblar", "stack of books"),
    ("open_book", "ochiq kitob", "open book"),
    ("notebook", "daftar", "notebook"),
    ("backpack", "maktab sumkasi", "school backpack"),
    ("globe", "globus", "globe"),
    ("abacus", "cho‘t", "abacus"),
    ("paperclip", "qisqich", "paperclip"),
    ("pushpin", "knopka", "pushpin"),
    ("envelope", "konvert (xat)", "envelope"),
    ("bell", "qo‘ng‘iroq", "bell"),
    ("clock", "soat", "alarm clock"),
    ("magnifier", "lupa", "magnifying glass"),
    ("page", "varaq", "sheet of paper"),
    ("tree", "daraxt", "deciduous tree"),
    ("fir_tree", "archa", "evergreen tree"),
    ("palm", "palma", "palm tree"),
    ("seedling", "nihol", "seedling"),
    ("herb", "o‘t", "herb"),
    ("clover", "sebarga", "four leaf clover"),
    ("maple_leaf", "chinor bargi", "maple leaf"),
    ("fallen_leaf", "xazon barg", "fallen leaf"),
    ("tulip", "lola", "tulip"),
    ("rose", "atirgul", "rose"),
    ("sunflower", "kungaboqar", "sunflower"),
    ("blossom", "gul", "flower blossom"),
    ("cherry_blossom", "o‘rik guli", "blossom flower"),
    ("bouquet", "guldasta", "bouquet"),
    ("cactus", "kaktus", "cactus"),
    ("wheat", "bug‘doy boshog‘i", "sheaf of wheat"),
    ("sun", "quyosh", "sun"),
    ("cloud", "bulut", "cloud"),
    ("rain_cloud", "yomg‘ir buluti", "rain cloud"),
    ("snowflake", "qor parchasi", "snowflake"),
    ("droplet", "tomchi", "water droplet"),
    ("star", "yulduz", "star"),
    ("moon", "oy", "crescent moon"),
    ("rainbow", "kamalak", "rainbow"),
    ("umbrella", "soyabon", "umbrella"),
    ("snowman", "qor odam", "snowman"),
    ("fire", "olov", "fire"),
    ("rock", "tosh", "rock"),
    ("wood", "yog‘och", "wood logs"),
    ("shell", "chig‘anoq", "spiral shell"),
    ("soccer_ball", "futbol to‘pi", "soccer ball"),
    ("basketball", "basketbol to‘pi", "basketball"),
    ("volleyball", "voleybol to‘pi", "volleyball"),
    ("balloon", "havo shari", "balloon"),
    ("gift", "sovg‘a", "wrapped gift"),
    ("teddy_bear", "ayiqcha (o‘yinchoq)", "teddy bear"),
    ("kite", "varrak", "kite"),
    ("nesting_doll", "matryoshka", "nesting dolls"),
    ("puzzle", "pazl bo‘lagi", "puzzle piece"),
    ("car", "mashina", "car"),
    ("bus", "avtobus", "bus"),
    ("bicycle", "velosiped", "bicycle"),
    ("airplane", "samolyot", "airplane"),
    ("boat", "qayiq", "sailboat"),
    ("train", "poyezd", "locomotive"),
    ("tractor", "traktor", "tractor"),
    ("house", "uy", "house"),
    ("school", "maktab", "school building"),
    ("basket", "savat", "basket"),
    ("bucket", "chelak", "bucket"),
    ("shopping_bag", "xarid sumkasi", "shopping bags"),
    ("box", "quti", "cardboard box"),
    ("coin", "tanga", "coin"),
    ("candle", "sham", "candle"),
    ("bulb", "lampochka", "light bulb"),
    ("key", "kalit", "key"),
    ("hammer", "bolg‘a", "hammer"),
    ("screwdriver", "otvyortka", "screwdriver"),
    ("bolt", "bolt va gayka", "nut and bolt"),
    ("saw", "arra", "carpentry saw"),
    ("thread", "ip g‘altagi", "spool of thread"),
    ("yarn", "kalava ip", "ball of yarn"),
    ("needle", "igna", "sewing needle"),
    ("magnet", "magnit", "magnet"),
    ("gem", "qimmatbaho tosh", "gem stone"),
    ("crown", "toj", "crown"),
    ("tshirt", "futbolka", "t-shirt"),
    ("dress", "ko‘ylak", "dress"),
    ("socks", "paypoq", "socks"),
    ("gloves", "qo‘lqop", "gloves"),
    ("scarf", "sharf", "scarf"),
    ("cap", "kepka", "cap"),
    ("shoe", "krossovka", "running shoe"),
    ("red_circle", "qizil doira", "red circle"),
    ("blue_circle", "ko‘k doira", "blue circle"),
    ("green_circle", "yashil doira", "green circle"),
    ("yellow_circle", "sariq doira", "yellow circle"),
    ("red_square", "qizil kvadrat", "red square"),
    ("blue_square", "ko‘k kvadrat", "blue square"),
    ("green_square", "yashil kvadrat", "green square"),
    ("triangle", "qizil uchburchak", "red triangle"),
    ("diamond", "romb", "orange diamond"),
    ("heart", "yurakcha", "red heart"),
]

_BY_KEY = {k: (k, uz, en) for k, uz, en in OBJECTS}

# Katalogda alohida rasmi yo‘q, lekin yaqin rasm bilan ko‘rsatsa bo‘ladigan nomlar
ALIASES = {
    "chumchuq": "bird", "qaldirgoch": "bird", "mayna": "bird", "musicha": "dove", "kaptar": "dove",
    "joja": "chick", "olcha": "cherries", "anor": "apple", "orik": "peach", "uzum boshi": "grapes",
    "qalamcha": "pencil", "ruchka": "pen", "kitobcha": "book", "gullar": "blossom", "lolaqizgaldoq": "tulip",
}


def keys() -> list[str]:
    return [k for k, _, _ in OBJECTS]


def exists(key: str) -> bool:
    return key in _BY_KEY


def uz_name(key: str) -> str:
    item = _BY_KEY.get(key)
    return item[1] if item else key


def en_name(key: str) -> str:
    item = _BY_KEY.get(key)
    return item[2] if item else key


def image_path(key: str) -> str | None:
    if key not in _BY_KEY:
        return None
    path = os.path.join(ASSETS_DIR, f"{key}.png")
    return path if os.path.exists(path) else None


def _simplify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[‘’ʻʼ`'\-]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _variants(s: str) -> list[str]:
    """So‘zning birlik shakllari: olmalar -> olma, apples -> apple, cherries -> cherry."""
    out = [s]
    for suffix, repl in (("lari", ""), ("lar", ""), ("ies", "y"), ("es", ""), ("s", "")):
        if s.endswith(suffix) and len(s) > len(suffix) + 2:
            out.append(s[: -len(suffix)] + repl)
    return out


def guess_key(*names: str) -> str | None:
    """AI ro‘yxatdan tashqari kalit bersa, nomi bo‘yicha eng yaqinini topadi."""
    for name in names:
        s = _simplify(name)
        if not s:
            continue
        for v in _variants(s):
            if v in ALIASES:
                return ALIASES[v]
            if v.replace(" ", "_") in _BY_KEY:
                return v.replace(" ", "_")
            for k, uz, en in OBJECTS:
                if v in (_simplify(uz), _simplify(en)):
                    return k
        # so‘z darajasida: "qizil olmalar" -> olma, "small birds" -> bird
        words = s.split()
        for k, uz, en in OBJECTS:
            for nm in (_simplify(uz), _simplify(en), k.replace("_", " ")):
                for w in words:
                    if nm in _variants(w):
                        return k
        # asosiy so‘z bo‘yicha: "uchburchak" -> "qizil uchburchak", "kvadrat" -> "qizil kvadrat"
        if len(words) == 1:
            for k, uz, en in OBJECTS:
                last = _simplify(uz).split()[-1] if _simplify(uz) else ""
                if last and last in _variants(words[0]) and len(last) >= 4:
                    return k
    return None


def prompt_catalog() -> str:
    """AI uchun qisqa ro‘yxat: kalit=o‘zbekcha nomi."""
    return ", ".join(f"{k}={uz}" for k, uz, _ in OBJECTS)
