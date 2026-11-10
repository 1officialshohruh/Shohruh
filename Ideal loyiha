import logging
from aiogram import Bot, Dispatcher, executor, types

# ⚠️ BotFather'dan olgan tokeningizni shu yerga qo'ying
API_TOKEN = 'BOT_TOKENINGIZNI_SHU_YERGA_YOZING'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 1. /start buyrug'i (Shaxsiy chatda xushmuomala kutib olish)
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type == 'private':
        welcome_text = (
            f"👋 Assalomu alaykum, hurmatli mijoz {message.from_user.first_name}!\n\n"
            "🧼 *Amin Gilam Yuvish* professional xizmati botiga xush kelibsiz!\n"
            "Siz bu yerda xizmatlarimiz bilan tanishishingiz va buyurtma berishingiz mumkin.\n\n"
            "📌 *Menyu buyruqlari:*\n"
            "📦 /buyurtma — Tezkor buyurtma berish\n"
            "📊 /narxlar — Narxlar va xizmatlar\n"
            "🧺 /parda — Parda yechib-ilib berish xizmati\n"
            "🎁 /aksiya — Chegirmalar va aksiyalar\n"
            "🌐 /ijtimoy — Guruhimiz va Instagram"
        )
        await message.reply(welcome_text, parse_mode="Markdown")

# 2. Tezkor buyurtma berish
@dp.message_handler(commands=['buyurtma'])
async def send_order_info(message: types.Message):
    order_text = (
        "📦 *Tezkor buyurtma berish:*\n\n"
        "Gilam, ko'rpa-to'shak yoki pardalaringizni yuvishga topshirish uchun hozirning o'zidayoq operatorimiz bilan bog'laning!\n\n"
        "📞 *Telefon raqamlarimiz:*\n"
        "☎️ (88) 263 63 63\n"
        "☎️ (88) 577 63 63\n\n"
        "🚚 Termiz shahri bo'ylab olib ketish va yetkazib berish *mutlaqo bepul!*"
    )
    await message.reply(order_text, parse_mode="Markdown")

# 3. Narxlar va xizmatlar (guruhda ham, shaxsiy chatda ham ishlaydi)
@dp.message_handler(commands=['narxlar'])
@dp.message_handler(lambda message: any(word in message.text.lower() for word in ['narx', 'narxi', 'qancha', 'necha pul', 'narxlar', 'adyol', 'ko\'rpa', 'mebel']))
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

# 4. Parda yechib-ilib berish xizmati
@dp.message_handler(commands=['parda'])
async def send_parda_info(message: types.Message):
    parda_text = (
        "🧺 *Parda yechib-ilib berish xizmati:*\n\n"
        "Uyingizdan chiqib, parda yechishga va uni qayta ilishga vaqt sarflamang! "
        "Xodimlarimiz uyingizga borib, pardalarni *o'zlari ehtiyotkorlik bilan yechib olishadi* va yuvib bo'lingach, *yana o'zlari ilib berishadi*! 😎\n\n"
        "💰 *Xizmat narxi:* 1 kg parda uchun — 40 000 so'm (Yuvish + Yechish + Ilib berish ichida)\n\n"
        "📞 *Bog'lanish:* (88) 263 63 63 | (88) 577 63 63"
    )
    await message.reply(parda_text, parse_mode="Markdown")

# 5. Chegirmalar va aksiyalar (Hozircha aksiya yo'qligi haqida)
@dp.message_handler(commands=['aksiya'])
async def send_promo(message: types.Message):
    promo_text = (
        "🎁 *Chegirmalar va Aksiyalar:*\n\n"
        "Hozircha faol aksiyalarimiz mavjud emas. Yaqin kunlarda siz uchun ajoyib va foydali aksiyalar e'lon qilamiz! 🔥\n\n"
        "📢 Yangi aksiyalar va chegirmalar boshlanganda guruhimizda va ijtimoiy tarmoqlarimizda albatta xabar beramiz. Bizni kuzatishda davom eting!\n\n"
        "📞 *Ma'lumot uchun:* (88) 263 63 63 | (88) 577 63 63"
    )
    await message.reply(promo_text, parse_mode="Markdown")

# 6. Ijtimoiy tarmoqlar
@dp.message_handler(commands=['ijtimoy'])
async def send_socials(message: types.Message):
    social_text = (
        "🌐 *Bizning ijtimoiy tarmoqlarimiz:*\n\n"
        "💬 Telegram Guruhimiz: [Qo'shilish](https://t.me)\n"
        "📸 Instagram Profilimiz: [Kuzatish](https://instagram.com)"
    )
    await message.reply(social_text, parse_mode="Markdown", disable_web_page_preview=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
