import json
import time
from telegram import KeyboardButton
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import asyncio
import os
import psycopg2
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)

cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    photo TEXT,
    gender TEXT,
    origin TEXT,
    season TEXT,
    category TEXT,
    name TEXT,
    size TEXT,
    price TEXT,
    count INTEGER,
    reserved INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    cart TEXT,
    location TEXT,
    phone TEXT,
    total INTEGER,
    status TEXT,
    time FLOAT
)
""")

conn.commit()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY
)
""")
conn.commit()
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

product_locks = {}
products = []
carts = {}
order_id_counter = 1
ORIGINS = [
    "🇺🇿 Vodiy",
    "🇨🇳 Xitoy",
    "🇹🇷 Turkiya",
    "🏭 8-mart fabrika"
]
def get_filter_menu(user_data):
    g = user_data.get("filter_gender")
    o = user_data.get("filter_origin")
    s = user_data.get("filter_season")

    return InlineKeyboardMarkup([

        # 👦 👧
        [
            InlineKeyboardButton(
                f"👦 O‘g‘il {'✅' if g=='o‘g‘il' else ''}",
                callback_data="g_o‘g‘il"
            ),
            InlineKeyboardButton(
                f"👧 Qiz {'✅' if g=='qiz' else ''}",
                callback_data="g_qiz"
            )
        ],

        [InlineKeyboardButton("ㅤ", callback_data="empty")],  # 🔥 GAP

        # 🇺🇿 🇨🇳
        [
            InlineKeyboardButton(
                f"🇺🇿 Vodiy {'✅' if o=='Vodiy' else ''}",
                callback_data="o_Vodiy"
            ),
            InlineKeyboardButton(
                f"🇨🇳 Xitoy {'✅' if o=='Xitoy' else ''}",
                callback_data="o_Xitoy"
            )
        ],

        # 🇹🇷 🏭
        [
            InlineKeyboardButton(
                f"🇹🇷 Turkiya {'✅' if o=='Turkiya' else ''}",
                callback_data="o_Turkiya"
            ),
            InlineKeyboardButton(
                f"🏭 8-mart {'✅' if o=='8-mart fabrika' else ''}",
                callback_data="o_8-mart fabrika"
            )
        ],

        [InlineKeyboardButton("ㅤ", callback_data="empty")],  # 🔥 GAP

        # ☀️ ❄️
        [
            InlineKeyboardButton(
                f"☀️ Yozgi {'✅' if s=='Yozgi' else ''}",
                callback_data="s_Yozgi"
            ),
            InlineKeyboardButton(
                f"❄️ Qishki {'✅' if s=='Qishki' else ''}",
                callback_data="s_Qishki"
            )
        ],

        # 🌸 🍂
        [
            InlineKeyboardButton(
                f"🌸 Bahor {'✅' if s=='Bahor' else ''}",
                callback_data="s_Bahor"
            ),
            InlineKeyboardButton(
                f"🍂 Kuz {'✅' if s=='Kuz' else ''}",
                callback_data="s_Kuz"
            )
        ],
        # ✅ 🔄
        [
            InlineKeyboardButton("✅ Tanlash", callback_data="apply"),
            InlineKeyboardButton("🔄 Tozalash", callback_data="reset")
        ]
    ])
def get_category_buttons(context):
    return [
        [f"👕 2 talik ({count_products(context,lambda p: p['category'].lower()=='2 talik kiyim')})",
         f"👕 3 talik ({count_products(context,lambda p: p['category'].lower()=='3 talik kiyim')})",
         f"👕 Futbolka ({count_products(context,lambda p: p['category'].lower()=='futbolka')})"],

         [f"👖 Shim ({count_products(context,lambda p: p['category'].lower()=='shim')})",
          f"🧥 Qalin ({count_products(context,lambda p: p['category'].lower()=='qalin kiyim')})",
         f"🩳 Shortik ({count_products(context,lambda p: p['category'].lower()=='shortik')})"],

        [f"👟 Oyoq ({count_products(context,lambda p: p['category'].lower()=='oyoq kiyim')})",
         f"🧢 Bosh ({count_products(context,lambda p: p['category'].lower()=='bosh kiyim')})",
         f"🩲 Ichki ({count_products(context,lambda p: p['category'].lower()=='ichki kiyim')})"],

        ["🔙 Orqaga", "🏠 Bosh menyu"]
    ]

