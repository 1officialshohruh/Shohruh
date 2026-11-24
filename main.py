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
from aiogram.utils.exceptions import TelegramAPIError

# ⚠️ O'Z MA'LUMOTLARINGIZNI KIRITING:
API_TOKEN = os.getenv("API_TOKEN", "9129369525:AAGOgJQINhbLyXTpozVmCzFS8HWgeuRivTw")
BOSS_ID = int(os.getenv("BOSS_ID", "2146334166"))
OPERATOR_ID = int(os.getenv("OPERATOR_ID", "2146334166"))
COURIER_ID = int(os.getenv("COURIER_ID", "2146334166"))
# Diqqat: Telegram superguruh ID odatda -100... bilan boshlanadi
WORKERS_GROUP_ID = int(os.getenv("WORKERS_GROUP_ID", "-2146334166"))

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
conn.commit()

# Agar jadval bo'sh bo'lsa, keyingi ID 1001 dan boshlanishi uchun
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
        types.InlineKeyboardButton("📞 Aloqa", callback_data="m_cont"),
    )
    return kb

class Ord(StatesGroup):
    tariff, srvs, carpet, blk_t, blk_c, korp, quilt, curt, furn, phone, loc, orientir = [State() for _ in range(12)]

class Calc(StatesGroup):
    size = State()

def esc(text) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def price_blk(raw: int, disc: int, unp: bool) -> str:
    if raw and raw > 0:
        fp = int(raw * (100 - disc) / 100)
        ex = " <i>(+ kelishiladigan xizmat)</i>" if unp else ""
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
            f"👇 Kerakli tugmani bosing:",
            reply_markup=main_kb(),
        )

@dp.callback_query_handler(lambda c: c.data == "m_home", state="*")
async def cb_home(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await c.message.edit_text(
        f"🧼 <b>Amin Cleaning — asosiy menyu</b>\n🚚 <b>Olib ketish va yetkazish — BEPUL!</b>",
        reply_markup=main_kb(),
    )
    await c.answer()

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
            "3️⃣ <b>🏘 Qo'shnilar tarifi:</b> <b>10% chegirma</b>\n"
            "4️⃣ <b>♻️ 6 oylik sovg'a:</b> <b>10% chegirma</b>"
        )
    elif d == "m_soc":
        back = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("📸 Instagram (@termiz_gilam_yuvishh)", url="https://instagram.com"),
            types.InlineKeyboardButton("💬 Telegram (@termizgilamyuvishh)", url="https://t.me"),
            types.InlineKeyboardButton("⬅️ Menyu", callback_data="m_home"),
        )
        t = "🌐 <b>Rasmiy sahifalarimizga obuna bo'ling:</b>"
    elif d == "m_cont":
        t = "📍 <b>Manzil:</b> Termiz shahri (Olib ketish va yetkazish BEPUL)\n📞 <b>Operator:</b> (88) 263 63 63\n🚚 <b>Kuryer:</b> (88) 577 63 63"
    else:
        o = cur.execute(
            "SELECT id, service, status, total_price, discount_percent, final_price FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (c.from_user.id,),
        ).fetchone()
        if o:
            oid, srv, st, raw, disc, fp = o
            t = (
                f"📦 <b>Buyurtma #{oid}</b>\n"
                f"🧼 {esc(srv)}\n"
                f"{price_blk(raw or 0, disc or 0, (fp or 0) == 0)}\n"
                f"📍 <b>Holati:</b> <b>{esc(st)}</b>"
            )
        else:
            t = "Faol buyurtma yo'q."
    await c.message.edit_text(t, reply_markup=back)
    await c.answer()

@dp.message_handler(commands=["stat"], state="*")
async def boss_stat(m: types.Message):
    if m.from_user.id != BOSS_ID:
        return
    tot, sm = cur.execute("SELECT COUNT(*), COALESCE(SUM(final_price),0) FROM orders").fetchone()
    dn = cur.execute("SELECT COUNT(*) FROM orders WHERE status='Topshirildi'").fetchone()[0]
    av, rc = cur.execute("SELECT AVG(rating), COUNT(rating) FROM orders WHERE rating>0").fetchone()
    baho_str = f"{av:.1f}/5 ({rc} ta)" if av else "Yo'q"
    await m.answer(
        f"📊 <b>STATISTIKA</b>\n"
        f"📦 Jami: {tot} ta | ✅ Topshirildi: {dn} ta\n"
        f"💰 Chegirmali tushum: {sm:,} so'm\n"
        f"⭐ O'rtacha baho: {baho_str}".replace(",", " ")
    )

