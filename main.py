import logging
import os
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ⚠️ 1. @BotFather dan olgan YANGI tokeningizni qo'shtirnoq ichiga yozing
API_TOKEN = '9099509925:AAGPJRkvzUyI272DmQRbu-3MxeYV4q6-zfs'

# ⚠️ 2. O'zingizning Telegram ID raqamingizni yozing (Masalan: ADMIN_ID = 123456789)
ADMIN_ID = None

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==========================================================
# BOTNI 24/7 UYG'OQ TUTIB TURUVCHI VEB-SERVER QISMI
# ==========================================================
app = Flask('')

@app.route('/')
def home():
    return "Amin Gilam Yuvish boti 24/7 faol ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
# ==========================================================

class OrderState(StatesGroup):
    name = State()
    phone = State()
    address = State()

@dp.message_handler(commands=['start'], state="*")
async def send_welcome(message: types.Message, state: FSMContext):
    await state.finish()
    if message.chat.type == 'private':
        welcome_text = (
            f"👋 Assalomu alaykum, hurmatli mijoz {message.from_user.first_name}!\n\n"
            "🧼 *Amin Gilam Yuvish* professional xizmati botiga xush kelibsiz!\n"
            "Siz bu yerda xizmatlarimiz bilan tanishishingiz va buyurtma berishingiz mumkin.\n\n"
            "📌 *Menyu buyruqlari:*\n"
            "📦 /buyurtma — Onlayn buyurtma berish\n"
            "📊 /narxlar — Narxlar va xizmatlar\n"
            "🧺 /parda — Parda yechib-ilib berish xizmati\n"
            "🎁 /aksiya — Chegirmalar va aksiyalar\n"
            "🌐 /ijtimoy — Guruhimiz va Instagram"
        )
        await message.reply(welcome_text, parse_mode="Markdown")