def filter_check(p, context):

    # 🔥 gender
    g = context.user_data.get("filter_gender")
    if g:
        if g.lower() not in str(p.get("gender", "")).lower():
            return False

    # 🔥 origin
    o = context.user_data.get("filter_origin")
    if o:
        if o.lower() not in str(p.get("origin", "")).lower():
            return False

    # 🔥 category
    c = context.user_data.get("filter_category")
    if c:
        user_cat = str(c).strip().lower()
        prod_cat = str(p.get("category", "")).strip().lower()

        if not prod_cat:
            return False

        if user_cat not in prod_cat:   # 👈 SHUNI QO‘Y
            return False

    # 🔥 season (TOZA)
    s = context.user_data.get("filter_season")
    if s:
        season = str(s).strip().lower()

        p_seasons = p.get("season", [])

        # har doim listga aylantiramiz
        if not isinstance(p_seasons, list):
            p_seasons = str(p_seasons).split(",")

        p_seasons = [str(x).strip().lower() for x in p_seasons]

        if season not in p_seasons:
            return False

    # 🔥 size
    if context.user_data.get("filter_size"):
        size_text = context.user_data.get("filter_size")
        if str(size_text).isdigit():
            size = int(size_text)
            raw = str(p.get("size") or "").lower().replace("sm", "").strip()

            if raw == "":
                print(f"DEBUG: {p['name']} - o'lcham bo'sh")
                return False

            if "-" in raw:
                parts = raw.split("-")
                if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    s1, s2 = int(parts[0]), int(parts[1])
                    if not (s1 <= size <= s2):
                        print(f"DEBUG: {p['name']} - o'lcham diapazonga tushmadi ({s1}-{s2})")
                        return False
                else: return False
            else:
                if not raw.isdigit(): return False
                p_size = int(raw)
                if abs(p_size - size) > 1:
                    print(f"DEBUG: {p['name']} - o'lcham mos kelmadi (P:{p_size}, U:{size})")
                    return False

    # 🔥 mavjudlik (Eng ko'p xato shu yerda bo'ladi)
    available = p.get("count", 0) - p.get("reserved", 0)
    if available <= 0:
        print(f"DEBUG: {p['name']} - sotuvda qolmagan yoki hammasi rezervda")
        return False

    # Agar barcha shartlardan o'tsa
    return True 
def clean_cart(user_id, context=None):
    
    now = time.time()

    # 🔥 BUYURTMA BOSILGAN BO‘LSA — TO‘XTAT
    if context and context.user_data.get("order_started"):
        return carts.get(user_id, {})

    cart = carts.get(user_id, {})
    new_cart = {}

    for pid, item in cart.items():
        if now - item["time"] < 7200:
            new_cart[int(pid)] = item
        else:
            p = next((x for x in products if x["id"] == int(pid)), None)
            if p:
                p["reserved"] = max(0, p.get("reserved", 0) - item["qty"])

    carts[user_id] = new_cart
    return new_cart

def load_products_from_db():
    global products

    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()

    products = []

    for r in rows:
        products.append({
            "id": r[0],
            "photo": r[1],
            "gender": r[2],
            "origin": r[3],
            "season": r[4].split(",") if r[4] else [],
            "category": r[5],
            "name": r[6],
            "size": r[7],
            "price": r[8],
            "count": r[9],
            "reserved": r[10]
        })
def count_products(context, filter_func=None):
    total = 0
    for p in products:
        available = p["count"] - p.get("reserved", 0)

        if available > 0 and filter_check(p, context):
            if not filter_func or filter_func(p):
                total += available

    return total


ADMIN_MENU = ReplyKeyboardMarkup(
    [
        ["📊 Statistika", "📦 Buyurtmalar"],
        ["➕ Mahsulot qo‘shish", "📢 Reklama"],
        ["🏠 Bosh menyu"]
    ],
    resize_keyboard=True
)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🛍 Kiyimlar"],
        ["🔍 Qidirish", "🧺 Savat"],
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

async def start_photo_flow(context, chat_id, file_id):
    # 🔥 bu photo_handler ichidagi boshlanish logikasi
    context.user_data.clear()
    context.user_data["photo"] = file_id
    context.user_data["step"] = "gender"

    keyboard = [["👦 O‘g‘il", "👧 Qiz"]]
    await context.bot.send_message(
        chat_id=chat_id,
        text="Kim uchun?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    user_id = update.effective_user.id

    cur.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

    load_products_from_db()

    # 🔥 BIR MARTA JAVOB BERAMIZ
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "👑 Admin panel, Assalomu aleykum AZIZJON AHMADOVICH " ,
            reply_markup=ADMIN_MENU
        )
    else:
        await update.message.reply_text(
            "Assalomu alaykum 👋",
            reply_markup=MAIN_MENU
        )