@dp.callback_query_handler(lambda c: c.data == "m_furn", state="*")
async def cb_furn(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    async with state.proxy() as d:
        d["disc"], d["q"], d["lbls"], d["det"], d["raw"], d["unp"] = 5, ["furn"], ["🪑 Yumshoq mebel"], [], 0, True
    await Ord.furn.set()
    await c.message.answer("📸 <b>Mebelingiz rasmini yuboring</b> — operatorimiz narxini kelishadi:\n📞 <b>(88) 263 63 63</b>")
    await c.answer()

SRVS = [
    ("carpet", "🧶 Gilam (15 000/kv.m)"),
    ("blanket", "🛏 Adyol"),
    ("korpacha", "🛋 Ko'rpacha (50 000)"),
    ("quilt", "🛌 Ko'rpa (70 000)"),
    ("curtain", "🪟 Parda"),
    ("furn", "🪑 Yumshoq mebel"),
]

def srvs_kb(sel):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, v in SRVS:
        kb.add(types.InlineKeyboardButton(("✅ " if k in sel else "➕ ") + v, callback_data=f"s_{k}"))
    if sel:
        kb.add(types.InlineKeyboardButton("➡️ Davom etish", callback_data="s_done"))
    return kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="m_home"))

@dp.message_handler(commands=["buyurtma"], state="*")
@dp.callback_query_handler(lambda c: c.data == "m_order", state="*")
async def start_ord(ev, state: FSMContext):
    await state.finish()
    uid = ev.from_user.id
    kb = types.InlineKeyboardMarkup(row_width=1)
    if has_180(uid):
        kb.add(types.InlineKeyboardButton("🎉 6 oylik 10% chegirma", callback_data="t_10"))
    else:
        kb.add(types.InlineKeyboardButton("👤 Oddiy (5% — Kombo 2× da 10%)", callback_data="t_5"))
        kb.add(types.InlineKeyboardButton("🏘 «Qo'shnilar» tarifi (10%)", callback_data="t_10"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="m_home"))
    await Ord.tariff.set()
    if isinstance(ev, types.CallbackQuery):
        await ev.message.edit_text("🧺 <b>Tarifni tanlang:</b>", reply_markup=kb)
        await ev.answer()
    else:
        await ev.answer("🧺 <b>Tarifni tanlang:</b>", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("t_"), state=Ord.tariff)