@dp.message_handler(commands=['buyurtma'], state="*")
async def start_order(message: types.Message):
    await OrderState.name.set()
    await message.reply(
        "📦 *Onlayn buyurtma berishni boshlaymiz.*\n\n"
        "Iltimos, ismingizni kiriting:",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message_handler(state=OrderState.name)
async def process_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("Iltimos, ismingizni matn ko'rinishida yozing:")
        return

    async with state.proxy() as data:
        data['name'] = message.text
    await OrderState.next()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = types.KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)
    keyboard.add(button)

    await message.reply(
        "Rahmat! Endi pastdagi tugmani bosish orqali yoki qo'lda *telefon raqamingizni* yuboring:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(content_types=types.ContentType.CONTACT, state=OrderState.phone)
async def process_phone_contact(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phone'] = message.contact.phone_number
    await OrderState.next()
    await message.reply(
        "Ajoyib! Oxirgi bosqich: *Manzilingizni* yozib qoldiring (Masalan: Termiz sh., Navoiy ko'chasi, 12-uy):",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

@dp.message_handler(state=OrderState.phone)
async def process_phone_text(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("Iltimos, telefon raqamingizni yozing yoki pastdagi tugmani bosing:")
        return

    async with state.proxy() as data:
        data['phone'] = message.text
    await OrderState.next()
    await message.reply(
        "Ajoyib! Oxirgi bosqich: *Manzilingizni* yozib qoldiring (Masalan: Termiz sh., Navoiy ko'chasi, 12-uy):",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

@dp.message_handler(state=OrderState.address)
async def process_address(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("Iltimos, manzilingizni matn ko'rinishida yozib qoldiring:")
        return

    async with state.proxy() as data:
        data['address'] = message.text

        client_text = (
            "🎉 *Buyurtmangiz muvaffaqiyatli qabul qilindi!*\n\n"
            "Tez orada operatorimiz siz bilan bog'lanadi. Rahmat!\n\n"
            "📞 *Tezkor aloqa:* (88) 263 63 63"
        )
        await message.reply(client_text, parse_mode="Markdown")

        admin_text = (
            "🔔 *YANGI BUYURTMA KELDI!*\n\n"
            f"👤 *Mijoz:* {data['name']}\n"
            f"📞 *Telefon:* {data['phone']}\n"
            f"📍 *Manzil:* {data['address']}\n"
            f"🆔 *Telegram Username:* @{message.from_user.username if message.from_user.username else 'Mavjud emas'}"
        )

        if ADMIN_ID is not None:
            try:
                await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Adminga xabar yuborishda xatolik: {e}")
        else:
            logging.warning("ADMIN_ID kiritilmagan! Buyurtma hech kimga yuborilmadi.")

    await state.finish()

@dp.message_handler(commands=['narxlar'], state="*")
@dp.message_handler(lambda message: message.text and any(word in message.text.lower() for word in ['narx', 'narxi', 'qancha', 'necha pul', 'narxlar', 'adyol', 'ko\'rpa', 'mebel']), state="*")
async def send_prices(message: types.Message):
    price_text = (
        "🧼 *Amin Gilam Yuvish Xizmati Narxlari:*\n\n"
        "🔸 *Gilam yuvish:* 1 kv.m — 15 000 so'm\n"
        "🔸 *Adyol yuvish:* 1 dona — 60 000 so'm\n"
        "🔸 *Ko'rpacha yuvish:* 1 dona — 50 000 so'm\n"
        "🔸 *Ko'rpa yuvish:* 1 dona — 70 000 so'm\n"
        "🔸 *Parda yuvish (oddiy):* 1 kg — 30 000 so'm\n"
        "🔸 *Mebel yuvish:* 1 kishilik — 90 000 so'm\n\n"
        "📞 *Buyurtma uchun:* (88) 263 63 63 | (88) 577 63 63"
    )
    await message.reply(price_text, parse_mode="Markdown")

@dp.message_handler(commands=['parda'], state="*")
async def send_parda_info(message: types.Message):
    parda_text = (
        "🧺 *Parda yechib-ilib berish xizmati:*\n\n"
        "Uyingizdan chiqib, parda yechishga va uni qayta ilishga vaqt sarflamang! "
        "Xodimlarimiz uyingizga borib, pardalarni *o'zlari ehtiyotkorlik bilan yechib olishadi* va yuvib bo'lingach, *yana o'zlari ilib berishadi*! 😎\n\n"
        "💰 *Xizmat narxi:* 1 kg parda uchun — 40 000 so'm (Yuvish + Yechish + Ilib berish ichida)\n\n"
        "📞 *Bog'lanish:* (88) 263 63 63 | (88) 577 63 63"
    )
    await message.reply(parda_text, parse_mode="Markdown")

@dp.message_handler(commands=['aksiya'], state="*")
async def send_promo(message: types.Message):
    promo_text = (
        "🎁 *Chegirmalar va Aksiyalar:*\n\n"
        "Hozircha faol aksiyalarimiz mavjud emas. Yaqin kunlarda siz uchun ajoyib va foydali aksiyalar e'lon qilamiz! 🔥\n\n"
        "📢 Yangi aksiyalar va chegirmalar boshlanganda guruhimizda va ijtimoiy tarmoqlarimizda albatta xabar beramiz. Bizni kuzatishda davom eting!\n\n"
        "📞 *Ma'lumot uchun:* (88) 263 63 63 | (88) 577 63 63"
    )
    await message.reply(promo_text, parse_mode="Markdown")

@dp.message_handler(commands=['ijtimoy'], state="*")
async def send_socials(message: types.Message):
    social_text = (
        "🌐 *Bizning ijtimoiy tarmoqlarimiz:*\n\n"
        "💬 Telegram Guruhimiz: [Qo'shilish](https://t.me)\n"
        "📸 Instagram Profilimiz: [Kuzatish](https://instagram.com)"
    )
    await message.reply(social_text, parse_mode="Markdown", disable_web_page_preview=True)

# Har qanday xatolik yuz berganda bot o'chib qolmasligi uchun
@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Xatolik yuz berdi: {exception}")
    return True

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