# RASM QABUL (ADMIN)
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔥 admin yoki bot yuborgan rasmni qabul qiladi
    if update.effective_user.id != ADMIN_ID and not update.message.from_user.is_bot:
        return

    context.user_data.clear()

    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "gender"

    keyboard = [["👦 O‘g‘il", "👧 Qiz"]]
    await update.message.reply_text(
        "Kim uchun?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
# HANDLE
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message:
            return

        text = update.message.text
        # ===== ADMIN FLOW =====
        if context.user_data.get("step") == "gender":
            gender = text.replace("👦 ", "").replace("👧 ", "")
            context.user_data["gender"] = gender

            # 🔥 YANGI STEP
            context.user_data["step"] = "origin"

            keyboard = [
                ["🇺🇿 Vodiy", "🇨🇳 Xitoy"],
                ["🇹🇷 Turkiya", "🏭 8-mart fabrika"]
            ]

            await update.message.reply_text(
                "Qaysi ishlab chiqarish:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        


        elif context.user_data.get("step") == "broadcast":
            msg = text

            cur.execute("SELECT user_id FROM users")
            users = cur.fetchall()

            count = 0

            for u in users:
                try:
                    await context.bot.send_message(chat_id=u[0], text=msg)
                    count += 1
                except:
                    pass

            await update.message.reply_text(f"✅ {count} ta userga yuborildi")

            context.user_data.clear()

        elif text == "🔍 Qidirish":
            context.user_data.clear()

            await update.message.reply_text(
                "🔎 Tanlang:\n\nJins: -\nFabrika: -\nFasl: -\n\n",
                reply_markup=get_filter_menu(context.user_data)
            )

            context.user_data["step"] = "inline_all"

        elif text == "📢 Reklama":
            if update.effective_user.id != ADMIN_ID:
                return

            context.user_data["step"] = "broadcast"
            await update.message.reply_text("📢 Yuboriladigan matnni yozing:")

        elif text == "📦 Buyurtmalar":
            if update.effective_user.id != ADMIN_ID:
                return

            cur.execute("SELECT id, total, status FROM orders ORDER BY id DESC LIMIT 10")
            rows = cur.fetchall()

            if not rows:
                await update.message.reply_text("❌ Buyurtmalar yo‘q")
                return

            msg = "📦 So‘nggi buyurtmalar:\n\n"

            for r in rows:
                msg += f"🆔 {r[0]} | 💰 {r[1]} | 📌 {r[2]}\n"

            await update.message.reply_text(msg)

        elif text == "📊 Statistika":
            if update.effective_user.id != ADMIN_ID:
                return

            # 🔥 jami buyurtma
            cur.execute("SELECT COUNT(*) FROM orders")
            total_orders = cur.fetchone()[0]

            # 🔥 jami pul
            cur.execute("SELECT SUM(total) FROM orders")
            total_money = cur.fetchone()[0] or 0

            # 🔥 bugungi buyurtma
            cur.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE DATE(to_timestamp(time)) = CURRENT_DATE
            """)
            today_orders = cur.fetchone()[0]

            # 🔥 bugungi pul
            cur.execute("""
            SELECT SUM(total) FROM orders 
            WHERE DATE(to_timestamp(time)) = CURRENT_DATE
            """)
            today_money = cur.fetchone()[0] or 0

            await update.message.reply_text(
                f"📊 STATISTIKA\n\n"
                f"🧾 Jami buyurtma: {total_orders}\n"
                f"💰 Jami tushum: {total_money}\n\n"
                f"📅 Bugun:\n"
                f"📦 Buyurtma: {today_orders}\n"
                f"💵 Tushum: {today_money}"
            )

        elif context.user_data.get("step") == "origin":
            origin = text.replace("🇺🇿 ", "").replace("🇨🇳 ", "").replace("🇹🇷 ", "").replace("🏭 ", "")
            context.user_data["origin"] = origin

            context.user_data["seasons"] = []
            context.user_data["step"] = "season"

            keyboard = [["☀️ Yozgi", "❄️ Qishki"], ["🌸 Bahor", "🍂 Kuz"]]

            await update.message.reply_text(
                "Fasl tanlang:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return    

        elif text == "✅ Tayyor" and context.user_data.get("step") == "season":
            context.user_data["step"] = "category"
        
            keyboard = get_category_buttons(context)
        
            await update.message.reply_text(
                "Kategoriya:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

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
                "AgACAgIAAxkBAAIglmnX1XJ2Za6zc4Svn1wLmGhE4Q5jAAIkF2sbymy5Su63OueLl84AAQEAAwIAA3kAAzsE",
                "AgACAgIAAxkBAAIgmGnX14xdrAqXRiMfrRGlq7lTiCkBAAIuF2sbymy5SvTdKaYZnU6_AQADAgADeQADOwQ"
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

        elif text == "❌ Lokatsiya ishlamayapti":
            user_id = update.effective_user.id
            cart = carts.get(user_id, {})

            if not cart:
                await update.message.reply_text("❌ Savat bo‘sh")
                return

            total = 0
            for pid, item in cart.items():
                qty = item["qty"]
                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue

                price = int(''.join(filter(str.isdigit, p["price"])))
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
            for pid, item in cart.items():
                qty = item["qty"]
                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue

                price = int(''.join(filter(str.isdigit, p["price"])))
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
                    ["75-80","80-85","85-90"],
                    ["90-95","95-100","100-105","105-110"],
                    ["110-115","115-120","120-125","125-130"],
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
        
        elif context.user_data.get("step") == "season":
            season = text.replace("☀️ ", "").replace("❄️ ", "").replace("🌸 ", "").replace("🍂 ", "")
        
            if "seasons" not in context.user_data:
                context.user_data["seasons"] = []
        
            if season not in context.user_data["seasons"]:
                context.user_data["seasons"].append(season)
        
            keyboard = [
                ["☀️ Yozgi","❄️ Qishki"],
                ["🌸 Bahor","🍂 Kuz"],
                ["✅ Tayyor"]
            ]
        
            await update.message.reply_text(
                f"Tanlangan: {', '.join(context.user_data['seasons'])}",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        
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

            context.user_data["category"] = category.strip().lower()
            context.user_data["step"] = "name"

            await update.message.reply_text("Nomini yozing:")
            return
        elif context.user_data.get("step") == "name":
            context.user_data["name"] = text
            context.user_data["step"] = "size"

            await update.message.reply_text("📏 Uzunlik yozing (sm) (masalan 40):")
            return
        elif context.user_data.get("step") == "size":
            size = text.strip()

            if not size.isdigit():
                await update.message.reply_text("❌ Faqat raqam yozing (masalan 44)")
                return

            context.user_data["size"] = size
            context.user_data["step"] = "price"

            await update.message.reply_text("Narxni yozing:")
            
        elif context.user_data.get("step") == "price":
            price = text.replace(" ", "").replace("so'm","").replace("soʻm","")

            if not price.isdigit():
                await update.message.reply_text("❌ Faqat raqam yozing (masalan 50000)")
                return

            price = int(price)
            price = f"{price:,}".replace(",", " ")

            context.user_data["price"] = price + " so‘m"
            context.user_data["step"] = "count"

            await update.message.reply_text("📦 Nechta bor? (masalan 4):")

    
        elif context.user_data.get("step") == "count":
            if not text.isdigit():
                await update.message.reply_text("❌ Faqat raqam yozing")
                return

            context.user_data["count"] = int(text)

            # 🔥 xavfsiz olish
            photo = context.user_data.get("photo")
            gender = context.user_data.get("gender")
            origin = context.user_data.get("origin")
            seasons = context.user_data.get("seasons", [])
            category = context.user_data.get("category")
            name = context.user_data.get("name")
            size = context.user_data.get("size")
            price = context.user_data.get("price")
            count = context.user_data.get("count")

            if context.user_data.get("mode") == "edit":
                pid = context.user_data.get("edit_product_id")

                cur.execute("""
                UPDATE products
                SET photo=%s, gender=%s, origin=%s, season=%s,
                    category=%s, name=%s, size=%s, price=%s, count=%s
                WHERE id=%s
                """, (
                    photo, gender, origin,
                    ",".join(seasons),
                    category, name, size, price, count,
                    pid
                ))

                await update.message.reply_text("✅ Tahrirlandi!")
            else:
                cur.execute("""
                INSERT INTO products (photo, gender, origin, season, category, name, size, price, count, reserved)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    photo, gender, origin,
                    ",".join(seasons),
                    category, name, size, price, count,
                    0
                ))

                await update.message.reply_text("✅ Qo‘shildi!")

            conn.commit()
            load_products_from_db()
            context.user_data.clear()
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
        elif text in ["👦 O‘g‘il", "👧 Qiz"] and context.user_data.get("step") != "gender":
            gender = text.replace("👦 ", "").replace("👧 ", "")
            context.user_data["filter_gender"] = gender

            context.user_data["step"] = "origin_select"

            keyboard = [
                ["🇺🇿 Vodiy", "🇨🇳 Xitoy"],
                ["🇹🇷 Turkiya", "🏭 8-mart fabrika"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Qaysi ishlab chiqarish:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        elif text == "📏 Razmer bo‘yicha":

            context.user_data["step"] = "size_filter"

            keyboard = [
                ["75-80","80-85","85-90"],
                ["90-95","95-100","100-105","105-110"],
                ["110-115","115-120","120-125","125-130"],
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
            load_products_from_db()
            user_id = update.effective_user.id
            cart = clean_cart(user_id, context)

            
            now = time.time()
            new_cart = {}

            for pid, item in cart.items():
                if now - item["time"] < 7200:
                    new_cart[pid] = item
                else:
                    qty = item["qty"]
                    p = next((x for x in products if x["id"] == int(pid)), None)
                    if p:
                        p["reserved"] = max(0, p.get("reserved", 0) - qty)

            carts[user_id] = new_cart
            cart = new_cart

            if not cart:
                await update.message.reply_text("🧺 Savat bo‘sh")
                return

            msg = "🧺 Savat:\n\n"
            total = 0
            keyboard = []

            for pid, item in cart.items():
                qty = item["qty"]

                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue

                pprice = int(''.join(filter(str.isdigit, p["price"])))

                summa = pprice * qty
                total += summa

                msg += f"{p['name']} x{qty} = {summa}\n"

                keyboard.append([
                    InlineKeyboardButton("❌", callback_data=f"del_{pid}")
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
        
        elif context.user_data.get("step") == "origin_select":
            origin = text.replace("🇺🇿 ", "").replace("🇨🇳 ", "").replace("🇹🇷 ", "").replace("🏭 ", "")
            context.user_data["filter_origin"] = origin

            context.user_data["step"] = "choose_type"

            keyboard = [
                ["📏 Razmer bo‘yicha", "📂 Umumiy"],
                ["🔙 Orqaga", "🏠 Bosh menyu"]
            ]

            await update.message.reply_text(
                "Qanday qidirasiz?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return


        # 👕 KATEGORIYA → STOP (FAqat mahsulot chiqadi)
        elif "(" in text and context.user_data.get("step") == "user_category":

            category = text.split("(")[0]
            category = category.replace("👕","").replace("👖","").replace("🧥","") \
                            .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()

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

            context.user_data["filter_category"] = category
            # 🔥 ADMIN bo‘lsa darrov chiqaramiz
            if update.effective_user.id == ADMIN_ID:

                found = False

                for p in products:
                    if category.strip().lower() == str(p.get("category","")).strip().lower():

                        found = True

                        keyboard = [
                            [InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_{p['id']}")],
                            [InlineKeyboardButton("❌ O‘chirish", callback_data=f"delete_{p['id']}")]
                        ]

                        await update.message.reply_photo(
                            photo=p["photo"],
                            caption=f"{p['name']}\n📏 {p['size']}\n📦 {p['count']}",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )

                if not found:
                    await update.message.reply_text("❌ Mahsulot yo‘q")

                return


            # 🔥 USER bo‘lsa razmer so‘raydi
            context.user_data["filter_category"] = category
            found = False

            for p in products:
                try:
                    if filter_check(p, context):
                        found = True

                        keyboard = [
                            [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{p['id']}")]
                        ]

                        await update.message.reply_photo(
                            photo=p["photo"],
                            caption=f"{p.get('name','')}\n📏 {p.get('size','')}\n💰 {p.get('price','')}",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    print("BROKEN PRODUCT:", p, "ERROR:", e)
                    continue   # 👈 xatoni tashlab ketadi

            if not found:
                await update.message.reply_text("❌ Mahsulot yo‘q")
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
                await update.message.reply_text("❌ Mahsulot yo‘q")

            context.user_data.clear()
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
            cur.execute("""
            INSERT INTO orders (user_id, cart, location, phone, total, status, time)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """, (
                user_id,
                json.dumps(data["cart"]),
                json.dumps(data["location"]),
                phone,
                data["total"],
                "new",
                time.time()
            ))

            order_id = str(cur.fetchone()[0])
            conn.commit()

            # ===== MAHSULOTNI KAMAYTIRISH =====
            for pid, item in data["cart"].items():
                qty = item["qty"]
                p = next((x for x in products if x["id"] == int(pid)), None)
                if p:
                    p["count"] -= qty
                    p["reserved"] = max(0, p.get("reserved", 0) - qty)

            #save_products()

            # ===== USERGA MAHSULOT =====
            for pid, item in data["cart"].items():
                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue
                qty = item["qty"]

                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=p["photo"],
                    caption=f"{p['name']}\n📏 Razmer: {p['size']}\n💰 {p['price']} x{qty}"
                )

            # ===== USER STATUS =====
            if data.get("type") == "delivery":
                await update.message.reply_text(
                    "🚚 Buyurtma qabul qilindi",
                    reply_markup=MAIN_MENU
                )
            else:
                await update.message.reply_text(
                    "📍 Olib ketish manzili:\nSamarqand, Pastdarg‘om, Charxin\nA'loqa 📞 +998915388499  Adminlar o'zlari a'loqaga chiqishadi va manzilni yetgazishadi. " 
                    ,
                    reply_markup=MAIN_MENU
                )

                #await context.bot.send_location(
                #   chat_id=user_id,
                #  latitude=39.690149,
                # longitude=66.824828
                #)

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
            for pid, item in data["cart"].items():
                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue
                qty = item["qty"]

                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=p["photo"],
                    caption=f"{p['name']}\n📏 Razmer: {p['size']}\n💰 {p['price']} x{qty}"
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
            for pid, item in cart.items():
                qty = item["qty"]
                p = next((x for x in products if x["id"] == int(pid)), None)
                if not p:
                    continue

                price = int(''.join(filter(str.isdigit, p["price"])))
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

        elif context.user_data.get("step") == "inline_category" and "(" in text:

            category = text.split("(")[0]
            category = category.replace("👕","").replace("👖","").replace("🧥","") \
                .replace("🩳","").replace("👟","").replace("🧢","").replace("🩲","").strip().lower()

            # 🔥 to‘g‘ri nomga o‘tkazamiz
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

            context.user_data["filter_category"] = category
            context.user_data["step"] = "write_size"

            await update.message.reply_text(
                "📏 Mahsulot uzunligini yozing (sm)\nMasalan: 44"
            )
        elif context.user_data.get("step") == "write_size":

            size = text.strip()

            if not size.isdigit():
                await update.message.reply_text("❌ Faqat raqam yozing (44)")
                return

            context.user_data["filter_size"] = size

            found = False

            for p in products:
                if filter_check(p, context):
                    found = True

                    keyboard = [
                        [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{p['id']}")]
                    ]

                    await update.message.reply_photo(
                        photo=p["photo"],
                        caption=f"{p['name']}\n📏 Razmer: {p['size']}\n💰 {p['price']}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

            if not found:
                await update.message.reply_text("❌ Mos mahsulot topilmadi")

            context.user_data.clear()

        elif text == "🏠 Bosh menyu":
            context.user_data.clear()

            await update.message.reply_text(
                "🏠 Bosh menyu",
                reply_markup=MAIN_MENU
            )
            return

    except Exception as e:
        print("XATO:", e)
        await update.message.reply_text("❌ Xatolik yuz berdi")
        context.user_data.clear()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

# ===== FILTER BLOK =====
    if data.startswith("g_") or data.startswith("o_") or data.startswith("s_"):

        if data.startswith("g_"):
            g = data[2:]

            if "o‘g" in g or "og" in g:
                context.user_data["filter_gender"] = "o‘g‘il"
            else:
                context.user_data["filter_gender"] = "qiz"

        elif data.startswith("o_"):
            context.user_data["filter_origin"] = data[2:]

        elif data.startswith("s_"):
            context.user_data["filter_season"] = data[2:]

        # 🔥 TEXTNI YANGILAYMIZ
        await query.message.edit_text(
            f"🔎 Tanlang:\n\n"
            f"Jins: {context.user_data.get('filter_gender','-')}\n"
            f"Fabrika: {context.user_data.get('filter_origin','-')}\n"
            f"Fasl: {context.user_data.get('filter_season','-')}\n",
            reply_markup=get_filter_menu(context.user_data)
        )
        return
    # ===== RESET =====
    if data == "reset":
        context.user_data.clear()

        await query.message.edit_text(
            "🔎 Tanlang:\n\nJins: -\nFabrika: -\nFasl: -\nRazmer: -",
            reply_markup=get_filter_menu(context.user_data)
        )
        return


    # ===== APPLY =====
    if data == "apply":

        context.user_data["step"] = "inline_category"

        keyboard = get_category_buttons(context)

        await query.message.reply_text(
            "📂 Kategoriya tanlang:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    elif data.startswith("add_"):
        
        product_id = int(data.split("_")[1])

        if product_id not in product_locks:
            product_locks[product_id] = asyncio.Lock()

        async with product_locks[product_id]:

            product = next((x for x in products if x["id"] == product_id), None)
            if not product:
                await query.answer("❌ Topilmadi", show_alert=True)
                return

            # 🔥 REAL TEKSHIRUV
            available = product["count"] - product.get("reserved", 0)

            if available <= 0:
                await query.answer("❌ Bu mahsulot band yoki qolmagan", show_alert=True)
                return

            if user_id not in carts:
                carts[user_id] = {}

            if product_id in carts[user_id]:
                carts[user_id][product_id]["qty"] += 1
            else:
                carts[user_id][product_id] = {
                    "qty": 1,
                    "time": time.time()
                }

            carts[user_id][product_id]["time"] = time.time()

            # 🔥 ENG MUHIM — RESERVE
            product["reserved"] = product.get("reserved", 0) + 1

        await query.answer("✅ Savatga qo‘shildi")

        keyboard = [
            [InlineKeyboardButton("🧺 Savatga o‘tish", callback_data="go_cart")]
        ]

        await query.message.reply_text(
            "🛒 Mahsulot vaqtincha siz uchun band qilindi!\n⏳ 2 soat ichida xarid qilmasangiz o‘chiriladi.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("edit_"):
        product_id = int(data.split("_")[1])

        old_product = next((x for x in products if x["id"] == product_id), None)
        if not old_product:
            await query.message.reply_text("❌ Topilmadi")
            return

        # eski mahsulotni o‘chir
        cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
        load_products_from_db()

        # bot rasmni chiqaradi
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=old_product["photo"]
        )

        # 🔥 ENG MUHIM — bot yuborgan rasmni ham ishlatamiz
        await start_photo_flow(context, query.message.chat_id, old_product["photo"])
    elif data.startswith("delete_"):
        if query.from_user.id != ADMIN_ID:
            return

        product_id = int(data.split("_")[1])

        cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()

        load_products_from_db()

        await query.message.reply_text("✅ Mahsulot o‘chirildi")
    elif data == "clear_yes":
        if query.from_user.id != ADMIN_ID:
            return

        cur.execute("DELETE FROM products")
        conn.commit()
        load_products_from_db()
       # save_products()

        await query.message.reply_text("✅ Barcha mahsulotlar o‘chirildi")

    elif data == "clear_no":
        await query.message.reply_text("❌ Bekor qilindi")

    elif data.startswith("plus_"):
        product_id = int(data.split("_")[1])

        product = next((x for x in products if x["id"] == product_id), None)
        if not product:
            return

        if product["count"] - product.get("reserved", 0) <= 0:
            await query.answer("❌ Yetarli mahsulot yo‘q", show_alert=True)
            return

        if user_id not in carts:
            carts[user_id] = {}

        # 🔥 ENG MUHIM TUZATISH
        if product_id in carts[user_id]:
            carts[user_id][product_id]["qty"] += 1
        else:
            carts[user_id][product_id] = {
                "qty": 1,
                "time": time.time()
            }

        carts[user_id][product_id]["time"] = time.time()
        product["reserved"] += 1

        await query.answer("➕ Qo‘shildi")
    elif data.startswith("send_"):
        order_id = data.split("_")[1]
        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

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

 
    elif data.startswith("deliver_"):
        order_id = data.split("_")[1]
        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

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
        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Buyurtmangizni qabul qilib oldingiz. Rahmat 😊"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ YAKUNLANDI\nID: {order_id}"
        )

        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()
       # save_orders()

        await query.answer("Yakunlandi")

    elif data.startswith("ready_"):
        order_id = data.split("_")[1]
        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

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
        cur.execute("SELECT user_id, cart FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]
        cart = json.loads(row[1])

        # 🔥 mahsulotni qaytaramiz
        for product_id, item in cart.items():
            qty = item["qty"]

            p = next((x for x in products if x["id"] == int(product_id)), None)

            if p:
                p["count"] += qty
                p["reserved"] = max(0, p["reserved"] - qty)

        load_products_from_db()  # 🔥 ENG MUHIM

        carts[user_id] = {}

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Buyurtmangiz bekor qilindi"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ BUYURTMA BEKOR QILINDI\nID: {order_id}"
        )

        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()

        await query.answer("Bekor qilindi")
    elif data.startswith("user_cancel_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id, cart FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            await query.answer("Allaqachon bekor qilingan")
            return

        user_id = row[0]
        cart = json.loads(row[1])

        # 🔥 mahsulotni qaytaramiz
        for pid, item in cart.items():
            qty = item["qty"]
            p = next((x for x in products if x["id"] == int(pid)), None)
            if p:
                p["count"] += qty
                p["reserved"] = max(0, p.get("reserved", 0) - qty)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Mijoz bekor qildi\nID: {order_id}"
        )

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Buyurtma bekor qilindi"
        )

        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()

        await query.answer("Bekor qilindi")

    elif data.startswith("delivered_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        # USER ga
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📦 Buyurtma yetkazildi!\n🆔 ID: {order_id}"
        )

        # ADMIN ga
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 Yetkazildi\nID: {order_id}"
        )

        await query.answer("Yetkazildi")
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

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

        # ORDERNI O‘CHIRAMIZ
        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()

        await query.answer("To‘lov olindi")

    elif data.startswith("accept_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        # 🔥 ADMIN MA’LUMOTI
        ADMIN_PHONE = "+998915388499"
        ADDRESS = "Samarqand vil. Pastdarg'om tum. charxin shax. charos ko‘chasi 53 uy Adminlar aloqaga chiqishadi va olib ketish vaqtini keishiladi."

        #LAT = 39.690149
        #LON = 66.824828

        # USERGA
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Buyurtmangiz qabul qilindi!\n\n📞 Tel: {ADMIN_PHONE}\n🏠 Manzil: {ADDRESS}"
        )

        await context.bot.send_location(
            chat_id=user_id,
            latitude=LAT,
            longitude=LON
        )

        # ADMIN ga
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ BUYURTMA QABUL QILINDI\nID: {order_id}"
        )

        await query.answer("Yuborildi")
    elif data.startswith("contact_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        await context.bot.send_message(
            chat_id=user_id,
            text="📞 Admin sizga 10 min ichida bog‘lanadi"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📞 Mijoz bilan bog‘laning\nID: {order_id}"
        )

        await query.answer("Yuborildi")
    elif data.startswith("picked_"):
        order_id = data.split("_")[1]

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtma yakunlandi! Rahmat 😊"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 BUYURTMA YAKUNLANDI\nID: {order_id}"
        )

        # 🔥 ORDERNI O‘CHIRAMIZ
        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()

        await query.answer("Yakunlandi")

    elif data == "go_cart":
        user_id = query.from_user.id
        cart = carts.get(user_id, {})

        
        now = time.time()
        new_cart = {}

        # ⏳ 2 soatdan eski itemlarni tozalash
        for pid, item in cart.items():
            if now - item["time"] < 7200:
                new_cart[pid] = item
            else:
                qty = item["qty"]
                p = next((x for x in products if x["id"] == int(pid)), None)
                if p:
                    p["reserved"] = max(0, p.get("reserved", 0) - qty)

        carts[user_id] = new_cart
        cart = new_cart

        # 🧺 Savat bo‘sh bo‘lsa
        if not cart:
            await query.message.reply_text("🧺 Savat bo‘sh")
            return

        msg = "🧺 Savat:\n\n"
        total = 0
        keyboard = []

        # 📦 Savat ichidagi mahsulotlar
        for pid, item in cart.items():
            try:
                pid = int(pid)
            except:
                continue

            p = next((x for x in products if x["id"] == pid), None)
            if not p:
                continue

            qty = item["qty"]

            # 💰 narxni tozalab olish
            pprice = int(''.join(filter(str.isdigit, p["price"])))

            summa = pprice * qty
            total += summa

            msg += f"{p['name']} x{qty} = {summa}\n"

            keyboard.append([
                InlineKeyboardButton(f"❌ {p['name']}", callback_data=f"del_{pid}")
            ])

        msg += f"\n💰 Jami: {total}"

        keyboard.append([
            InlineKeyboardButton("🚚 Buyurtma berish", callback_data="checkout")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Orqaga", callback_data="back")
        ])

        await query.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("del_"):
        product_id = int(data.split("_")[1])

        cart = carts.get(user_id, {})

        if product_id in cart:
            qty = cart[product_id]["qty"]

            p = next((x for x in products if x["id"] == product_id), None)
            if p:
                p["reserved"] = max(0, p.get("reserved", 0) - qty)

            cart.pop(product_id)

        await query.answer("❌ O‘chirildi")

        if not cart:
            await query.message.reply_text("🧺 Savat bo‘sh")
            return

        msg = "🧺 Savat:\n\n"
        total = 0
        keyboard = []

        for pid, item in cart.items():
            qty = item["qty"]

            p = next((x for x in products if x["id"] == int(pid)), None)
            if not p:
                continue

            pprice = int(''.join(filter(str.isdigit, p["price"])))

            summa = pprice * qty
            total += summa

            msg += f"{p['name']} x{qty} = {summa}\n"

            keyboard.append([
                InlineKeyboardButton("❌", callback_data=f"del_{pid}")
            ])

        msg += f"\n💰 Jami: {total}"

        keyboard.append([InlineKeyboardButton("🚚 Buyurtma berish", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])

        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "checkout":

        context.user_data["order_started"] = time.time()
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

        cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        user_id = row[0]

        await context.bot.send_message(
            chat_id=user_id,
            text="📦 Buyurtmangiz tayyor! Kelishilgan vaqtda olib ketishingiz mumkin"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 BUYURTMA TASDIQLANDI\nID: {order_id}"
        )

        await query.answer("Tasdiqlandi")
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

    for pid, item in cart.items():
        qty = item["qty"]
        p = next((x for x in products if x["id"] == int(pid)), None)
        if not p:
            continue

        pprice = int(''.join(filter(str.isdigit, p["price"])))

        total += pprice * qty   # ✅ TO‘G‘RI

    delivery = 0
    final = total + delivery

    context.user_data["temp_order"] = {
        "cart": cart,
        "location": {"lat": lat, "lon": lon},
        "total": final,
        "type": context.user_data.get("order_type")
    }

    await update.message.reply_text("⏳ Lokatsiya qabul qilindi, hisoblanmoqda...")

    context.user_data["order_step"] = "phone"

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
        cur.execute("""
        INSERT INTO orders (user_id, cart, location, phone, total, status, time)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """, (
            user_id,
            json.dumps(data["cart"]),
            json.dumps(data["location"]),
            phone,
            data["total"],
            "new",
            time.time()
        ))

        order_id = str(cur.fetchone()[0])
        conn.commit()
        # ===== MAHSULOTNI KAMAYTIRISH =====
        for pid, item in data["cart"].items():
            qty = item["qty"]
            p = next((x for x in products if x["id"] == int(pid)), None)
            if p:
                p["count"] -= qty
                p["reserved"] = max(0, p.get("reserved", 0) - qty)

        #save_products()
# ===== USERGA MAHSULOT =====
        for pid, item in data["cart"].items():
            p = next((x for x in products if x["id"] == int(pid)), None)
            if not p:
                continue
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=user_id,
                photo=p["photo"],
                caption=f"{p['name']}\n📏 Razmer: {p['size']}\n💰 {p['price']} x{qty}"
            )

        # ===== ADMINGA MAHSULOT =====
        for pid, item in data["cart"].items():
            p = next((x for x in products if x["id"] == int(pid)), None)
            if not p:
                continue
            qty = item["qty"]

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=p["photo"],
                caption=f"{p['name']}\n📏 Razmer: {p['size']}\n💰 {p['price']} x{qty}"
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
                        )

            # USER GA MANZIL
            await update.message.reply_text(
                "📍 Olib ketish manzili:\nSamarqand, Pastdarg‘om, Charxin\n A'loqa 📞 +998915388499  Adminlar o'zlari a'loqaga chiqishadi va manzilni yetgazishadi. " 
                
            )

            #await context.bot.send_location(
             #   chat_id=user_id,
              #  latitude=39.690149,
               # longitude=66.824828
            #)

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

       # await query.answer("Tasdiqlandi")
    # ===== TOZALASH =====
        carts[user_id] = {}
        context.user_data.clear()

# Application'ni qurishda quyidagi tartibda qo'shing:

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))   # 🔥 1-o‘rinda
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))  # 🔥 MUHIM
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
app.add_handler(MessageHandler(filters.LOCATION, location_handler))
app.add_handler(CallbackQueryHandler(button_handler, pattern=".*"))
load_products_from_db()
app.run_polling()