async def pr_tar(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d:
        d["bdisc"], d["sel"] = (10 if c.data == "t_10" else 5), []
    await Ord.srvs.set()
    await c.message.edit_text("🧼 <b>Xizmatlarni tanlang (2+ xizmat = 🔥 Kombo 2× 10%):</b>", reply_markup=srvs_kb([]))
    await c.answer()

async def next_step(ev, state: FSMContext):
    msg = ev.message if isinstance(ev, types.CallbackQuery) else ev
    async with state.proxy() as d:
        q = d.get("q", [])
        if not q:
            raw, disc, unp = d.get("raw", 0), d.get("disc", 5), d.get("unp", False)
            d["fp"] = int(raw * (100 - disc) / 100) if raw > 0 else 0
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(
                types.KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)
            )
            await Ord.phone.set()
            det_txt = "\n".join(esc(x) for x in d.get("det", []))
            return await msg.answer(
                f"🧾 <b>Tafsilotlar:</b>\n{det_txt}\n\n{price_blk(raw, disc, unp)}\n\n📞 <b>Telefon raqamingizni yuboring:</b>",
                reply_markup=kb,
            )
        nxt = q.pop(0)
        d["q"] = q
    if nxt == "carpet":
        await Ord.carpet.set()
        await msg.answer("📐 Gilam o'lchamini yozing (Masalan: <code>2x5</code> yoki <code>2x5 + 3x4</code>):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "blanket":
        kb = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("🛏 1 kishilik (60 000 so'm)", callback_data="b_1"),
            types.InlineKeyboardButton("🛏 2 kishilik (Kelishiladi)", callback_data="b_2"),
        )
        await Ord.blk_t.set()
        await msg.answer("🛏 <b>Adyol turini tanlang:</b>", reply_markup=kb)
    elif nxt == "korpacha":
        await Ord.korp.set()
        await msg.answer("🛋 <b>Nechta ko'rpacha?</b> (50 000 so'm/dona):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "quilt":
        await Ord.quilt.set()
        await msg.answer("🛌 <b>Nechta ko'rpa?</b> (70 000 so'm/dona):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "curtain":
        kb = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("🪟 O'zimiz yechib-ilib beramiz (40 000/kg)", callback_data="cu_1"),
            types.InlineKeyboardButton("🧺 Oddiy yuvish (30 000/kg)", callback_data="cu_2"),
        )
        await Ord.curt.set()
        await msg.answer("🪟 <b>Parda xizmatini tanlang:</b>", reply_markup=kb)
    elif nxt == "furn":
        await Ord.furn.set()
        await msg.answer("📸 <b>Mebel rasmini yuboring</b> (Operator kelishadi):", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query_handler(lambda c: c.data.startswith("s_"), state=Ord.srvs)
async def pr_srvs(c: types.CallbackQuery, state: FSMContext):
    k = c.data.split("_")[1]
    mp = dict(SRVS)
    async with state.proxy() as d:
        sel = d.get("sel", [])
        if k == "done":
            if not sel:
                return await c.answer("Xizmat tanlang!", show_alert=True)
            komb = len(sel) >= 2
            d["disc"] = 10 if komb else d["bdisc"]
            d["komb"], d["lbls"], d["q"], d["det"], d["raw"], d["unp"] = komb, [mp[x] for x in sel], list(sel), [], 0, False
            if komb:
                await c.message.answer("🔥 <b>Kombo 2× faollashdi! (10% chegirma)</b>")
            await c.answer()
            return await next_step(c, state)
        if k in sel:
            sel.remove(k)
        else:
            sel.append(k)
        d["sel"] = sel
        await c.message.edit_text(f"🧼 <b>Tanlandi ({len(sel)} ta):</b>", reply_markup=srvs_kb(sel))
        await c.answer()

@dp.message_handler(state=Ord.carpet)
async def pr_carp(m: types.Message, state: FSMContext):
    ar, ts, fm = parse_area(m.text or "")
    if ar <= 0:
        return await m.reply("❌ Noto'g'ri o'lcham. Masalan: <code>2×5</code> deb yozing:")
    async with state.proxy() as d:
        d["carp_tot"] = round(d.get("carp_tot", 0.0) + ar, 2)
        d.setdefault("carp_fms", []).append(fm)
        tot = d["carp_tot"]
        tot_s = int(tot) if tot.is_integer() else tot
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("➕ Yana gilam qo'shish", callback_data="ord_cmore"),
        types.InlineKeyboardButton("➡️ Tayyor (Davom etish)", callback_data="ord_cdone"),
    )
    await m.answer(
        f"✅ <b>Qo'shildi:</b> {esc(fm)}\n📐 <b>Jami gilam:</b> <b>{tot_s} kv.m</b>\n\nYana gilam qo'shasizmi?",
        reply_markup=kb,
    )

@dp.callback_query_handler(lambda c: c.data in ("ord_cmore", "ord_cdone"), state=Ord.carpet)
async def cb_ord_carp(c: types.CallbackQuery, state: FSMContext):
    if c.data == "ord_cmore":
        await c.message.edit_text("📐 <b>Keyingi gilam o'lchamini yozing</b> (Masalan: <code>3×4</code>):")
        return await c.answer()
    async with state.proxy() as d:
        tot = d.get("carp_tot", 0.0)
        tot_s = int(tot) if tot.is_integer() else tot
        fm_all = " + ".join(d.get("carp_fms", []))
        p = int(tot * 15000)
        d["raw"] += p
        d["det"].append(f"🧶 Gilam: {fm_all} | {tot_s}×15 000 = {p:,} so'm".replace(",", " "))
        d["carp_tot"], d["carp_fms"] = 0.0, []
    await c.answer()
    await next_step(c, state)

@dp.callback_query_handler(lambda c: c.data.startswith("b_"), state=Ord.blk_t)
async def pr_blkt(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d:
        d["bt"] = c.data.split("_")[1]
    await Ord.blk_c.set()
    await c.message.edit_text("🛏 <b>Nechta adyol?</b> (Raqam yozing):")
    await c.answer()

@dp.message_handler(state=Ord.blk_c)
async def pr_blkc(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text or "")
    if not ns or int(ns[0]) <= 0:
        return await m.reply("❌ Sonini yozing:")
    n = int(ns[0])
    async with state.proxy() as d:
        if d.get("bt") == "1":
            p = n * 60000
            d["raw"] += p
            d["det"].append(f"🛏 Adyol (1 kishilik): {n}×60 000 = {p:,} so'm".replace(",", " "))
        else:
            d["unp"] = True
            d["det"].append(f"🛏 Adyol (2 kishilik): {n} dona (Kelishiladi)")
    await next_step(m, state)

@dp.message_handler(state=Ord.korp)
async def pr_korp(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text or "")
    if not ns or int(ns[0]) <= 0:
        return await m.reply("❌ Sonini yozing:")
    n = int(ns[0])
    p = n * 50000
    async with state.proxy() as d:
        d["raw"] += p
        d["det"].append(f"🛋 Ko'rpacha: {n}×50 000 = {p:,} so'm".replace(",", " "))
    await next_step(m, state)

@dp.message_handler(state=Ord.quilt)
async def pr_quilt(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text or "")
    if not ns or int(ns[0]) <= 0:
        return await m.reply("❌ Sonini yozing:")
    n = int(ns[0])
    p = n * 70000
    async with state.proxy() as d:
        d["raw"] += p
        d["det"].append(f"🛌 Ko'rpa: {n}×70 000 = {p:,} so'm".replace(",", " "))
    await next_step(m, state)

@dp.callback_query_handler(lambda c: c.data.startswith("cu_"), state=Ord.curt)
async def pr_curt(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d:
        d["unp"] = True
        d["det"].append(
            "🪟 Parda: ⚠️ O'zimiz YECHIB, yuvib, ILIB BERAMIZ (40 000/kg)"
            if c.data == "cu_1"
            else "🪟 Parda: Oddiy yuvish (30 000/kg)"
        )
    await c.answer()
    await next_step(c, state)

@dp.message_handler(content_types=types.ContentType.PHOTO, state=Ord.furn)
async def pr_furn(m: types.Message, state: FSMContext):
    async with state.proxy() as d:
        d["photo"] = m.photo[-1].file_id
        d["unp"] = True
        d["det"].append("🪑 Mebel: Rasmi yuborildi (Kelishiladi)")
    await next_step(m, state)

@dp.message_handler(content_types=[types.ContentType.CONTACT, types.ContentType.TEXT], state=Ord.phone)
async def pr_phone(m: types.Message, state: FSMContext):
    async with state.proxy() as d:
        d["phone"] = m.contact.phone_number if m.contact else m.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(
        types.KeyboardButton("📍 Joylashuvni yuborish (GPS)", request_location=True)
    )
    await Ord.loc.set()
    await m.answer("📍 <b>GPS lokatsiyangizni yuboring:</b>", reply_markup=kb)

@dp.message_handler(content_types=types.ContentType.LOCATION, state=Ord.loc)
async def pr_loc(m: types.Message, state: FSMContext):
    async with state.proxy() as d:
        d["lat"], d["lon"] = m.location.latitude, m.location.longitude
    await Ord.orientir.set()
    await m.answer("🏠 <b>Orientir va uy/xonadon raqamini yozing:</b>", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Ord.orientir)
async def pr_ori(m: types.Message, state: FSMContext):
    if not m.text:
        return await m.reply("Matn yozing:")
    async with state.proxy() as d:
        srv = ", ".join(d.get("lbls", [])) + (" (🔥 Kombo 2×)" if d.get("komb") else "")
        det = "\n".join(d.get("det", []))
        cur.execute(
            """INSERT INTO orders
            (user_id,full_name,phone,service,details,total_price,discount_percent,final_price,lat,lon,orientir,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                m.from_user.id,
                m.from_user.full_name,
                d.get("phone", ""),
                srv,
                det,
                d.get("raw", 0),
                d.get("disc", 5),
                d.get("fp", 0),
                d.get("lat"),
                d.get("lon"),
                m.text,
                "Operator kutilmoqda",
            ),
        )
        conn.commit()
        oid = cur.lastrowid
        pb = price_blk(d.get("raw", 0), d.get("disc", 5), d.get("unp", False))
        await m.answer(
            f"🎉 <b>Buyurtma #{oid} qabul qilindi!</b>\n\n"
            f"🧼 {esc(srv)}\n{esc(det)}\n\n{pb}\n"
            f"📍 <b>Orientir:</b> {esc(m.text)}\n\n"
            f"Hurmat bilan, <b>Amin Cleaning</b> jamoasi ✨\n"
            f"📞 Operator: (88) 263 63 63 | 🚚 Kuryer: (88) 577 63 63",
            reply_markup=main_kb(),
        )
        op_t = (
            f"🆕 <b>BUYURTMA #{oid}</b>\n"
            f"👤 {esc(m.from_user.full_name)} ({esc(d.get('phone', ''))})\n"
            f"🧼 {esc(srv)}\n{esc(det)}\n\n{pb}\n"
            f"🏠 <b>Orientir:</b> {esc(m.text)}"
        )
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✅ Tasdiqlash (Kuryerga)", callback_data=f"op_{oid}")
        )
        try:
            if d.get("photo"):
                await bot.send_photo(OPERATOR_ID, d["photo"], caption=op_t, reply_markup=kb)
            else:
                await bot.send_message(OPERATOR_ID, op_t, reply_markup=kb)
            if d.get("lat") is not None and d.get("lon") is not None:
                await bot.send_location(OPERATOR_ID, d["lat"], d["lon"])
        except TelegramAPIError as e:
            logger.error("Operatorga yuborishda xato: %s", e)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith(("op_", "cp_", "wr_", "cd_", "rt_")))
async def workflow(c: types.CallbackQuery):
    ps = c.data.split("_")
    act, oid = ps[0], int(ps[1])
    o = cur.execute(
        "SELECT user_id,full_name,phone,service,details,total_price,discount_percent,final_price,lat,lon,orientir FROM orders WHERE id=?",
        (oid,),
    ).fetchone()
    if not o:
        return await c.answer("Buyurtma topilmadi", show_alert=True)
    uid, fn, ph, srv, det, raw, disc, fp, lat, lon, ori = o
    pb = price_blk(raw or 0, disc or 0, (fp or 0) == 0)

    try:
        if act == "op":
            cur.execute("UPDATE orders SET status='Kuryerda' WHERE id=?", (oid,))
            conn.commit()
            if c.message.caption:
                await c.message.edit_caption(c.message.caption + "\n✅ Tasdiqlandi")
            else:
                await c.message.edit_text(c.message.text + "\n✅ Tasdiqlandi")
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("📦 Qabul qildim (Sexga)", callback_data=f"cp_{oid}")
            )
            await bot.send_message(
                COURIER_ID,
                f"🚚 <b>OLIB KETISH #{oid}</b>\n👤 {esc(fn)} ({esc(ph)})\n🧼 {esc(srv)}\n{esc(det)}\n\n{pb}\n🏠 {esc(ori)}",
                reply_markup=kb,
            )
            if lat is not None and lon is not None:
                await bot.send_location(COURIER_ID, lat, lon)

        elif act == "cp":
            cur.execute("UPDATE orders SET status='🧼 Buyurtmangiz yuvilmoqda' WHERE id=?", (oid,))
            conn.commit()
            await c.message.edit_text(c.message.text + "\n📦 Sexga topshirildi")
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("✨ Tayyor", callback_data=f"wr_{oid}")
            )
            await bot.send_message(
                WORKERS_GROUP_ID,
                f"🧼 <b>SEXGA KELDI #{oid}</b>\n🔹 {esc(srv)}\n{esc(det)}\n\n{pb}\n🏠 {esc(ori)}",
                reply_markup=kb,
            )

        elif act == "wr":
            cur.execute("UPDATE orders SET status='✨ Tayyor' WHERE id=?", (oid,))
            conn.commit()
            await c.message.edit_text(c.message.text + "\n✨ TAYYOR")
            await bot.send_message(
                uid,
                f"🎉 <b>Xushxabar, {esc(fn)}!</b> <b>#{oid}</b>-buyurtmangiz <b>TAYYOR BO'LDI</b>! ✨\n"
                f"🚚 Kuryer: (88) 577 63 63\nHurmat bilan, <b>Amin Cleaning</b> jamoasi ✨",
            )
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("✅ Topshirildi", callback_data=f"cd_{oid}")
            )
            await bot.send_message(
                COURIER_ID,
                f"✨ <b>TAYYOR — ELTIB BERING #{oid}</b>\n👤 {esc(fn)} ({esc(ph)})\n{pb}\n🏠 {esc(ori)}",
                reply_markup=kb,
            )
            if lat is not None and lon is not None:
                await bot.send_location(COURIER_ID, lat, lon)

        elif act == "cd":
            cur.execute(
                "UPDATE orders SET status='Topshirildi', delivered_at=? WHERE id=?",
                (datetime.now(UZ_TZ).isoformat(), oid),
            )
            conn.commit()
            await c.message.edit_text(c.message.text + "\n✅ Topshirildi")
            await bot.send_message(
                BOSS_ID,
                f"✅ <b>TOPSHIRILDI #{oid}</b>\n👤 {esc(fn)} ({esc(ph)})\n🧼 {esc(srv)}\n{esc(det)}\n\n{pb}",
            )
            rkb = types.InlineKeyboardMarkup(row_width=5).add(
                *[types.InlineKeyboardButton(f"{i}⭐", callback_data=f"rt_{oid}_{i}") for i in range(1, 6)]
            )
            await bot.send_message(
                uid,
                f"🙏 Rahmat, <b>{esc(fn)}</b>! <b>#{oid}</b>-buyurtma sifatini baholang:",
                reply_markup=rkb,
            )

        elif act == "rt":
            st = int(ps[2])
            cur.execute("UPDATE orders SET rating=? WHERE id=?", (st, oid))
            conn.commit()
            await c.message.edit_text(
                f"🎉 <b>{st} ⭐ baho uchun rahmat!</b> Hurmat bilan, <b>Amin Cleaning</b> jamoasi ✨",
                reply_markup=main_kb(),
            )
            await bot.send_message(
                BOSS_ID,
                f"{'⚠️ PAST BAHO!' if st <= 3 else '📊 DARAJA HISOBOTI'} <b>#{oid}</b>\n"
                f"👤 {esc(fn)} ({esc(ph)})\n🧼 {esc(srv)}\n{pb}\n"
                f"🌟 <b>Daraja:</b> <b>{st}/5</b> {'⭐'*st}",
            )
    except TelegramAPIError as e:
        logger.error("Workflow Telegram xatosi (%s): %s", act, e)
        await c.answer("Xabar yuborishda ID yoki guruh sozlamasini tekshiring!", show_alert=True)
        return

    await c.answer()

async def sched_11_11():
    sent = ""
    while True:
        try:
            now = datetime.now(UZ_TZ)
            td = now.strftime("%Y-%m-%d")
            if now.hour == 11 and now.minute == 11 and sent != td:
                sent = td
                rows = cur.execute(
                    "SELECT id,user_id,delivered_at FROM orders WHERE status='Topshirildi' AND delivered_at IS NOT NULL"
                ).fetchall()
                for oid, uid, ds in rows:
                    if cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND id>?", (uid, oid)).fetchone()[0] > 0:
                        continue
                    days = (now.date() - datetime.fromisoformat(ds).date()).days
                    m = None
                    if days == 180:
                        m = "Assalomu alaykum, hurmatli mijoz! Gilamlaringiz yuvilganiga 6 oy bo'ldi. <b>5 kun ichida</b> buyurtma bersangiz <b>10% chegirma</b>! Hurmat bilan, <b>Amin Cleaning</b> jamoasi ✨"
                    elif days in (181, 182, 183, 184):
                        m = f"Assalomu alaykum, hurmatli mijoz! Maxsus <b>10% chegirmangiz</b> tugashiga <b>{185-days} kun</b> qoldi! Hurmat bilan, <b>Amin Cleaning</b> jamoasi ✨"
                    elif days == 186:
                        m = "Assalomu alaykum, qadrli mijozimiz! Siz uchun <b>10% chegirmangizni yana 1 kunga uzaytirib berdik</b>! Hurmat bilan, <b>Amin Cleaning</b> jamoasi ✨"
                    if m:
                        try:
                            await bot.send_message(uid, m, reply_markup=main_kb())
                        except Exception:
                            pass
        except Exception as e:
            logger.exception("Scheduler xatosi: %s", e)
        await asyncio.sleep(25)

async def on_start(dispatcher):
    asyncio.create_task(sched_11_11())

if __name__ == "__main__":
    keep_alive()
    executor.start_polling(dp, skip_updates=True, on_startup=on_start)
