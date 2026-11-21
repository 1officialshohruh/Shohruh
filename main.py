import logging, os, re, sqlite3, asyncio
from datetime import datetime, timedelta, timezone
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ⚠️ SHU 5 TA QATORGA O'Z MA'LUMOTLARINGIZNI YOZING:
API_TOKEN = '9129369525:AAGOgJQINhbLyXTpozVmCzFS8HWgeuRivTw'
BOSS_ID = 2146334166
OPERATOR_ID = 2146334166
COURIER_ID = 2146334166
WORKERS_GROUP_ID = -2146334166

UZ_TZ = timezone(timedelta(hours=5))
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="Markdown")
dp = Dispatcher(bot, storage=MemoryStorage())

conn = sqlite3.connect("amin_cleaning.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, full_name TEXT, phone TEXT,
    service TEXT, details TEXT, total_price INTEGER, discount_percent INTEGER,
    final_price INTEGER, lat REAL, lon REAL, orientir TEXT, status TEXT,
    delivered_at TEXT, rating INTEGER DEFAULT 0)""")
conn.commit()
if cur.execute("SELECT COUNT(*) FROM orders").fetchone() == 0:
    cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('orders', 1000)")
    conn.commit()

app = Flask('')
@app.route('/')
def home(): return "Amin Cleaning 24/7 faol!"
def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()

def main_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🧺 Buyurtma berish", callback_data="m_order"))
    kb.add(types.InlineKeyboardButton("🧮 Narx hisoblash", callback_data="m_calc"), types.InlineKeyboardButton("📊 Narxlar", callback_data="m_prices"))
    kb.add(types.InlineKeyboardButton("🪟 Parda xizmati", callback_data="m_parda"), types.InlineKeyboardButton("🛋 Mebel (Rasm)", callback_data="m_furn"))
    kb.add(types.InlineKeyboardButton("📦 Buyurtmam holati", callback_data="m_stat"), types.InlineKeyboardButton("🎁 Chegirmalar", callback_data="m_promo"))
    kb.add(types.InlineKeyboardButton("🌐 Instagram & TG", callback_data="m_soc"), types.InlineKeyboardButton("📞 Aloqa", callback_data="m_cont"))
    return kb

class Ord(StatesGroup):
    tariff, srvs, carpet, blk_t, blk_c, korp, quilt, curt, furn, phone, loc, orientir = [State() for _ in range(12)]
class Calc(StatesGroup):
    size = State()

def price_blk(raw: int, disc: int, unp: bool) -> str:
    if raw > 0:
        fp = int(raw * (100 - disc) / 100)
        ex = " _(+ kelishiladigan xizmat)_" if unp else ""
        return f"💰 *Asl narxi:* {raw:,} so'm\n🎁 *Chegirma bilan ({disc}%):* *{fp:,} so'm*{ex}".replace(",", " ")
    return f"🎁 *Chegirma ({disc}%):* Operator kelishadi"

def parse_area(t: str):
    parts = t.lower().replace(",", ".").replace("*", "x").replace("х", "x").replace("×", "x").split("+")
    tot, f = 0.0, []
    for p in parts:
        ns = re.findall(r"\d+(?:\.\d+)?", p)
        if "x" in p and len(ns) >= 2:
            a, b = float(ns[0]), float(ns[1])
            ar = round(a * b, 2); tot += ar
            f.append(f"{int(a) if a.is_integer() else a}×{int(b) if b.is_integer() else b}={int(ar) if ar.is_integer() else ar}")
        elif ns:
            ar = float(ns[0]); tot += ar
            f.append(f"{int(ar) if ar.is_integer() else ar} kv.m")
    tot = round(tot, 2)
    return tot, (int(tot) if tot.is_integer() else tot), " + ".join(f)

def has_180(uid: int) -> bool:
    r = cur.execute("SELECT delivered_at FROM orders WHERE user_id=? AND status='Topshirildi' ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    return bool(r and r and (datetime.now(UZ_TZ).date() - datetime.fromisoformat(r).date()).days in (180,181,182,183,184,186))

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(m: types.Message, state: FSMContext):
    await state.finish()
    if m.chat.type == 'private':
        await m.answer(f"👋 Assalomu alaykum, hurmatli mijoz *{m.from_user.first_name}*!\n\n🧼 *Amin Cleaning — tozalik xizmati* botiga xush kelibsiz!\n🚚 *Olib ketish va yetkazish — BEPUL!*\n👇 Kerakli tugmani bosing:", reply_markup=main_kb())

@dp.callback_query_handler(lambda c: c.data == "m_calc", state="*")
async def cb_calc(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    async with state.proxy() as d: d['c_tot'], d['c_fm'] = 0.0, []
    await Calc.size.set()
    await c.message.answer("🧮 *1-gilam o'lchamini yozing* (Masalan: `2×5` yoki `3x4` yoki kvadratni `10` deb yozing):")
    await c.answer()

@dp.message_handler(state=Calc.size)
async def pr_calc(m: types.Message, state: FSMContext):
    ar, ts, fm = parse_area(m.text)
    if ar <= 0: return await m.reply("❌ Noto'g'ri format. Masalan: `2×5` yoki `10` deb yozing:")
    async with state.proxy() as d:
        d['c_tot'] = round(d.get('c_tot', 0.0) + ar, 2)
        d['c_fm'].append(fm)
        tot = d['c_tot']
        tot_s = int(tot) if tot.is_integer() else tot
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("➕ Yana gilam qo'shish", callback_data="calc_more"),
        types.InlineKeyboardButton("✅ Tayyor (Narxni hisoblash)", callback_data="calc_done")
    )
    await m.answer(f"✅ *Qo'shildi:* {fm}\n📐 *Jami maydon:* *{tot_s} kv.m*\n\nYana gilam bormi yoki hisoblaymizmi?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ("calc_more", "calc_done"), state=Calc.size)
async def cb_calc_act(c: types.CallbackQuery, state: FSMContext):
    if c.data == "calc_more":
        await c.message.edit_text("📐 *Keyingi gilam o'lchamini yozing* (Masalan: `3×4`):")
        return await c.answer()
    async with state.proxy() as d:
        tot = d.get('c_tot', 0.0)
        fm_all = " + ".join(d.get('c_fm', []))
    tot_s = int(tot) if tot.is_integer() else tot
    raw = int(tot * 15000)
    await state.finish()
    await c.message.edit_text(
        f"📐 *Jami o'lcham:* {fm_all} (*{tot_s} kv.m*)\n"
        f"💰 *Asl narxi:* {raw:,} so'm\n"
        f"🎁 *5% chegirma:* *{int(raw*0.95):,} so'm*\n"
        f"🔥 *10% (Kombo 2×/Qo'shnilar):* *{int(raw*0.9):,} so'm*\n\n"
        f"🚚 *Olib ketish va yetkazish — BEPUL!*".replace(",", " "),
        reply_markup=main_kb()
    )
    await c.answer()

@dp.message_handler(commands=['narxlar', 'parda', 'aksiya', 'ijtimoy'], state="*")
async def cmd_infos(m: types.Message):
    cmd = m.get_command().lstrip("/")
    mp = {"narxlar": "m_prices", "parda": "m_parda", "aksiya": "m_promo", "ijtimoy": "m_soc"}
    await m.answer("👇 Ma'lumotni ochish uchun bosing:", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📂 Ochish", callback_data=mp[cmd])))

@dp.callback_query_handler(lambda c: c.data in ("m_prices","m_parda","m_promo","m_soc","m_cont","m_stat"), state="*")
async def cb_infos(c: types.CallbackQuery):
    d = c.data
    back = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🧺 Buyurtma", callback_data="m_order"), types.InlineKeyboardButton("⬅️ Menyu", callback_data="m_home"))
    if d == "m_prices":
        t = "🧼 *Xizmatlar va Narxlar:*\n\n🔸 *Gilam:* 1 kv.m — 15 000 so'm\n🔸 *Adyol (1 kishilik):* 60 000 so'm\n🔸 *Adyol (2 kishilik):* Kelishiladi\n🔸 *Ko'rpacha:* 50 000 so'm\n🔸 *Ko'rpa:* 70 000 so'm\n🔸 *Parda (oddiy):* 1 kg — 30 000 so'm\n🔸 *Parda (yechib-ilish):* 1 kg — 40 000 so'm\n🔸 *Mebel:* Rasmiga qarab kelishiladi\n\n🔥 *Kombo 2×* (2+ xizmat) va *Qo'shnilar* — *10% chegirma!*"
    elif d == "m_parda":
        t = "🪟 *Parda yechib-ilib berish:*\n\n💰 *O'zimiz yechib, yuvib, ilib bersak:* 1 kg — *40 000 so'm*\n🧺 *Oddiy yuvish (o'zingiz yechsangiz):* 1 kg — *30 000 so'm*\n\n📞 *Operator:* (88) 263 63 63"
    elif d == "m_promo":
        t = "🎁 *Chegirmalar:*\n\n1️⃣ *Bot orqali:* 5% chegirma\n2️⃣ *🔥 Kombo 2×* (2+ xizmat birga): *10% chegirma*\n3️⃣ *🏘 Qo'shnilar tarifi:* *10% chegirma*\n4️⃣ *♻️ 6 oylik sovg'a:* *10% chegirma*"
    elif d == "m_soc":
        back = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("📸 Instagram (@termiz_gilam_yuvishh)", url="https://instagram.com"),
            types.InlineKeyboardButton("💬 Telegram (@termizgilamyuvishh)", url="https://t.me"),
            types.InlineKeyboardButton("⬅️ Menyu", callback_data="m_home"))
        t = "🌐 *Rasmiy sahifalarimizga obuna bo'ling:*"
    elif d == "m_cont":
        t = "📍 *Manzil:* Termiz shahri (Olib ketish va yetkazish BEPUL)\n📞 *Operator:* (88) 263 63 63\n🚚 *Kuryer:* (88) 577 63 63"
    else:
        o = cur.execute("SELECT id, service, status, total_price, discount_percent, final_price FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1", (c.from_user.id,)).fetchone()
        t = f"📦 *Buyurtma #{o}*\n🧼 {o}\n{price_blk(o, o, o==0)}\n📍 *Holati:* *{o}*" if o else "Faol buyurtma yo'q."
    await c.message.edit_text(t, reply_markup=back); await c.answer()

@dp.message_handler(commands=['stat'], state="*")
async def boss_stat(m: types.Message):
    if m.from_user.id != BOSS_ID: return
    tot, sm = cur.execute("SELECT COUNT(*), COALESCE(SUM(final_price),0) FROM orders").fetchone()
    dn = cur.execute("SELECT COUNT(*) FROM orders WHERE status='Topshirildi'").fetchone()
    av, rc = cur.execute("SELECT AVG(rating), COUNT(rating) FROM orders WHERE rating>0").fetchone()
    await m.answer(f"📊 *STATISTIKA*\n📦 Jami: {tot} ta | ✅ Topshirildi: {dn} ta\n💰 Chegirmali tushum: {sm:,} so'm\n⭐ O'rtacha baho: {f'{av:.1f}/5 ({rc} ta)' if av else 'Yoq'}".replace(",", " "))

@dp.callback_query_handler(lambda c: c.data == "m_furn", state="*")
async def cb_furn(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    async with state.proxy() as d:
        d['disc'], d['q'], d['lbls'], d['det'], d['raw'], d['unp'] = 5, ["furn"], ["🪑 Yumshoq mebel"], [], 0, True
    await Ord.furn.set(); await c.message.answer("📸 *Mebelingiz rasmini yuboring* — operatorimiz narxini kelishadi:\n📞 *(88) 263 63 63*"); await c.answer()

SRVS = [("carpet","🧶 Gilam (15 000/kv.m)"),("blanket","🛏 Adyol"),("korpacha","🛋 Ko'rpacha (50 000)"),("quilt","🛌 Ko'rpa (70 000)"),("curtain","🪟 Parda"),("furn","🪑 Yumshoq mebel")]
def srvs_kb(sel):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, v in SRVS: kb.add(types.InlineKeyboardButton(("✅ " if k in sel else "➕ ") + v, callback_data=f"s_{k}"))
    if sel: kb.add(types.InlineKeyboardButton("➡️ Davom etish", callback_data="s_done"))
    return kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="m_home"))

@dp.message_handler(commands=['buyurtma'], state="*")
@dp.callback_query_handler(lambda c: c.data == "m_order", state="*")
async def start_ord(ev, state: FSMContext):
    await state.finish()
    uid = ev.from_user.id
    kb = types.InlineKeyboardMarkup(row_width=1)
    if has_180(uid): kb.add(types.InlineKeyboardButton("🎉 6 oylik 10% chegirma", callback_data="t_10"))
    else:
        kb.add(types.InlineKeyboardButton("👤 Oddiy (5% — Kombo 2× da 10%)", callback_data="t_5"))
        kb.add(types.InlineKeyboardButton("🏘 «Qo'shnilar» tarifi (10%)", callback_data="t_10"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="m_home"))
    await Ord.tariff.set()
    if isinstance(ev, types.CallbackQuery): await ev.message.edit_text("🧺 *Tarifni tanlang:*", reply_markup=kb); await ev.answer()
    else: await ev.answer("🧺 *Tarifni tanlang:*", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("t_"), state=Ord.tariff)
async def pr_tar(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d: d['bdisc'], d['sel'] = (10 if c.data=="t_10" else 5), []
    await Ord.srvs.set(); await c.message.edit_text("🧼 *Xizmatlarni tanlang (2+ xizmat = 🔥 Kombo 2× 10%):*", reply_markup=srvs_kb([])); await c.answer()

async def next_step(ev, state: FSMContext):
    msg = ev.message if isinstance(ev, types.CallbackQuery) else ev
    async with state.proxy() as d:
        q = d.get('q', [])
        if not q:
            raw, disc, unp = d.get('raw', 0), d.get('disc', 5), d.get('unp', False)
            d['fp'] = int(raw * (100 - disc) / 100) if raw > 0 else 0
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(types.KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
            await Ord.phone.set()
            return await msg.answer(f"🧾 *Tafsilotlar:*\n" + "\n".join(d['det']) + f"\n\n{price_blk(raw, disc, unp)}\n\n📞 *Telefon raqamingizni yuboring:*", reply_markup=kb)
        nxt = q.pop(0); d['q'] = q
    if nxt == "carpet": await Ord.carpet.set(); await msg.answer("📐 Gilam o'lchamini yozing (Masalan: `2x5` yoki `2x5 + 3x4`):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "blanket":
        kb = types.InlineKeyboardMarkup(row_width=1).add(types.InlineKeyboardButton("🛏 1 kishilik (60 000 so'm)", callback_data="b_1"), types.InlineKeyboardButton("🛏 2 kishilik (Kelishiladi)", callback_data="b_2"))
        await Ord.blk_t.set(); await msg.answer("🛏 *Adyol turini tanlang:*", reply_markup=kb)
    elif nxt == "korpacha": await Ord.korp.set(); await msg.answer("🛋 *Nechta ko'rpacha?* (50 000 so'm/dona):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "quilt": await Ord.quilt.set(); await msg.answer("🛌 *Nechta ko'rpa?* (70 000 so'm/dona):", reply_markup=types.ReplyKeyboardRemove())
    elif nxt == "curtain":
        kb = types.InlineKeyboardMarkup(row_width=1).add(types.InlineKeyboardButton("🪟 O'zimiz yechib-ilib beramiz (40 000/kg)", callback_data="cu_1"), types.InlineKeyboardButton("🧺 Oddiy yuvish (30 000/kg)", callback_data="cu_2"))
        await Ord.curt.set(); await msg.answer("🪟 *Parda xizmatini tanlang:*", reply_markup=kb)
    elif nxt == "furn": await Ord.furn.set(); await msg.answer("📸 *Mebel rasmini yuboring* (Operator kelishadi):", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query_handler(lambda c: c.data.startswith("s_"), state=Ord.srvs)
async def pr_srvs(c: types.CallbackQuery, state: FSMContext):
    k = c.data.split("_")[1]
    mp = dict(SRVS)
    async with state.proxy() as d:
        sel = d.get('sel', [])
        if k == "done":
            if not sel: return await c.answer("Xizmat tanlang!", show_alert=True)
            komb = len(sel) >= 2
            d['disc'] = 10 if komb else d['bdisc']
            d['komb'], d['lbls'], d['q'], d['det'], d['raw'], d['unp'] = komb, [mp[x] for x in sel], list(sel), [], 0, False
            if komb: await c.message.answer("🔥 *Kombo 2× faollashdi! (10% chegirma)*")
            await c.answer(); return await next_step(c, state)
        if k in sel: sel.remove(k)
        else: sel.append(k)
        d['sel'] = sel
        await c.message.edit_text(f"🧼 *Tanlandi ({len(sel)} ta):*", reply_markup=srvs_kb(sel)); await c.answer()

@dp.message_handler(state=Ord.carpet)
async def pr_carp(m: types.Message, state: FSMContext):
    ar, ts, fm = parse_area(m.text)
    if ar <= 0: return await m.reply("❌ Noto'g'ri o'lcham. Masalan: `2×5` deb yozing:")
    async with state.proxy() as d:
        d['carp_tot'] = round(d.get('carp_tot', 0.0) + ar, 2)
        d.setdefault('carp_fms', []).append(fm)
        tot = d['carp_tot']
        tot_s = int(tot) if tot.is_integer() else tot
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("➕ Yana gilam qo'shish", callback_data="ord_cmore"),
        types.InlineKeyboardButton("➡️ Tayyor (Davom etish)", callback_data="ord_cdone")
    )
    await m.answer(f"✅ *Qo'shildi:* {fm}\n📐 *Jami gilam:* *{tot_s} kv.m*\n\nYana gilam qo'shasizmi?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ("ord_cmore", "ord_cdone"), state=Ord.carpet)
async def cb_ord_carp(c: types.CallbackQuery, state: FSMContext):
    if c.data == "ord_cmore":
        await c.message.edit_text("📐 *Keyingi gilam o'lchamini yozing* (Masalan: `3×4`):")
        return await c.answer()
    async with state.proxy() as d:
        tot = d.get('carp_tot', 0.0)
        tot_s = int(tot) if tot.is_integer() else tot
        fm_all = " + ".join(d.get('carp_fms', []))
        p = int(tot * 15000)
        d['raw'] += p
        d['det'].append(f"🧶 Gilam: {fm_all} | {tot_s}×15 000 = {p:,} so'm".replace(",", " "))
        d['carp_tot'], d['carp_fms'] = 0.0, []
    await c.answer()
    await next_step(c, state)

@dp.callback_query_handler(lambda c: c.data.startswith("b_"), state=Ord.blk_t)
async def pr_blkt(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d: d['bt'] = c.data.split("_")[1]
    await Ord.blk_c.set(); await c.message.edit_text("🛏 *Nechta adyol?* (Raqam yozing):"); await c.answer()

@dp.message_handler(state=Ord.blk_c)
async def pr_blkc(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text)
    if not ns or int(ns[0]) <= 0: return await m.reply("❌ Sonini yozing:")
    n = int(ns[0])
    async with state.proxy() as d:
        if d.get('bt') == "1":
            p = n * 60000; d['raw'] += p; d['det'].append(f"🛏 Adyol (1 kishilik): {n}×60 000 = {p:,} so'm".replace(",", " "))
        else: d['unp'] = True; d['det'].append(f"🛏 Adyol (2 kishilik): {n} dona (Kelishiladi)")
    await next_step(m, state)

@dp.message_handler(state=Ord.korp)
async def pr_korp(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text)
    if not ns or int(ns[0]) <= 0: return await m.reply("❌ Sonini yozing:")
    n = int(ns[0]); p = n * 50000
    async with state.proxy() as d: d['raw'] += p; d['det'].append(f"🛋 Ko'rpacha: {n}×50 000 = {p:,} so'm".replace(",", " "))
    await next_step(m, state)

@dp.message_handler(state=Ord.quilt)
async def pr_quilt(m: types.Message, state: FSMContext):
    ns = re.findall(r"\d+", m.text)
    if not ns or int(ns[0]) <= 0: return await m.reply("❌ Sonini yozing:")
    n = int(ns[0]); p = n * 70000
    async with state.proxy() as d: d['raw'] += p; d['det'].append(f"🛌 Ko'rpa: {n}×70 000 = {p:,} so'm".replace(",", " "))
    await next_step(m, state)

@dp.callback_query_handler(lambda c: c.data.startswith("cu_"), state=Ord.curt)
async def pr_curt(c: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as d:
        d['unp'] = True
        d['det'].append("🪟 Parda: ⚠️ O'zimiz YECHIB, yuvib, ILIB BERAMIZ (40 000/kg)" if c.data=="cu_1" else "🪟 Parda: Oddiy yuvish (30 000/kg)")
    await c.answer(); await next_step(c, state)

@dp.message_handler(content_types=types.ContentType.PHOTO, state=Ord.furn)
async def pr_furn(m: types.Message, state: FSMContext):
    async with state.proxy() as d: d['photo'] = m.photo[-1].file_id; d['unp'] = True; d['det'].append("🪑 Mebel: Rasmi yuborildi (Kelishiladi)")
    await next_step(m, state)

@dp.message_handler(content_types=[types.ContentType.CONTACT, types.ContentType.TEXT], state=Ord.phone)
async def pr_phone(m: types.Message, state: FSMContext):
    async with state.proxy() as d: d['phone'] = m.contact.phone_number if m.contact else m.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(types.KeyboardButton("📍 Joylashuvni yuborish (GPS)", request_location=True))
    await Ord.loc.set(); await m.answer("📍 *GPS lokatsiyangizni yuboring:*", reply_markup=kb)

@dp.message_handler(content_types=types.ContentType.LOCATION, state=Ord.loc)
async def pr_loc(m: types.Message, state: FSMContext):
    async with state.proxy() as d: d['lat'], d['lon'] = m.location.latitude, m.location.longitude
    await Ord.orientir.set(); await m.answer("🏠 *Orientir va uy/xonadon raqamini yozing:*", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Ord.orientir)
async def pr_ori(m: types.Message, state: FSMContext):
    if not m.text: return await m.reply("Matn yozing:")
    async with state.proxy() as d:
        srv = ", ".join(d['lbls']) + (" (🔥 Kombo 2×)" if d.get('komb') else "")
        det = "\n".join(d['det'])
        cur.execute("INSERT INTO orders (user_id,full_name,phone,service,details,total_price,discount_percent,final_price,lat,lon,orientir,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (m.from_user.id, m.from_user.full_name, d['phone'], srv, det, d['raw'], d['disc'], d['fp'], d['lat'], d['lon'], m.text, "Operator kutilmoqda"))
        conn.commit(); oid = cur.lastrowid
        pb = price_blk(d['raw'], d['disc'], d['unp'])
        await m.answer(f"🎉 *Buyurtma #{oid} qabul qilindi!*\n\n🧼 {srv}\n{det}\n\n{pb}\n📍 *Orientir:* {m.text}\n\nHurmat bilan, *Amin Cleaning* jamoasi ✨\n📞 Operator: (88) 263 63 63 | 🚚 Kuryer: (88) 577 63 63", reply_markup=main_kb())
        op_t = f"🆕 *BUYURTMA #{oid}*\n👤 {m.from_user.full_name} ({d['phone']})\n🧼 {srv}\n{det}\n\n{pb}\n🏠 *Orientir:* {m.text}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Tasdiqlash (Kuryerga)", callback_data=f"op_{oid}"))
        if d.get('photo'): await bot.send_photo(OPERATOR_ID, d['photo'], caption=op_t, reply_markup=kb)
        else: await bot.send_message(OPERATOR_ID, op_t, reply_markup=kb)
        await bot.send_location(OPERATOR_ID, d['lat'], d['lon'])
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith(("op_","cp_","wr_","cd_","rt_")))
async def workflow(c: types.CallbackQuery):
    ps = c.data.split("_"); act, oid = ps[0], int(ps[1])
    o = cur.execute("SELECT user_id,full_name,phone,service,details,total_price,discount_percent,final_price,lat,lon,orientir FROM orders WHERE id=?", (oid,)).fetchone()
    if not o: return
    uid, fn, ph, srv, det, raw, disc, fp, lat, lon, ori = o
    pb = price_blk(raw, disc, fp == 0)
    if act == "op":
        cur.execute("UPDATE orders SET status='Kuryerda' WHERE id=?", (oid,)); conn.commit()
        await (c.message.edit_caption(c.message.caption+"\n✅ Tasdiqlandi") if c.message.caption else c.message.edit_text(c.message.text+"\n✅ Tasdiqlandi"))
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📦 Qabul qildim (Sexga)", callback_data=f"cp_{oid}"))
        await bot.send_message(COURIER_ID, f"🚚 *OLIB KETISH #{oid}*\n👤 {fn} ({ph})\n🧼 {srv}\n{det}\n\n{pb}\n🏠 {ori}", reply_markup=kb)
        await bot.send_location(COURIER_ID, lat, lon)
    elif act == "cp":
        cur.execute("UPDATE orders SET status='🧼 Buyurtmangiz yuvilmoqda' WHERE id=?", (oid,)); conn.commit()
        await c.message.edit_text(c.message.text+"\n📦 Sexga topshirildi")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✨ Tayyor", callback_data=f"wr_{oid}"))
        await bot.send_message(WORKERS_GROUP_ID, f"🧼 *SEXGA KELDI #{oid}*\n🔹 {srv}\n{det}\n\n{pb}\n🏠 {ori}", reply_markup=kb)
    elif act == "wr":
        cur.execute("UPDATE orders SET status='✨ Tayyor' WHERE id=?", (oid,)); conn.commit()
        await c.message.edit_text(c.message.text+"\n✨ TAYYOR")
        await bot.send_message(uid, f"🎉 *Xushxabar, {fn}!* *#{oid}*-buyurtmangiz *TAYYOR BO'LDI*! ✨\n🚚 Kuryer: (88) 577 63 63\nHurmat bilan, *Amin Cleaning* jamoasi ✨")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Topshirildi", callback_data=f"cd_{oid}"))
        await bot.send_message(COURIER_ID, f"✨ *TAYYOR — ELTIB BERING #{oid}*\n👤 {fn} ({ph})\n{pb}\n🏠 {ori}", reply_markup=kb)
        await bot.send_location(COURIER_ID, lat, lon)
    elif act == "cd":
        cur.execute("UPDATE orders SET status='Topshirildi', delivered_at=? WHERE id=?", (datetime.now(UZ_TZ).isoformat(), oid)); conn.commit()
        await c.message.edit_text(c.message.text+"\n✅ Topshirildi")
        await bot.send_message(BOSS_ID, f"✅ *TOPSHIRILDI #{oid}*\n👤 {fn} ({ph})\n🧼 {srv}\n{det}\n\n{pb}")
        rkb = types.InlineKeyboardMarkup(row_width=5).add(*[types.InlineKeyboardButton(f"{i}⭐", callback_data=f"rt_{oid}_{i}") for i in range(1,6)])
        await bot.send_message(uid, f"🙏 Rahmat, *{fn}*! *#{oid}*-buyurtma sifatini baholang:", reply_markup=rkb)
    elif act == "rt":
        st = int(ps[2]); cur.execute("UPDATE orders SET rating=? WHERE id=?", (st, oid)); conn.commit()
        await c.message.edit_text(f"🎉 *{st} ⭐ baho uchun rahmat!* Hurmat bilan, *Amin Cleaning* jamoasi ✨", reply_markup=main_kb())
        await bot.send_message(BOSS_ID, f"{'⚠️ PAST BAHO!' if st<=3 else '📊 DARAJA HISOBOTI'} *#{oid}*\n👤 {fn} ({ph})\n🧼 {srv}\n{pb}\n🌟 *Daraja:* *{st}/5* {'⭐'*st}")
    await c.answer()

async def sched_11_11():
    sent = ""
    while True:
        now = datetime.now(UZ_TZ); td = now.strftime("%Y-%m-%d")
        if now.hour == 11 and now.minute == 11 and sent != td:
            sent = td
            for oid, uid, ds in cur.execute("SELECT id,user_id,delivered_at FROM orders WHERE status='Topshirildi' AND delivered_at IS NOT NULL").fetchall():
                if cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND id>?", (uid, oid)).fetchone()[0] > 0: continue
                days = (now.date() - datetime.fromisoformat(ds).date()).days
                m = None
                if days == 180: m = "Assalomu alaykum, hurmatli mijoz! Gilamlaringiz yuvilganiga 6 oy bo'ldi. *5 kun ichida* buyurtma bersangiz *10% chegirma*! Hurmat bilan, *Amin Cleaning* jamoasi ✨"
                elif days in (181,182,183,184): m = f"Assalomu alaykum, hurmatli mijoz! Maxsus *10% chegirmangiz* tugashiga *{185-days} kun* qoldi! Hurmat bilan, *Amin Cleaning* jamoasi ✨"
                elif days == 186: m = "Assalomu alaykum, qadrli mijozimiz! Siz uchun *10% chegirmangizni yana 1 kunga uzaytirib berdik*! Hurmat bilan, *Amin Cleaning* jamoasi ✨"
                if m:
                    try: await bot.send_message(uid, m, reply_markup=main_kb())
                    except: pass
        await asyncio.sleep(25)

async def on_start(dp): asyncio.create_task(sched_11_11())
if __name__ == '__main__':
    keep_alive(); executor.start_polling(dp, skip_updates=True, on_startup=on_start)
