import logging
import os
import re
import sqlite3
import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import TelegramAPIError

# ⚠️ O'Z MA'LUMOTLARINGIZNI KIRITING:
API_TOKEN = os.getenv("API_TOKEN", "9129369525:AAGOgJQINhbLyXTpozVmCzFS8HWgeuRivTw")
BOSS_ID = int(os.getenv("BOSS_ID", "2146334166"))
OPERATOR_ID = int(os.getenv("OPERATOR_ID", "2146334166"))
COURIER_ID = int(os.getenv("COURIER_ID", "2146334166"))
WORKERS_GROUP_ID = int(os.getenv("WORKERS_GROUP_ID", "-1003205663486"))

UZ_TZ = timezone(timedelta(hours=5))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

conn = sqlite3.connect("amin_cleaning.db", check_same_thread=False, timeout=30.0)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("""
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
cur.execute("""
CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    full_name TEXT,
    phone TEXT,
    message TEXT,
    created_at TEXT
)
""")
conn.commit()

cur.execute("SELECT COUNT(*) FROM orders")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('orders', 1000)")
    cur.execute("UPDATE sqlite_sequence SET seq = 1000 WHERE name = 'orders' AND seq < 1000")
    conn.commit()

app = Flask("")

@app.route("/")
def home():
    return "Amin Cleaning 24/7 faol!"

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True).start()

def main_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🧺 Buyurtma berish", callback_data="m_order"))
    kb.add(
        types.InlineKeyboardButton("🧮 Narx hisoblash", callback_data="m_calc"),
        types.InlineKeyboardButton("📊 Narxlar", callback_data="m_prices"),
    )
    kb.add(
        types.InlineKeyboardButton("🪟 Parda xizmati", callback_data="m_parda"),
        types.InlineKeyboardButton("🛋 Mebel (Rasm)", callback_data="m_furn"),
    )
    kb.add(
        types.InlineKeyboardButton("📦 Buyurtmam holati", callback_data="m_stat"),
        types.InlineKeyboardButton("🎁 Chegirmalar", callback_data="m_promo"),
    )
    kb.add(
        types.InlineKeyboardButton("🌐 Instagram & TG", callback_data="m_soc"),
        types.InlineKeyboardButton("🆘 Yordam xizmati", callback_data="m_help"),
    )
    kb.add(types.InlineKeyboardButton("📞 Aloqa", callback_data="m_cont"))
    return kb

class Ord(StatesGroup):
    tariff, srvs, carpet, blk_t, blk_c, korp, quilt, curt, furn, phone, loc, orientir = [State() for _ in range(12)]

class Calc(StatesGroup):
    size = State()

class HelpState(StatesGroup):
    msg = State()

def esc(text) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def report_to_boss(title: str, detail: str, user_info: str = ""):
    text = (
        f"🚨 <b>{esc(title)}</b>\n"
        f"🕒 Vaqt: {datetime.now(UZ_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{('👤 Mijoz: ' + esc(user_info) + '\n') if user_info else ''}"
        f"📝 Tavsif:\n<code>{esc(detail[:1800])}</code>"
    )
    try:
        await bot.send_message(BOSS_ID, text)
    except Exception as e:
        logger.error("Bossga xato yuborishda muammo: %s", e)

def price_blk(raw: int, disc: int, unp: bool) -> str:
    raw = raw or 0
    disc = disc or 0
    if raw > 0:
        fp = int(raw * (100 - disc) / 100)
        ex = " <i>(+ kelishiladigan xizmat qo'shiladi)</i>" if unp else ""
        return (
            f"💰 <b>Asl narxi:</b> {raw:,} so'm\n"
            f"🎁 <b>Chegirma bilan ({disc}%):</b> <b>{fp:,} so'm</b>{ex}"
        ).replace(",", " ")
    return f"🎁 <b>Chegirma ({disc}%):</b> Operator kelishadi"

def parse_area(t: str):
    parts = t.lower().replace(",", ".").replace("*", "x").replace("х", "x").replace("×", "x").split("+")
    tot, f = 0.0, []
    for p in parts:
        ns = re.findall(r"\d+(?:\.\d+)?", p)
        if "x" in p and len(ns) >= 2:
            a, b = float(ns[0]), float(ns[1])
            ar = round(a * b, 2)
            tot += ar
            f.append(f"{int(a) if a.is_integer() else a}×{int(b) if b.is_integer() else b}={int(ar) if ar.is_integer() else ar}")
        elif ns:
            ar = float(ns[0])
            tot += ar
            f.append(f"{int(ar) if ar.is_integer() else ar} kv.m")
    tot = round(tot, 2)
    return tot, (int(tot) if tot.is_integer() else tot), " + ".join(f)

def has_180(uid: int) -> bool:
    try:
        r = cur.execute(
            "SELECT delivered_at FROM orders WHERE user_id=? AND status='Topshirildi' AND delivered_at IS NOT NULL ORDER BY id DESC LIMIT 1",
            (uid,),
        ).fetchone()
        if not r or not r[0]:
            return False
        delivered_date = datetime.fromisoformat(r[0]).date()
        days = (datetime.now(UZ_TZ).date() - delivered_date).days
        return days in (180, 181, 182, 183, 184, 186)
    except Exception as e:
        logger.exception("has_180 xatosi: %s", e)
        return False

@dp.message_handler(commands=["start"], state="*")
async def cmd_start(m: types.Message, state: FSMContext):
    await state.finish()
    if m.chat.type == "private":
        await m.answer(
            f"👋 Assalomu alaykum, hurmatli mijoz <b>{esc(m.from_user.first_name)}</b>!\n\n"
            f"🧼 <b>Amin Cleaning — tozalik xizmati</b> botiga xush kelibsiz!\n"
            f"🚚 <b>Olib ketish va yetkazish — BEPUL!</b>\n"
            f"🆘 Savol yoki murojaat uchun: <b>Yordam xizmati</b> tugmasini bosing.\n"
            f"👇 Kerakli tugmani bosing:",
            reply_markup=main_kb(),
        )

@dp.callback_query_handler(lambda c: c.data == "m_home", state="*")
async def cb_home(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await c.message.edit_text(
        "🧼 <b>Amin Cleaning — asosiy menyu</b>\n🚚 <b>Olib ketish va yetkazish — BEPUL!</b>",
        reply_markup=main_kb(),
    )
    await c.answer()

# --- MIJOZLAR UCHUN YORDAM XIZMATI ---
@dp.message_handler(commands=["yordam"], state="*")
@dp.callback_query_handler(lambda c: c.data == "m_help", state="*")
async def start_help(ev, state: FSMContext):
    await state.finish()
    await HelpState.msg.set()
    txt = (
        "🆘 <b>Mijozlar uchun yordam xizmati</b>\n\n"
        "Savolingiz, taklifingiz yoki buyurtma bo'yicha murojaatingizni yozib yuboring. "
        "Operatorimiz va rahbariyat ko'rib chiqib, siz bilan bog'lanadi.\n\n"
        "📞 Tezkor aloqa: <b>(88) 263 63 63</b>"
    )
    if isinstance(ev, types.CallbackQuery):
        await ev.message.answer(txt)
        await ev.answer()
    else:
        await ev.answer(txt)

@dp.message_handler(state=HelpState.msg)
async def save_help(m: types.Message, state: FSMContext):
    if not m.text or not m.text.strip():
        return await m.reply("Iltimos, savol yoki murojaatingizni matn ko'rinishida yozing:")
    now_str = datetime.now(UZ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    last_phone = cur.execute(
        "SELECT phone FROM orders WHERE user_id=? AND phone IS NOT NULL ORDER BY id DESC LIMIT 1",
        (m.from_user.id,),
    ).fetchone()
    ph = last_phone[0] if last_phone else "Ko'rsatilmagan"
    cur.execute(
        "INSERT INTO support_tickets (user_id, full_name, phone, message, created_at) VALUES (?,?,?,?,?)",
        (m.from_user.id, m.from_user.full_name, ph, m.text.strip(), now_str),
    )
    conn.commit()
    tid = cur.lastrowid

    ticket_text = (
        f"🆘 <b>YANGI YORDAM MUROJAATI #{tid}</b>\n"
        f"👤 Mijoz: <b>{esc(m.from_user.full_name)}</b> (ID: <code>{m.from_user.id}</code>)\n"
        f"📞 Tel: <code>{esc(ph)}</code>\n"
        f"🕒 Vaqt: {now_str}\n\n"
        f"💬 Xabar:\n{esc(m.text.strip())}"
    )
    for target_id in (OPERATOR_ID, BOSS_ID):
        try:
            await bot.send_message(target_id, ticket_text)
        except Exception as e:
            logger.error("Yordam xabarini yuborishda xato (%s): %s", target_id, e)

    await state.finish()
    await m.answer(
        f"✅ <b>Murojaatingiz #{tid} qabul qilindi!</b>\n"
        f"Tez orada operatorimiz siz bilan bog'lanadi.\n"
        f"📞 Operator: <b>(88) 263 63 63</b>",
        reply_markup=main_kb(),
    )

# --- KALKULYATOR ---
@dp.callback_query_handler(lambda c: c.data == "m_calc", state="*")
async def cb_calc(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    async with state.proxy() as d:
        d["c_tot"], d["c_fm"] = 0.0, []
    await Calc.size.set()
    await c.message.answer("🧮 <b>1-gilam o'lchamini yozing</b> (Masalan: <code>2×5</code> yoki <code>3x4</code> yoki kvadratni <code>10</code> deb yozing):")
    await c.answer()

@dp.message_handler(state=Calc.size)
async def pr_calc(m: types.Message, state: FSMContext):
    ar, ts, fm = parse_area(m.text or "")
    if ar <= 0:
        return await m.reply("❌ Noto'g'ri format. Masalan: <code>2×5</code> yoki <code>10</code> deb yozing:")
    async with state.proxy() as d:
        d["c_tot"] = round(d.get("c_tot", 0.0) + ar, 2)
        d["c_fm"].append(fm)
        tot = d["c_tot"]
        tot_s = int(tot) if tot.is_integer() else tot
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("➕ Yana gilam qo'shish", callback_data="calc_more"),
        types.InlineKeyboardButton("✅ Tayyor (Narxni hisoblash)", callback_data="calc_done"),
    )
    await m.answer(
        f"✅ <b>Qo'shildi:</b> {esc(fm)}\n📐 <b>Jami maydon:</b> <b>{tot_s} kv.m</b>\n\nYana gilam bormi yoki hisoblaymizmi?",
        reply_markup=kb,
    )

@dp.callback_query_handler(lambda c: c.data in ("calc_more", "calc_done"), state=Calc.size)
async def cb_calc_act(c: types.CallbackQuery, state: FSMContext):
    if c.data == "calc_more":
        await c.message.edit_text("📐 <b>Keyingi gilam o'lchamini yozing</b> (Masalan: <code>3×4</code>):")
        return await c.answer()
    async with state.proxy() as d:
        tot = d.get("c_tot", 0.0)
        fm_all = " + ".join(d.get("c_fm", []))
    tot_s = int(tot) if tot.is_integer() else tot
    raw = int(tot * 15000)
    await state.finish()
    await c.message.edit_text(
        (
            f"📐 <b>Jami o'lcham:</b> {esc(fm_all)} (<b>{tot_s} kv.m</b>)\n"
            f"💰 <b>Asl narxi:</b> {raw:,} so'm\n"
            f"🎁 <b>5% chegirma:</b> <b>{int(raw*0.95):,} so'm</b>\n"
            f"🔥 <b>10% (Kombo 2×/Qo'shnilar):</b> <b>{int(raw*0.9):,} so'm</b>\n\n"
            f"🚚 <b>Olib ketish va yetkazish — BEPUL!</b>"
        ).replace(",", " "),
        reply_markup=main_kb(),
    )
    await c.answer()

# --- MA'LUMOTLAR ---
@dp.message_handler(commands=["narxlar", "parda", "aksiya", "ijtimoy"], state="*")
async def cmd_infos(m: types.Message):
    cmd = m.get_command().lstrip("/")
    mp = {"narxlar": "m_prices", "parda": "m_parda", "aksiya": "m_promo", "ijtimoy": "m_soc"}
    await m.answer(
        "👇 Ma'lumotni ochish uchun bosing:",
        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📂 Ochish", callback_data=mp[cmd])),
    )

@dp.callback_query_handler(lambda c: c.data in ("m_prices", "m_parda", "m_promo", "m_soc", "m_cont", "m_stat"), state="*")
async def cb_infos(c: types.CallbackQuery):
    d = c.data
    back = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🧺 Buyurtma", callback_data="m_order"),
        types.InlineKeyboardButton("🆘 Yordam", callback_data="m_help"),
        types.InlineKeyboardButton("⬅️ Menyu", callback_data="m_home"),
    )
    if d == "m_prices":
        t = (
            "🧼 <b>Xizmatlar va Narxlar:</b>\n\n"
            "🔸 <b>Gilam:</b> 1 kv.m — 15 000 so'm\n"
            "🔸 <b>Adyol (1 kishilik):</b> 60 000 so'm\n"
            "🔸 <b>Adyol (2 kishilik):</b> Kelishiladi\n"
            "🔸 <b>Ko'rpacha:</b> 50 000 so'm\n"
            "🔸 <b>Ko'rpa:</b> 70 000 so'm\n"
            "🔸 <b>Parda (oddiy):</b> 1 kg — 30 000 so'm\n"
            "🔸 <b>Parda (yechib-ilish):</b> 1 kg — 40 000 so'm\n"
            "🔸 <b>Mebel:</b> Rasmiga qarab kelishiladi\n\n"
            "🔥 <b>Kombo 2×</b> (2+ xizmat) va <b>Qo'shnilar</b> — <b>10% chegirma!</b>"
        )
    elif d == "m_parda":
        t = (
            "🪟 <b>Parda yechib-ilib berish:</b>\n\n"
            "💰 <b>O'zimiz yechib, yuvib, ilib bersak:</b> 1 kg — <b>40 000 so'm</b>\n"
            "🧺 <b>Oddiy yuvish (o'zingiz yechsangiz):</b> 1 kg — <b>30 000 so'm</b>\n\n"
            "📞 <b>Operator:</b> (88) 263 63 63"
        )
    elif d == "m_promo":
        t = (
            "🎁 <b>Chegirmalar:</b>\n\n"
            "1️⃣ <b>Bot orqali:</b> 5% chegirma\n"
            "2️⃣ <b>🔥 Kombo 2×</b> (2+ xizmat birga): <b>10% chegirma</b>\n"
            "3️⃣ <b>🏘 Qo'shnilar tarifi:</b> <b>1
