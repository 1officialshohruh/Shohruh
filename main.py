import logging
import os
import re
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ==========================================================
# ⚠️ SHU 5 TA QATORGA O'Z MA'LUMOTLARINGIZNI YOZING:
# ==========================================================
API_TOKEN = '9129369525:AAGOgJQINhbLyXTpozVmCzFS8HWgeuRivTw'
BOSS_ID = 2146334166
OPERATOR_ID = 2146334166
COURIER_ID = 2146334166
WORKERS_GROUP_ID = -2146334166
# ==========================================================

UZ_TZ = timezone(timedelta(hours=5))
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="Markdown")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect("amin_cleaning.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    full_name TEXT,
    phone TEXT,
    service TEXT,
    details TEXT,
    total_price INTEGER,
    discount_percent INTEGER,
    final_price INTEGER,
    lat REAL,
    lon REAL,
    orientir TEXT,
    status TEXT,
    delivered_at TEXT,
    rating INTEGER DEFAULT 0
)
""")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM orders")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('orders', 1000)")
    conn.commit()

app = Flask('')

@app.route('/')
def home():
    return "Amin Cleaning boti 24/7 uzluksiz faol ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

def inline_main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🧺 Buyurtma berish", callback_data="menu_order"))
    kb.add(
        types.InlineKeyboardButton("🧮 Narx hisoblash", callback_data="menu_calc"),
        types.InlineKeyboardButton("📊 Narxlar va xizmatlar", callback_data="menu_prices")
    )
    kb.add(
        types.InlineKeyboardButton("🪟 Parda xizmati", callback_data="menu_parda"),
        types.InlineKeyboardButton("🛋 Mebel (Rasm yuborish)", callback_data="menu_furniture")
    )
    kb.add(
        types.InlineKeyboardButton("📦 Buyurtmam holati", callback_data="menu_status"),
        types.InlineKeyboardButton("🎁 Chegirmalar (Kombo 2×)", callback_data="menu_promo")
    )
    kb.add(
        types.InlineKeyboardButton("🌐 Instagram & Telegram", callback_data="menu_socials"),
        types.InlineKeyboardButton("📞 Aloqa va Manzil", callback_data="menu_contact")
    )
    return kb

class OrderState(StatesGroup):
    tariff = State()
    services_select = State()
    carpet_size = State()
    blanket_type = State()
    blanket_count = State()
    quilt_count = State()
    korpacha_count = State()
    curtain_type = State()
    furniture_photo = State()
    phone = State()
    location = State()
    orientir = State()

class CalcState(StatesGroup):
    size = State()

def format_price_block(raw_total: int, discount: int, has_unpriced: bool) -> str:
    if raw_total > 0:
        final_price = int(raw_total * (100 - discount) / 100)
        raw_str = f"{raw_total:,}".replace(",", " ")
        final_str = f"{final_price:,}".replace(",", " ")
        extra = " _(+ kelishiladigan xizmat)_" if has_unpriced else ""
        return (
            f"💰 *Asl narxi:* {raw_str} so'm\n"
            f"🎁 *Chegirma bilan ({discount}%):* *{final_str} so'm*{extra}"
        )
    return f"🎁 *Chegirma ({discount}%):* Operator rasm/miqdorga qarab kelishadi"

def parse_carpet_details(text: str):
    clean = text.lower().replace(",", ".").replace("*", "x").replace("х", "x")
    parts = clean.split("+")
    total_area = 0.0
    formulas = []
    for part in parts:
        part = part.strip()
        if "x" in part:
            nums = re.findall(r"\d+(?:\.\d+)?", part)
            if len(nums) >= 2:
                a, b = float(nums[0]), float(nums[1])
                area = round(a * b, 2)
                total_area += area
                a_s = int(a) if a.is_integer() else a
                b_s = int(b) if b.is_integer() else b
                ar_s = int(area) if area.is_integer() else area
                formulas.append(f"{a_s}×{b_s}={ar_s}")
        else:
            nums = re.findall(r"\d+(?:\.\d+)?", part)
            if nums:
                area = float(nums[0])
                total_area += area
                ar_s = int(area) if area.is_integer() else area
                formulas.append(f"{ar_s} kv.m")
    total_area = round(total_area, 2)
    tot_s = int(total_area) if total_area.is_integer() else total_area
    return total_area, tot_s, " + ".join(formulas)

def check_180_promo(user_id: int) -> bool:
    cursor.execute("SELECT delivered_at FROM orders WHERE user_id=? AND status='Topshirildi' ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        delivered_date = datetime.fromisoformat(row[0])
        days = (datetime.now(UZ_TZ).date() - delivered_date.date()).days
        if days in (180, 181, 182, 183, 184, 186):
            return True
    return False

@dp.message_handler(commands=['start'], state="*")
async def send_welcome(message: types.Message, state: FSMContext):
    await state.finish()
    if message.chat.type == 'private':
        welcome_text = (
            f"👋 Assalomu alaykum, hurmatli mijoz *{message.from_user.first_name}*!\n\n"
            "🧼 *Amin Cleaning — tozalik xizmati* botiga xush kelibsiz!\n"
            "Biz Termiz shahri bo'ylab gilam, adyol, ko'rpa-ko'rpacha, parda va yumshoq mebellarni professional yuvib beramiz.\n\n"
            "🚚 *Olib ketish va yetkazib berish — BEPUL!*\n"
            "👇 Kerakli xizmat tugmasini bosing:"
        )
        await message.answer(welcome_text, reply_markup=inline_main_menu())

@dp.callback_query_handler(lambda c: c.data == "menu_home", state="*")
async def back_to_home(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    welcome_text = (
        "🧼 *Amin Cleaning — Asosiy menyu*\n\n"
        "🚚 *Termiz shahri bo'ylab olib ketish va yetkazish — BEPUL!*\n"
        "👇 Kerakli bo'limni tanlang:"
    )
    await call.message.edit_text(welcome_text, reply_markup=inline_main_menu())
    await call.answer()

def get_prices_text():
    return (
        "🧼 *Amin Cleaning — Xizmatlar va Narxlar:*\n\n"
        "🔸 *Gilam yuvish:* 1 kv.m — 15 000 so'm\n"
        "🔸 *Adyol (1 kishilik):* 1 dona — 60 000 so'm\n"
        "🔸 *Adyol (2 kishilik):* Operatorimiz bilan kelishiladi\n"
        "🔸 *Ko'rpacha yuvish:* 1 dona — 50 000 so'm\n"
        "🔸 *Ko'rpa yuvish:* 1 dona — 70 000 so'm\n"
        "🔸 *Parda yuvish (oddiy):* 1 kg — 30 000 so'm\n"
        "🔸 *Parda (yechib + yuvib + ilib berish):* 1 kg — 40 000 so'm\n"
        "🔸 *Yumshoq mebel yuvish:* Mebel rasmiga qarab operatorimiz bilan kelishiladi\n\n"
        "🎁 *CHEGIRMALAR:*\n"
        "✅ Bot orqali 1 ta xizmatga — *5% chegirma!*\n"
        "🔥 *Kombo 2×* (2 ta va undan ko'p xizmat birga: Gilam + Adyol, Gilam + Parda, Ko'rpa + Mebel va h.k.) — *10% chegirma!*\n"
        "🏘 *Qo'shningiz bilan birga* buyurtma bersangiz — *10% chegirma!*\n\n"
        "📞 *Operator:* (88) 263 63 63\n"
        "🚚 *Kuryer:* (88) 577 63 63"
    )

@dp.message_handler(commands=['narxlar'], state="*")
async def cmd_prices(message: types.Message):
    await message.answer(get_prices_text(), reply_markup=inline_main_menu())

@dp.callback_query_handler(lambda c: c.data == "menu_prices", state="*")
async def send_prices_cb(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🧺 Buyurtma berish", callback_data="menu_order"),
        types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="menu_home")
    )
    await call.message.edit_text(get_prices_text(), reply_markup=kb)
    await call.answer()

def get_parda_text():
    return (
        "🪟 *Parda yechib-ilib berish xizmati:*\n\n"
        "Uyingizdan chiqib, parda yechishga va uni qayta ilishga vaqt sarflamang! "
        "Xodimlarimiz uyingizga borib, pardalarni *o'zlari ehtiyotkorlik bilan yechib olishadi* va yuvib bo'lingach, *yana o'zlari ilib berishadi*! 😎\n\n"
        "💰 *O'zimiz yechib, yuvib, ilib bersak:* 1 kg — *40 000 so'm*\n"
        "🧺 *Oddiy yuvish (o'zingiz yechib bersangiz):* 1 kg — *30 000 so'm*\n\n"
        "📞 *Operator:* (88) 263 63 63\n"
        "🚚 *Kuryer:* (88) 577 63 63"
    )

@dp.message_handler(commands=['parda'], state="*")
async def cmd_parda(message: types.Message):
    await message.answer(get_parda_text(), reply_markup=inline_main_menu())

@dp.callback_query_handler(lambda c: c.data == "menu_parda", state="*")
async def send_parda_cb(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🧺 Buyurtma berish", callback_data="menu_order"),
        types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="menu_home")
    )
    await call.message.edit_text(get_parda_text(), reply_markup=kb)
    await call.answer()

def get_promo_text():
    return (
        "🎁 *Amin Cleaning — Chegirmalar va Aksiyalar:*\n\n"
        "1️⃣ *Bot mijozi chegirmasi (5%):* Bot orqali berilgan har bir buyurtmaga avtomatik 5% chegirma!\n"
        "2️⃣ *🔥 Kombo 2× aksiyasi (10%):* Bir vaqtning o'zida 2 ta yoki undan ko'p xizmatdan foydalansangiz (masalan: Gilam + Adyol, Gilam + Parda, Ko'rpacha + Gilam) — *10% chegirma*!\n"
        "3️⃣ *🏘 «Qo'shnilar» tarifi (10%):* Qo'shningiz bilan birga buyurtma bersangiz, ikkalangizga ham *10% chegirma*!\n"
