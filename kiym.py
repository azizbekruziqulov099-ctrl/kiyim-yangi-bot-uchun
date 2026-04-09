import json
from telegram import KeyboardButton
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import asyncio
import os

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

product_locks = {}
products = []
carts = {}
orders = {}
order_id_counter = 1

def get_category_buttons(context):
    return [
        [f"👕 2 talik ({count_products(lambda p: p['category'].lower()=='2 talik kiyim')})",
         f"👕 3 talik ({count_products(lambda p: p['category'].lower()=='3 talik kiyim')})"],

        [f"👕 Futbolka ({count_products(lambda p: p['category'].lower()=='futbolka')})",
         f"👖 Shim ({count_products(lambda p: p['category'].lower()=='shim')})"],

        [f"🧥 Qalin ({count_products(lambda p: p['category'].lower()=='qalin kiyim')})",
         f"🩳 Shortik ({count_products(lambda p: p['category'].lower()=='shortik')})"],

        [f"👟 Oyoq ({count_products(lambda p: p['category'].lower()=='oyoq kiyim')})",
         f"🧢 Bosh ({count_products(lambda p: p['category'].lower()=='bosh kiyim')})"],

        [f"🩲 Ichki ({count_products(lambda p: p['category'].lower()=='ichki kiyim')})"],

        ["🔙 Orqaga", "🏠 Bosh menyu"]
    ]
def filter_check(p, context):
    # gender
    if context.user_data.get("filter_gender"):
        if p["gender"] != context.user_data.get("filter_gender"):
            return False

    # size
    if context.user_data.get("filter_size"):
        if p["size"] != context.user_data.get("filter_size"):
            return False

    # season
    if context.user_data.get("filter_season"):
        if p["season"] != context.user_data.get("filter_season"):
            return False

    # category
    if context.user_data.get("filter_category"):
        if p["category"].lower() != context.user_data.get("filter_category"):
            return False

    # mavjudlik
    if (p["count"] - p.get("reserved", 0)) <= 0:
        return False

    return True

def count_products(filter_func=None):
    total = 0
    for p in products:
        available = p["count"] - p.get("reserved", 0)
        if available > 0:
            if not filter_func or filter_func(p):
                total += available
    return total

def save_products():
    with open("products.json", "w") as f:
        json.dump(products, f, indent=4)


def load_products():
    global products
    try:
        with open("products.json", "r") as f:
            products = json.load(f)
    except:
        products = []


def save_orders():
    with open("orders.json", "w") as f:
        json.dump(orders, f, indent=4)


def load_orders():
    global orders
    try:
        with open("orders.json", "r") as f:
            orders = json.load(f)
    except:
        orders = {}


# 🔥 ENG MUHIM QISM
load_products()   
load_orders()
for p in products:
    if "reserved" not in p:
        p["reserved"] = 0

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        ["🗑 Tozalash", "🏠 Bosh menyu"],
        ["🛍 Kiyimlar", "🧺 Savat"],
    ],
    resize_keyboard=True
)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🛍 Kiyimlar", "🧺 Savat"],
        ["ℹ️ Yordam", "📏 Razmer jadvali"]
    ],
    resize_keyboard=True
)

BACK_BUTTON = ["🔙 Orqaga"]
HOME_BUTTON = ["🏠 Bosh menyu"]
CART_BUTTON = ["🧺 Savat"]

CATEGORIES = [
    "👕 2 talik kiyim (dvoyka)",
    "👕 3 talik kiyim (troyka)",
    "👕 Futbolka",
    "👖 Shim",
    "🧥 Qalin kiyim",
    "🩳 Shortik",
    "👟 oyoq kiyim",
    "🧢 Bosh kiyim",
    "🩲 Ichki kiyim"
]
# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "👑 Admin panel",
            reply_markup=ADMIN_MENU
        )
    else:
        await update.message.reply_text(
            "Assalomu alaykum 👋",
            reply_markup=MAIN_MENU
        )


