# ================== IMPORT ==================
import json
import os
import time
from uuid import uuid4

from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

# ================== CONFIG ==================
TOKEN = "8454595686:AAFwRa3_OgE2ZCan6ePYsny8O1WlMcfMHZg"
ADMIN_IDS = [401251407]
ADMIN_USERNAME = "your_username"

PRODUCTS_FILE = "products.json"

products = []

# ================== DB ==================
def load_products():
    global products
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    else:
        products = []

def save_products():
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2)

# ================== TIMEOUT ==================
def check_timeout(context):
    t = context.user_data.get("cart_time")
    if not t:
        return

    if time.time() - t > 7200:
        cart = context.user_data.get("cart", [])

        for item in cart:
            for p in products:
                if p["id"] == item["id"]:
                    p["quantity"] += item["quantity"]

        save_products()
        context.user_data["cart"] = []
        context.user_data["cart_time"] = None

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_products()

    user_id = update.effective_user.id
    role = "admin" if user_id in ADMIN_IDS else "user"
    context.user_data["role"] = role
    context.user_data["cart"] = []

    keyboard = [["🛍 Kiyimlar"], ["📦 Savat"]]

    if role == "admin":
        keyboard.append(["➕ Qo‘shish"])

    await update.message.reply_text(
        "🏠 Bosh menyu",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================== TEXT ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_timeout(context)

    text = update.message.text
    role = context.user_data.get("role")

    # ===== ADMIN =====
    if role == "admin":
        step = context.user_data.get("admin_step")

        if text == "➕ Qo‘shish":
            context.user_data["admin_step"] = "photo"
            context.user_data["new"] = {}
            await update.message.reply_text("📸 Rasm yubor")
            return

        if step == "gender":
            context.user_data["new"]["gender"] = text
            context.user_data["admin_step"] = "name"
            await update.message.reply_text("📝 Nomi")
            return

        if step == "name":
            context.user_data["new"]["name"] = text
            context.user_data["admin_step"] = "price"
            await update.message.reply_text("💰 Narxi")
            return

        if step == "price":
            context.user_data["new"]["price"] = int(text)
            context.user_data["admin_step"] = "quantity"
            await update.message.reply_text("📦 Soni")
            return

        if step == "quantity":
            context.user_data["new"]["quantity"] = int(text)
            context.user_data["new"]["id"] = str(uuid4())

            products.append(context.user_data["new"])
            save_products()

            context.user_data["admin_step"] = None
            await update.message.reply_text("✅ Qo‘shildi")
            return

    # ===== USER =====
    else:
        if text == "🛍 Kiyimlar":
            for p in products:
                keyboard = [
                    [InlineKeyboardButton("🛒 Qo‘shish", callback_data=f"add_{p['id']}")]
                ]

                await update.message.reply_photo(
                    p["photo"],
                    caption=f"{p['name']}\n💰 {p['price']}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if text == "📦 Savat":
            await show_cart(update, context)

# ================== PHOTO ==================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("role") != "admin":
        return

    if context.user_data.get("admin_step") != "photo":
        return

    photo = update.message.photo[-1].file_id
    context.user_data["new"]["photo"] = photo
    context.user_data["admin_step"] = "gender"

    await update.message.reply_text("👦 yoki 👧")

# ================== CART ==================
async def show_cart(update, context):
    cart = context.user_data.get("cart", [])

    if not cart:
        await update.message.reply_text("❌ Bo‘sh")
        return

    for item in cart:
        keyboard = [
            [
                InlineKeyboardButton("➕", callback_data=f"plus_{item['id']}"),
                InlineKeyboardButton("➖", callback_data=f"minus_{item['id']}"),
                InlineKeyboardButton("❌", callback_data=f"del_{item['id']}")
            ]
        ]

        await update.message.reply_text(
            f"{item['name']} x {item['quantity']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
def load_products_from_db():
    global products

    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    else:
        products = []
# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    load_products_from_db()

    check_timeout(context)

    data = query.data
    cart = context.user_data.get("cart", [])

    # ===== ADD =====
    if data.startswith("add_"):
        load_products_from_db()   # yoki load_products()

        pid = data.split("_")[1]

        product = next((x for x in products if x["id"] == pid), None)
        if not product:
            await query.answer("❌ Topilmadi", show_alert=True)
            return

        if product["quantity"] <= 0:
            await query.answer("❌ Tugagan", show_alert=True)
            return

        product["quantity"] -= 1
        save_products()

        found = False
        for item in cart:
            if item["id"] == pid:
                item["quantity"] += 1
                found = True

        if not found:
            cart.append({
                "id": pid,
                "name": product["name"],
                "quantity": 1
            })

        context.user_data["cart"] = cart
        context.user_data["cart_time"] = time.time()

        await query.answer("✅ Qo‘shildi")
        await query.message.reply_text("✅ Savatga qo‘shildi")
    # ===== PLUS =====
    if data.startswith("plus_"):
        pid = data.split("_")[1]

        for p in products:
            if p["id"] == pid and p["quantity"] > 0:
                p["quantity"] -= 1

                for item in cart:
                    if item["id"] == pid:
                        item["quantity"] += 1

        save_products()
        await query.message.reply_text("➕")

    # ===== MINUS =====
    if data.startswith("minus_"):
        pid = data.split("_")[1]

        for item in cart:
            if item["id"] == pid:
                item["quantity"] -= 1

                for p in products:
                    if p["id"] == pid:
                        p["quantity"] += 1

                if item["quantity"] <= 0:
                    cart.remove(item)

        save_products()
        await query.message.reply_text("➖")

    # ===== DELETE =====
    if data.startswith("del_"):
        pid = data.split("_")[1]

        for item in cart:
            if item["id"] == pid:
                for p in products:
                    if p["id"] == pid:
                        p["quantity"] += item["quantity"]

                cart.remove(item)

        save_products()
        await query.message.reply_text("❌ O‘chirildi")

# ================== MAIN ==================
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, text_handler))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(CallbackQueryHandler(callback))

app.run_polling()