# RASM QABUL (ADMIN)
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    print(update.message.photo[-1].file_id)

    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "gender"

    keyboard = [["👦 O‘g‘il", "👧 Qiz"]]
    await update.message.reply_text(
        "Kim uchun?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
# HANDLE
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # ===== ADMIN FLOW =====
    if context.user_data.get("step") == "gender":
        gender = text.replace("👦 ", "").replace("👧 ", "")
        context.user_data["gender"] = gender
        context.user_data["step"] = "season"

        keyboard = [["☀️ Yozgi", "❄️ Qishki"], ["🌸 Bahor", "🍂 Kuz"]]
        await update.message.reply_text(
            "Fasl tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    
    elif text == "🗑 Tozalash":
        if update.effective_user.id != ADMIN_ID:
            return

        keyboard = [
            [InlineKeyboardButton("✅ HA", callback_data="clear_yes")],
            [InlineKeyboardButton("❌ YO‘Q", callback_data="clear_no")]
        ]

        await update.message.reply_text(
            "⚠️ Rostdan ham barcha mahsulotlarni o‘chirmoqchimisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "ℹ️ Yordam":
        await update.message.reply_text(
            "Bolalar uchun kiyim razmerini to‘g‘ri tanlash uchun avvalo bolaning bo‘yini aniqlash kerak: "
            "bola oyoq kiyimsiz, devorga tik turgan holatda boshiga tekis buyum qo‘yilib belgi qilinadi va poldan shu belgigacha masofa santimetrda o‘lchanadi; "
            "masalan, agar bola 100 sm chiqsa, jadvaldan 98 yoki 104 razmer tanlanadi.\n\n"

            "Ko‘krak o‘lchami futbolka va ko‘ylaklar uchun olinadi: santimetr lenta ko‘krakning eng keng joyidan aylantirib, siqmasdan va bo‘sh qoldirmasdan o‘lchanadi; "
            "bel o‘lchami esa shim va shortik uchun kerak bo‘lib, belning tabiiy qismidan aylantirib o‘lchanadi.\n\n"

            "Agar o‘lchash qiyin bo‘lsa, eng oson usul — bolaning hozir yaxshi kelayotgan kiyimini tekis joyga qo‘yib, uzunligi va kengligini o‘lchab, yangi kiyimni shu o‘lchamga yaqin tanlashdir.\n\n"

            "Jadvaldan foydalanishda asosiy mezon — bola bo‘yi: jadvalda berilgan bo‘y oralig‘iga mos razmer tanlanadi va odatda qulaylik uchun 2–4 sm zahira bilan olish tavsiya etiladi.\n\n"

            "Shuni inobatga olish kerakki, barcha o‘lchamlar umumiy standartlarga asoslangan bo‘lib, har bir brend yoki modelga qarab biroz farq qilishi mumkin, "
            "shuning uchun jadvaldagi qiymatlar yo‘naltiruvchi (taxminiy) hisoblanadi."
        )
    elif text == "📏 Razmer jadvali":

        images = [
            "AgACAgIAAxkBAAIUMGnT3_ygo9D71LcXU02CpCCnGDvcAAILGGsbKLCgSnIkhjlFioIaAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUUGnT4g8wUh7XRa14PIXIiHIykOChAAIgGGsbKLCgSu9RA0Vm4ErIAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUUWnT4g8PCecHEZK_udyediGEfaiOAAIhGGsbKLCgSsvCSMSCP42IAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUUmnT4g8SZYg3u7rRQDj71gPoMG3OAAIiGGsbKLCgSkZn-iOydmfQAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUU2nT4g_PLZYFspoJ6ek9o-5HGaq2AAIjGGsbKLCgSlTXOV5vrhoFAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUVGnT4g-K24aZF0GRCdvgz4nU2_ACAAIkGGsbKLCgSjiUy8Y98avLAQADAgADeQADOwQ",
            "AgACAgIAAxkBAAIUVWnT4g_HEGtzuOYebzIgQHBmLZM2AAIlGGsbKLCgSqauzPvcMoOYAQADAgADeQADOwQ"
        ]

        for img in images:
            await update.message.reply_photo(photo=img)

        await update.message.reply_text("🏠 Bosh menyu", reply_markup=MAIN_MENU)
        
    elif context.user_data.get("step") == "size_season" and text in ["☀️ Yozgi","❄️ Qishki","🌸 Bahor","🍂 Kuz"]:
        season = text.replace("☀️ ", "").replace("❄️ ", "").replace("🌸 ", "").replace("🍂 ", "")
        context.user_data["filter_season"] = season
        context.user_data["step"] = "size_category"

       
        keyboard = get_category_buttons(context)
        await update.message.reply_text(
            "Kategoriya tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        ) 
        return  

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
                and (p["count"] - p.get("reserved", 0)) > 0
            ):
                found = True

                keyboard = [
                    [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{i}")]
                ]

                await update.message.reply_photo(
                    photo=p["photo"],
                    caption=f"{p['name']}\n{p['size']}\n{p['price']}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if not found:
            await update.message.reply_text("❌ Mos mahsulot yo‘q")         
    elif text == "❌ Lokatsiya ishlamayapti":
        user_id = update.effective_user.id
        cart = carts.get(user_id, {})

        if not cart:
            await update.message.reply_text("❌ Savat bo‘sh")
            return

        total = 0
        for idx, item in cart.items():
            qty = item["qty"]
            p = products[int(idx)]

            price = int(
                p["price"].lower()
                .replace("ming", "000")
                .replace("mong", "000")
                .replace("ning", "000")
                .replace("som", "")
                .replace("mig", "000")
                .replace("so'm", "")
                .replace("soʻm", "")
                .replace(" ", "")
            )
            total += price * qty

        final = total + 0

        # 🔥 ENG MUHIM — TEMP ORDER
        context.user_data["temp_order"] = {
            "cart": cart,
            "location": {},   # 🔥 bo‘sh dict (None emas!)
            "total": final,
            "type": "delivery"
        }

        context.user_data["order_step"] = "phone"

        await update.message.reply_text(
    "🚚 Dastavka narxi taxminan 20 000 - 50 000 so‘m atrofida bo‘ladi.\n\n📞 Telefon raqamingizni yozing:"
        )
    elif context.user_data.get("order_step") == "manual_location":
        address = text

        user_id = update.effective_user.id
        cart = carts.get(user_id, {})

        total = 0
        for idx, item in cart.items():
            qty = item["qty"]
            p = products[int(idx)]

            price = int(
                p["price"].lower()
                .replace("ming", "000")
                .replace("so'm", "")
                .replace("soʻm", "")
                .replace(" ", "")
            )
            total += price * qty

        delivery = 0
        final = total + delivery

        context.user_data["temp_order"] = {
            "cart": cart,
            "location": {"text": address},
            "total": final,
            "type": "delivery"
        }

        context.user_data["order_step"] = "phone"

        await update.message.reply_text("📞 Telefon yuboring:")    

    elif text == "🔙 Orqaga":
        step = context.user_data.get("step")

        # 🔹 size_category → size_season
        if step == "size_category":
            context.user_data["step"] = "size_season"

            keyboard = [
                ["☀️ Yozgi","❄️ Qishki"],
                ["🌸 Bahor","🍂 Kuz"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Fasl tanlang:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 size_season → size_filter
        elif step == "size_season":
            context.user_data["step"] = "size_filter"

            keyboard = [
                ["50-55","55-60","60-65","65-70"],["70-75","75-80","80-85","85-90"],["90-95","95-100","105-110","110-115"],["115-120","120-125","125-130"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Razmer tanlang:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 size_filter → choose_type
        elif step == "size_filter":
            context.user_data["step"] = "choose_type"

            keyboard = [
                ["📏 Razmer bo‘yicha", "📂 Umumiy"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Qanday qidirasiz?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 choose_type → gender
        elif step == "choose_type":
            context.user_data["step"] = "user_gender"

            keyboard = [
                ["👦 O‘g‘il", "👧 Qiz"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Kim uchun:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 user_category → user_season
        elif step == "user_category":
            context.user_data["step"] = "user_season"

            keyboard = [
                ["☀️ Yozgi","❄️ Qishki"],
                ["🌸 Bahor","🍂 Kuz"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Fasl tanlang:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 user_season → choose_type
        elif step == "user_season":
            context.user_data["step"] = "choose_type"

            keyboard = [
                ["📏 Razmer bo‘yicha", "📂 Umumiy"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Qanday qidirasiz?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

        # 🔹 default → bosh menyu
        else:
            context.user_data.clear()
            await update.message.reply_text("🏠 Bosh menyu", reply_markup=MAIN_MENU)

        return
    elif text == "📊 Statistika":
        if update.effective_user.id != ADMIN_ID:
            return

        count = len(orders)
        total = sum(o["total"] for o in orders)

        await update.message.reply_text(
            f"📊 Buyurtmalar: {count}\n💰 Jami: {total}"
        )

    elif context.user_data.get("step") == "season":
        season = text.replace("☀️ ", "").replace("❄️ ", "").replace("🌸 ", "").replace("🍂 ", "")
        
        context.user_data["season"] = season
        context.user_data["step"] = "category"

        keyboard = get_category_buttons(context)   # 🔥 ENG MUHIM

        await update.message.reply_text(
            "Kategoriya:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    
    elif context.user_data.get("step") == "category":

        category = text.split("(")[0]
        category = category.replace("👕","").replace("👖","").replace("🧥","") \
                        .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()

        # 🔥 TO‘G‘RI NOMGA O‘TKAZAMIZ
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

        context.user_data["category"] = category
        context.user_data["step"] = "name"

        await update.message.reply_text("Nomini yozing:")
        return
    elif context.user_data.get("step") == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "size"

        keyboard = [["50-55","55-60","60-65","65-70"],["70-75","75-80","80-85","85-90"],["90-95","95-100","105-110","110-115"],["115-120","120-125","125-130"],["🔙 Orqaga", "🏠 Bosh menyu"]]
        await update.message.reply_text("O‘lcham:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return
    elif context.user_data.get("step") == "size":
        context.user_data["size"] = text.replace(" ", "")
        context.user_data["step"] = "price"

        await update.message.reply_text("Narx:")
        return
    elif context.user_data.get("step") == "price":
        context.user_data["price"] = text

        # 🔥 SAQLAYMIZ
        products.append({
            "photo": context.user_data["photo"],
            "gender": context.user_data["gender"],
            "season": context.user_data["season"],
            "category": context.user_data["category"],
            "name": context.user_data["name"],
            "size": context.user_data["size"],
            "price": context.user_data["price"],
            "count": 1,
            "reserved": 0 
        })

        save_products()

        context.user_data.clear()

        await update.message.reply_text("✅ Qo‘shildi!")
        return
    elif context.user_data.get("step") == "size_filter" and "-" in text:
        size = text.replace(" ", "")
        context.user_data["filter_size"] = size
        context.user_data["step"] = "size_season"

        keyboard = [
            ["☀️ Yozgi","❄️ Qishki"],
            ["🌸 Bahor","🍂 Kuz"],
            ["🔙 Orqaga", "🏠 Bosh menyu"]
        ]

        await update.message.reply_text(
            "Fasl tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

        # ===== USER FLOW =====
    elif text == "🛍 Kiyimlar":
        context.user_data.clear() 
        keyboard = [["👦 O‘g‘il", "👧 Qiz"],["🔙 Orqaga", "🏠 Bosh menyu"]]
        await update.message.reply_text("Tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    # 👦 / 👧
    elif text in ["👦 O‘g‘il", "👧 Qiz"]:
        gender = text.replace("👦 ", "").replace("👧 ", "")
        context.user_data["filter_gender"] = gender
        context.user_data["step"] = "choose_type"

        keyboard = [
            ["📏 Razmer bo‘yicha", "📂 Umumiy"],
            ["🔙 Orqaga", "🏠 Bosh menyu"]
        ]

        await update.message.reply_text(
            "Qanday qidirasiz?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "📏 Razmer bo‘yicha":

        context.user_data["step"] = "size_filter"

        keyboard = [
            ["50-55","55-60","60-65","65-70"],
            ["70-75","75-80","80-85","85-90"],
            ["90-95","95-100","105-110","110-115"],
            ["115-120","120-125","125-130"],
            ["🔙 Orqaga", "🏠 Bosh menyu"]
        ]

        await update.message.reply_text(
            "📏 Razmer tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    elif text == "📂 Umumiy":

        context.user_data["step"] = "user_season"

        keyboard = [
            ["☀️ Yozgi","❄️ Qishki"],
            ["🌸 Bahor","🍂 Kuz"],
            ["🔙 Orqaga", "🏠 Bosh menyu"]
        ]

        await update.message.reply_text(
            "Fasl tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "🧺 Savat":
        user_id = update.effective_user.id
        cart = carts.get(user_id, {})
        import time

        now = time.time()
        new_cart = {}

        for idx, item in cart.items():
            if now - item["time"] < 7200:
                new_cart[idx] = item
            else:
                products[int(idx)]["reserved"] -= item["qty"]

        carts[user_id] = new_cart
        cart = new_cart
        save_products()

        if not cart:
            await update.message.reply_text("🧺 Savat bo‘sh")
            return

        msg = "🧺 Savat:\n\n"
        total = 0
        keyboard = []

        for idx, item in cart.items():
            qty = item["qty"]
            p = products[idx]
            def parse_price(price_str):
                return int(
                price_str.lower()
        .replace("ming", "000")
        .replace("mong", "000")
        .replace("mimg", "000")
        .replace("so'm", "")
        .replace("ning", "000")
        .replace("mung", "000")
        .replace("mug", "000")
        .replace("mig", "000")
        .replace("min", "000")
        .replace("soʻm", "")
        .replace("som", "")
        .replace(" ", "")
    )
            price = parse_price(p["price"])
            summa = price * qty
            total += summa

            msg += f"{p['name']} x{qty} = {summa}\n"

            keyboard.append([
                InlineKeyboardButton("❌", callback_data=f"del_{idx}")
            ])

        msg += f"\n💰 Jami: {total}"

        keyboard.append([InlineKeyboardButton("🚚 Buyurtma", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])

        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    # 🌦 FASL
    elif text in ["☀️ Yozgi","❄️ Qishki","🌸 Bahor","🍂 Kuz"]:
        season = text.replace("☀️ ", "").replace("❄️ ", "").replace("🌸 ", "").replace("🍂 ", "")
        context.user_data["filter_season"] = season
        context.user_data["step"] = "user_category"

        keyboard = get_category_buttons(context)
        await update.message.reply_text(
            "Kategoriya tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # 👕 KATEGORIYA → STOP (FAqat mahsulot chiqadi)
    elif "(" in text and context.user_data.get("step") == "user_category":

        category = text.split("(")[0]
        category = category.replace("👕","").replace("👖","").replace("🧥","") \
                        .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()

        # 🔥 ADMIN BILAN MOS QILAMIZ
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
            if category in p["category"].strip().lower():
                found = True

                keyboard = [
                    [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{i}")]
                ]

                await update.message.reply_photo(
                    photo=p["photo"],
                    caption=f"{p['name']}\n{p['size']}\n{p['price']}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if not found:
            await update.message.reply_text("❌ Mahsulot yo‘q")

        return
    elif text == "🚚 Buyurtma berish":
        keyboard = [["🚚 Dastavka", "📍 Olib ketish"],["🔙 Orqaga", "🏠 Bosh menyu"]]

        await update.message.reply_text(
            "Qanday olasiz?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )   
    elif text == "🚚 Dastavka":
        context.user_data["order_step"] = "location"
        context.user_data["order_type"] = "delivery"

        keyboard = [[KeyboardButton("📍 Lokatsiya yuborish", request_location=True)],
        ["❌ Lokatsiya ishlamayapti"],
        ["🏠 Bosh menyu"]
    ]

        await update.message.reply_text(
            "📍 Lokatsiyangizni yuboring va \n⏳ Iltimos bir oz kuting... yoki lokatsiya ishlamasa pastdagi tugmani bosing:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )  

    elif context.user_data.get("order_step") == "phone":
        phone = text.strip().replace(" ", "")

        if phone.isdigit() and len(phone) == 9:
            phone = "+998" + phone
        elif phone.startswith("+998") and len(phone) == 13:
            pass
        else:
            await update.message.reply_text("❌ Noto‘g‘ri raqam!")
            return

        data = context.user_data.get("temp_order")
        if not data:
            await update.message.reply_text("❌ Xatolik")
            return

        user_id = update.effective_user.id
        order_id = str(len(orders) + 1)

        # ===== ORDER =====
        orders[order_id] = {
            "user_id": user_id,
            "cart": data["cart"],
            "location": data["location"],
            "phone": phone,
            "total": data["total"],
            "status": "new"
        }
        save_orders()

        # ===== MAHSULOTNI KAMAYTIRISH =====
        for idx, item in data["cart"].items():
            qty = item["qty"]
            products[int(idx)]["count"] -= qty
            products[int(idx)]["reserved"] -= qty

        save_products()

        # ===== USERGA MAHSULOT =====
        for idx, item in data["cart"].items():
            p = products[int(idx)]
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=user_id,
                photo=p["photo"],
                caption=f"{p['name']}\n{p['size']}\n{p['price']} x{qty}"
            )

        # ===== USER STATUS =====
        if data.get("type") == "delivery":
            await update.message.reply_text(
                "🚚 Buyurtma qabul qilindi",
                reply_markup=MAIN_MENU
            )
        else:
            await update.message.reply_text(
                "📍 Olib ketish manzili:\nSamarqand, Pastdarg‘om, Charxin\n📞 +998915388499",
                reply_markup=MAIN_MENU
            )

            await context.bot.send_location(
                chat_id=user_id,
                latitude=39.690149,
                longitude=66.824828
            )

            await update.message.reply_text(
                "🏠 Bosh menyu",
                reply_markup=MAIN_MENU
            )

        # ===== ADMIN TUGMALAR =====
        admin_keyboard = [
            [InlineKeyboardButton("📞 Aloqa", callback_data=f"contact_{order_id}")],
            [InlineKeyboardButton("🚚 Yetkazishni boshlash", callback_data=f"deliver_{order_id}")],
            [InlineKeyboardButton("✅ Yakunlandi", callback_data=f"done_{order_id}")],
            [InlineKeyboardButton("❌ Bekor", callback_data=f"cancel_{order_id}")]
        ]

        # ===== ADMINGA MAHSULOT =====
        for idx, item in data["cart"].items():
            p = products[int(idx)]
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=p["photo"],
                caption=f"{p['name']}\n{p['size']}\n{p['price']} x{qty}"
            )

        # ===== ADMINGA UMUMIY INFO =====
        if data.get("type") == "delivery":
            text_admin = f"🚚 DASTAVKA\n📞 {phone}\n💰 {data['total']}"
        else:
            text_admin = f"📍 OLIB KETISH\n📞 {phone}\n💰 {data['total']}"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text_admin,
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )

        # ===== TOZALASH =====
        carts[user_id] = {}
        context.user_data.clear()

    elif text == "📍 Olib ketish":
        context.user_data["order_step"] = "phone"

        user_id = update.effective_user.id
        cart = carts.get(user_id, {})

        if not cart:
            await update.message.reply_text("❌ Savat bo‘sh")
            return

        total = 0
        for idx, item in cart.items():
            qty = item["qty"]
            p = products[int(idx)]

            price = int(
                p["price"].lower()
                .replace("ming", "000")
                .replace("so'm", "")
                .replace("soʻm", "")
                .replace(" ", "")
            )
            total += price * qty

        context.user_data["temp_order"] = {
            "cart": cart,
            "location": None,
            "total": total,
            "type": "pickup"
        }

        keyboard = [
            [KeyboardButton("📞 Telefon yuborish", request_contact=True)],
            ["🏠 Bosh menyu"]
        ]

        await update.message.reply_text(
            "📞 Telefon raqamingizni yuboring yoki yozing:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "🏠 Bosh menyu":
        context.user_data.clear()

        await update.message.reply_text(
            "🏠 Bosh menyu",
            reply_markup=MAIN_MENU
        )
        return
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("add_"):
        idx = int(data.split("_")[1])
        product = products[idx]

        # 🔥 TEKSHIRUV
        if product["count"] - product.get("reserved", 0) <= 0:
            await query.answer("❌ Mahsulot qolmagan!", show_alert=True)
            return

        # 🔥 RESERVED OSHIRAMIZ
        product["reserved"] = product.get("reserved", 0) + 1
        save_products()

        # 🔥 SAVAT
        if user_id not in carts:
            carts[user_id] = {}

        import time

        if idx not in carts[user_id]:
            carts[user_id][idx] = {
                "qty": 1,
                "time": time.time()
            }
        else:
            carts[user_id][idx]["qty"] += 1
            carts[user_id][idx]["time"] = time.time()

        keyboard = [
            [InlineKeyboardButton("🧺 Savatga o‘tish", callback_data="go_cart")]
        ]

        await query.message.reply_text(
            "✅ Savatga qo‘shildi!\n⏳ 2 soat ichida buyurtma bermasangiz o‘chib ketadi.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "clear_yes":
        if query.from_user.id != ADMIN_ID:
            return

        products.clear()
        save_products()

        await query.message.reply_text("✅ Barcha mahsulotlar o‘chirildi")

    elif data == "clear_no":
        await query.message.reply_text("❌ Bekor qilindi")

    elif data.startswith("plus_"):
        idx = int(data.split("_")[1])
        product = products[idx]

        # 🔥 TEKSHIRUV
        if product["count"] - product.get("reserved", 0) <= 0:
            await query.answer("❌ Yetarli mahsulot yo‘q", show_alert=True)
            return

        carts[user_id][idx]["qty"] += 1
        carts[user_id][idx]["time"] = time.time()

        product["reserved"] += 1
        save_products()

        await query.answer("➕ Qo‘shildi")

    elif data.startswith("send_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        # USERGA
        await context.bot.send_message(
            chat_id=user_id,
            text="🚚 Buyurtmangiz yo‘lga chiqdi!\n⏳ 1 soat ichida yetkaziladi."
        )

        # ADMINGA
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚚 Buyurtma jo‘natildi\nID: {order_id}"
        )

        await query.answer("Yuborildi")

    elif data.startswith("confirm_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            await query.answer("Xatolik")
            return

        user_id = order["user_id"]

        # USERGA
        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtmangiz tayyor!\n🕒 Kelishilgan vaqtda olib ketishingiz mumkin."
        )

        # ADMINGA
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 BUYURTMA TASDIQLANDI\nID: {order_id}"
        )

        await query.answer("Tasdiqlandi")

    elif data.startswith("deliver_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        # USERGA
        await context.bot.send_message(
            chat_id=user_id,
            text="🚚 Buyurtmangiz yetkazilmoqda!\n⏳ 1 soat ichida yetkaziladi."
        )

        # ADMINGA
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚚 Yetkazish boshlandi\nID: {order_id}"
        )

        await query.answer("Yuborildi")

    elif data.startswith("done_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Buyurtmangizni qabul qilib oldingiz. Rahmat 😊"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ YAKUNLANDI\nID: {order_id}"
        )

        orders.pop(order_id)
        save_orders()

        await query.answer("Yakunlandi")

    elif data.startswith("ready_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtmangiz tayyor!"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 TAYYOR\nID: {order_id}"
        )

        await query.answer("Tayyor qilindi")

    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        # mahsulotni qaytaramiz
# mahsulotni qaytaramiz
        for idx, item in order["cart"].items():
            qty = item["qty"]

            products[int(idx)]["count"] += qty
            products[int(idx)]["reserved"] -= qty   # 🔥 MUHIM

        save_products()

        user_id = order["user_id"]

        # 🔥 ENG MUHIM — SAVATNI TOZALASH
        carts[user_id] = {}

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Buyurtmangiz bekor qilindi"
        )

        orders.pop(order_id)
        save_orders()

        await query.answer("Bekor qilindi")

    elif data.startswith("user_cancel_"):
        order_id = data.split("_")[2]
        order = orders.get(order_id)

        if not order:
            await query.answer("Allaqachon bekor qilingan")
            return

        # mahsulotni qaytaramiz
        for idx, item in order["cart"].items():
            qty = item["qty"]
            products[int(idx)]["count"] += qty
            products[int(idx)]["reserved"] -= qty

        save_products()

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Mijoz bekor qildi\nID: {order_id}"
        )

        await context.bot.send_message(
            chat_id=order["user_id"],
            text="❌ Buyurtma bekor qilindi"
        )

        orders.pop(order_id)
        save_orders()

        await query.answer("Bekor qilindi")        

    elif data.startswith("delivered_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        # USER ga
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📦 Buyurtma yetkazildi!\n🆔 ID: {order_id}"
        )

        # ADMIN ga ham qayta yozamiz
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 Yetkazildi\nID: {order_id}"
        )

        # STATUS
        order["status"] = "📦 Yetkazildi"
        save_orders()

        await query.answer("Yetkazildi")

    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        # USER ga
        await context.bot.send_message(
            chat_id=user_id,
            text="💰 To‘lov qabul qilindi! Rahmat 😊"
        )

        # ADMIN ga
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💰 To‘lov olindi\nID: {order_id}"
        )

        # ORDERNI YOPAMIZ
        orders.pop(order_id)
        save_orders()

        await query.answer("To‘lov olindi")

    elif data.startswith("accept_"):
        order_id = data.split("_")[1]
        order = orders.get(str(order_id))

        if not order:
            return

        user_id = order["user_id"]

        # 🔥 ADMIN MA’LUMOTI (O‘ZINGNI YOZ)
        ADMIN_PHONE = "+998915388499"
        ADDRESS = "Samarqand vil. Pastdarg'om tum. charxin shax. charos ko‘chasi 53 uy "

        LAT = 39.690149
        LON = 66.824828

        # 📞 + 🏠 USERGA YUBORISH
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Buyurtmangiz qabul qilindi! Adminlar tez orada aloqaga chiqishadi.\n\n📞 Tel: {ADMIN_PHONE}\n🏠 Manzil: {ADDRESS}"
        )

        # 📍 LOKATSIYA YUBORISH
        await context.bot.send_location(
            chat_id=user_id,
            latitude=LAT,
            longitude=LON
        )

        # ADMINGA XABAR
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ BUYURTMA QABUL QILINDI\nID: {order_id}"
        )

        await query.answer("Yuborildi")

    elif data.startswith("contact_"):
        order_id = data.split("_")[1]
        order = orders.get(str(order_id))

        if not order:
            return

        user_id = order["user_id"]

        await context.bot.send_message(
            chat_id=user_id,
            text="📞 Admin sizga 10 min ichida bog‘lanadi"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📞 Mijoz bilan 10 min ichida aloqalashing\nID: {order_id}"
        )


        await query.answer("Mijozga yuborildi")
    elif data.startswith("picked_"):
        order_id = data.split("_")[1]
        order = orders.get(str(order_id))

        if not order:
            return

        user_id = order["user_id"]

        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtma yakunlandi! Rahmat 😊"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 BUYURTMA YAKUNLANDI\nID: {order_id}"
        )

        orders.pop(str(order_id))
        save_orders()

# ===== SAVAT SYSTEMA (YANGI) =====

    elif data == "go_cart":
        user_id = query.from_user.id
        cart = carts.get(user_id, {})

        import time
        now = time.time()
        new_cart = {}

        for idx, item in cart.items():
            if now - item["time"] < 7200:
                new_cart[idx] = item
            else:
                products[int(idx)]["reserved"] -= item["qty"]

        carts[user_id] = new_cart
        cart = new_cart
        save_products()

        if not cart:
            await query.message.reply_text("🧺 Savat bo‘sh")
            return

        msg = "🧺 Savat:\n\n"
        total = 0
        keyboard = []

        for idx, item in cart.items():
            qty = item["qty"]
            p = products[int(idx)]

            price = int(
                p["price"].lower()
                .replace("ming", "000")
                .replace("so'm", "")
                .replace("soʻm", "")
                .replace(" ", "")
            )

            summa = price * qty
            total += summa

            msg += f"{p['name']} x{qty} = {summa}\n"

            keyboard.append([
                InlineKeyboardButton(f"❌ {p['name']}", callback_data=f"del_{idx}")
            ])

        msg += f"\n💰 Jami: {total}"

        keyboard.append([
            InlineKeyboardButton("🚚 Buyurtma berish", callback_data="checkout")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Orqaga", callback_data="back")
        ])

        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_"):
        idx = int(data.split("_")[1])

        user_id = query.from_user.id
        cart = carts.get(user_id, {})

        if idx in cart:
            qty = cart[idx]["qty"]
            products[idx]["reserved"] -= qty
            cart.pop(idx)

            save_products()

        await query.answer("❌ O‘chirildi")

        # 🔥 SAVATNI QAYTA CHIQARAMIZ
        if not cart:
            await query.message.reply_text("🧺 Savat bo‘sh")
            return

        msg = "🧺 Savat:\n\n"
        total = 0
        keyboard = []

        for i, item in cart.items():
            qty = item["qty"]
            p = products[int(i)]

            price = int(
                p["price"].lower()
                .replace("ming", "000")
                .replace("so'm", "")
                .replace("soʻm", "")
                .replace(" ", "")
            )

            summa = price * qty
            total += summa

            msg += f"{p['name']} x{qty} = {summa}\n"

            keyboard.append([
                InlineKeyboardButton("❌", callback_data=f"del_{i}")
            ])

        msg += f"\n💰 Jami: {total}"

        keyboard.append([InlineKeyboardButton("🚚 Buyurtma berish", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])

        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "checkout":
        context.user_data["order_step"] = "choose_type"

        keyboard = [
            ["🚚 Dastavka", "📍 Olib ketish"],
            ["🏠 Bosh menyu"]
        ]

        await query.message.reply_text(
            "Qanday olasiz?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )


    elif data == "back":
        await query.message.reply_text(
            "🏠 Bosh menyu",
            reply_markup=MAIN_MENU
            
        )
    elif data.startswith("confirm_"):
        order_id = data.split("_")[1]
        order = orders.get(order_id)

        if not order:
            return

        user_id = order["user_id"]

        # USERGA
        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtmangiz tayyor!\n🕒 Kelishilgan vaqtda olib ketishingiz mumkin."
        )

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("order_step") != "location":
        return

    location = update.message.location
    lat = location.latitude
    lon = location.longitude

    user_id = update.effective_user.id
    cart = carts.get(user_id, {})

    if not cart:
        await update.message.reply_text("❌ Savat bo‘sh")
        return

    total = 0

    for idx, item in cart.items():
        qty = item["qty"]
        p = products[int(idx)]

        price = int(
            p["price"].lower()
            .replace("ming", "000")
            .replace("so'm", "")
            .replace("soʻm", "")
            .replace(" ", "")
        )

        total += price * qty

    delivery = 0
    final = total + delivery

    # 🔥 vaqtincha Asaqlaymiz
    context.user_data["temp_order"] = {
        "cart": cart,
        "location": {"lat": lat, "lon": lon},
        "total": final,
        "type": context.user_data.get("order_type")
    }

    # 🔥 USERGA INFO
    await update.message.reply_text("⏳ Lokatsiya qabul qilindi, hisoblanmoqda...")

    # 🔥 STEP
    context.user_data["order_step"] = "phone"

    # 🔥 TELEFON TANLASH
    keyboard = [
        [KeyboardButton("📞 Telefon yuborish", request_contact=True)],
        ["🏠 Bosh menyu"]
    ]

    await update.message.reply_text(
        "📞 Telefon raqamingizni yuboring yoki yozing (+998...):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get("order_step") != "phone":
            return

        contact = update.message.contact
        phone = contact.phone_number

        if not phone.startswith("+"):
            phone = "+" + phone

        data = context.user_data.get("temp_order")
        if not data:
            await update.message.reply_text("❌ Xatolik")
            return

        user_id = update.effective_user.id
        order_id = str(len(orders) + 1)

        # ===== ORDER SAQLASH =====
        orders[order_id] = {
            "user_id": user_id,
            "cart": data["cart"],
            "location": data["location"],
            "phone": phone,
            "total": data["total"],
            "status": "new"
        }
        save_orders()

        # ===== MAHSULOTNI KAMAYTIRISH =====
        for idx, item in data["cart"].items():
            qty = item["qty"]
            products[int(idx)]["count"] -= qty
            products[int(idx)]["reserved"] -= qty

        save_products()
# ===== USERGA MAHSULOT =====
        for idx, item in data["cart"].items():
            p = products[int(idx)]
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=user_id,
                photo=p["photo"],
                caption=f"{p['name']}\n{p['size']}\n{p['price']} x{qty}"
            )

        # ===== ADMINGA MAHSULOT =====
        for idx, item in data["cart"].items():
            p = products[int(idx)]
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=p["photo"],
                caption=f"{p['name']}\n{p['size']}\n{p['price']} x{qty}"
            )

        # ===== ADMIN TUGMALAR =====
        if data.get("type") == "delivery":
            admin_keyboard = [
                [InlineKeyboardButton("📞 Aloqa", callback_data=f"contact_{order_id}")],
                [InlineKeyboardButton("🚚 Buyurtmani jo‘natish", callback_data=f"send_{order_id}")],
                [InlineKeyboardButton("✅ Yakunlandi", callback_data=f"done_{order_id}")],
                [InlineKeyboardButton("❌ Bekor", callback_data=f"cancel_{order_id}")]
            ]
        else:
            admin_keyboard = [
                [InlineKeyboardButton("📞 Aloqa", callback_data=f"contact_{order_id}")],
                [InlineKeyboardButton("📦 Buyurtmani tasdiqlash", callback_data=f"confirm_{order_id}")],
                [InlineKeyboardButton("✅ Yakunlandi", callback_data=f"done_{order_id}")],
                [InlineKeyboardButton("❌ Bekor", callback_data=f"cancel_{order_id}")]
            ]

        # ===== TEXT =====
        if data.get("type") == "delivery":

            if data.get("location") and "lat" in data["location"]:
                lat = data["location"]["lat"]
                lon = data["location"]["lon"]
                loc = f"\n📍 https://maps.google.com/?q={lat},{lon}"
            else:
                loc = "\n📍 Lokatsiya yuborilmadi"

            text_admin = (
                f"🚚 DASTAVKA\n"
                f"📞 {phone}\n"
                f"💰 {data['total']}{loc}"
            )

            # USER GA STATUS
            await update.message.reply_text(
                        "🚚 Buyurtma qabul qilindi!\n📞 Admin siz bilan tez orada bog‘lanadi.",
                        reply_markup=MAIN_MENU
            )

        else:
            text_admin = (
                f"📍 OLIB KETISH\n"
                f"📞 {phone}\n"
                f"💰 {data['total']}\n"
                f"🏠 Samarqand, Pastdarg‘om, Charxin\n"
                f"📞 +998915388499"
            )

            # USER GA MANZIL
            await update.message.reply_text(
                "📍 Olib ketish manzili:\nSamarqand, Pastdarg‘om, Charxin\n📞 +998915388499"
                
            )

            await context.bot.send_location(
                chat_id=user_id,
                latitude=39.690149,
                longitude=66.824828
            )

            await update.message.reply_text(
                "🏠 Bosh menyu",
                reply_markup=MAIN_MENU
            )

        # 🔥 ENG MUHIM — ADMIN GA HAR DOIM YUBORILADI
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text_admin,
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        # ADMINGA
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 Pickup tayyor\nID: {order_id}"
        )

        await query.answer("Tasdiqlandi")
    # ===== TOZALASH =====
        carts[user_id] = {}
        context.user_data.clear()

# Application'ni qurishda quyidagi tartibda qo'shing:

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
app.add_handler(MessageHandler(filters.LOCATION, location_handler))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle))

app.add_handler(CallbackQueryHandler(button_handler))

load_products()
load_orders()

app.run_polling()
