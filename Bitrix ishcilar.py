import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, time, date
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict

# 🔐 TOKEN va ID lar
TOKEN = "8284461914:AAEv7aoHgMfrViKpQkIGxm1lJxqIyrIZ1Wc"
admin_id = 7530522892
log_chat_id = -1002143893100  # Guruh loglar uchun

# Google Sheets ulanish
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
SPREADSHEET_ID = "1QRGqsZEZI2hDRCE3aZ2hi79Uyg5nmW7vSYcdpCpbGxE"
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1

# Vaqt zonasi
tz = pytz.timezone("Asia/Tashkent")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Ish boshlanish vaqti (soat 9:00)
work_start = time(9, 0)

# Hodimlar ro'yxati
employee_names = {
    5171756780: "Zokir",
    5917861933: "Yusuf",
    5149506457: "Umid",
}

# Klaviaturalar
only_start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📥 Ishga keldim")]],
    resize_keyboard=True
)

full_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📤 Ishdan chiqdim")]],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📊 Hisobot")]],
    resize_keyboard=True
)

# Holatlarni saqlash
user_states = {}
user_times = {}
used_video_ids = {}
user_rows = {}
user_daily_limit = defaultdict(lambda: None)  # user_id -> sana

# /start komandasi
@dp.message(F.text == "/start")
async def start_handler(msg: Message):
    if msg.from_user.id == admin_id:
        await msg.reply("👋 Assalomu alekum Ibrohim aka:", reply_markup=admin_keyboard)
    else:
        await msg.reply(
            f"👋 Assalomu alaykum, {msg.from_user.full_name}!\n"
            "Quyidagi tugmalar orqali ish vaqtini belgilashingiz mumkin.",
            reply_markup=only_start_keyboard
        )


@dp.message(F.text == "📊 Hisobot")
async def report_handler(msg: Message):
    print(msg)
    if msg.from_user.id != admin_id:
        await msg.reply("⛔ Sizda bu amal uchun ruxsat yo‘q.")
        return

    sheet_url = "https://docs.google.com/spreadsheets/d/1QRGqsZEZI2hDRCE3aZ2hi79Uyg5nmW7vSYcdpCpbGxE/edit"
    await msg.reply(
        f"📊 Hisobot Google Sheets’ga yozib borilmoqda.\n\n👉 <a href='https://docs.google.com/spreadsheets/d/1QRGqsZEZI2hDRCE3aZ2hi79Uyg5nmW7vSYcdpCpbGxE/edit'>Google Sheets’ni ochib ko‘rishingiz mumkin</a>.",
        disable_web_page_preview=True
    )

    all_records = sheet.get_all_records()
    now = datetime.now(tz)
    current_month = now.strftime("%Y-%m")

    monthly = [r for r in all_records if str(r['Ishga keldi']).startswith(current_month)]

    if not monthly:
        await msg.reply("📊 Bu oy uchun ma’lumot topilmadi.")
        return

    text = f"📊 {now.strftime('%B %Y')} hisobot:\n\n"
    for r in monthly:
        text += f"👤 {r['Ism']}\n🕒 {r['Ishga keldi']} - {r['Ishdan chiqdi']}\n⏰ {r['Ish vaqti']}\n\n"

    await msg.reply(text, disable_web_page_preview=True)

# 📥 Ishga keldim
@dp.message(F.text == "📥 Ishga keldim")
async def start_work(msg: Message):
    user_id = msg.from_user.id
    today = date.today()

    # 🔒 Kunlik cheklov
    if user_daily_limit[user_id] == today:
        await msg.reply("⚠️ Siz bugun allaqachon ro‘yxatdan o‘tgansiz. Ertaga yana urinib ko‘ring.")
        return

    user_states[user_id] = "start"
    await msg.reply("📹 Dumaloq video yuboring.", reply_markup=only_start_keyboard)

# 📤 Ishdan chiqdim
@dp.message(F.text == "📤 Ishdan chiqdim")
async def end_work(msg: Message):
    user_id = msg.from_user.id
    now = datetime.now(tz)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    times = user_times.get(user_id)
    row = user_rows.get(user_id)

    if not times or "start" not in times:
        await msg.reply("⚠️ Avval '📥 Ishga keldim' tugmasini bosib dumaloq video yuboring.",
                        reply_markup=only_start_keyboard)
        return

    start_time = times["start"]
    delta = now - start_time
    soat = delta.seconds // 3600
    minut = (delta.seconds % 3600) // 60

    if now.time() < time(18, 0):
        user_states[user_id] = "early_leave_reason"
        await msg.reply("⚠️ Siz 18:00 dan oldin ketmoqchisiz. Iltimos, ketish sababini yozing.")
        return

    # Google Sheets yangilash
    if row:
        sheet.update_cell(row, 3, now_str)  # Ketgan vaqti
        sheet.update_cell(row, 4, f"{soat} soat {minut} daqiqa")  # Ishlagan vaqt
        sheet.update_cell(row, 7, "-")  # Ketish sababi

    await msg.reply(f"✅ Bugun ishlagan vaqt: <b>{soat} soat {minut} daqiqa</b>", reply_markup=only_start_keyboard)

    # Tozalash
    user_states.pop(user_id, None)
    user_times.pop(user_id, None)
    user_rows.pop(user_id, None)

# Dumaloq video (faqat ishga kelganda)
@dp.message(F.video_note)
async def handle_video_note(msg: Message):
    user_id = msg.from_user.id
    video = msg.video_note
    unique_id = video.file_unique_id

    if msg.forward_date or msg.forward_from or msg.forward_sender_name:
        await msg.reply("❌ Forward qilingan video yuborish mumkin emas.")
        return

    if user_id in used_video_ids and unique_id in used_video_ids[user_id]:
        await msg.reply("⚠️ Bu video allaqachon qabul qilingan.")
        return

    state = user_states.get(user_id)
    if not state:
        await msg.reply("⛔ Iltimos, tugmalardan foydalaning.", reply_markup=only_start_keyboard)
        return

    used_video_ids.setdefault(user_id, set()).add(unique_id)
    now = datetime.now(tz)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    user_name = employee_names.get(user_id, msg.from_user.full_name)

    if state == "start":
        user_times[user_id] = {"start": now}
        user_daily_limit[user_id] = date.today()  # ✅ Kunlik belgilash

        # ⏰ Kechikishni hisoblash
        late_minutes = (datetime.combine(date.today(), now.time()) -
                        datetime.combine(date.today(), work_start)).total_seconds() / 60
        if late_minutes > 0:
            late_hours = int(late_minutes // 60)
            late_min = int(late_minutes % 60)
            late_text = f"{late_hours} soat {late_min} daqiqa kechikdi"
            user_states[user_id] = "late_reason"
            await msg.reply(f"✅ Ishga kelgan vaqt: <b>{now_str}</b>\n⏰ {late_text}\n\n"
                            f"⚠️ Siz kechikdingiz. Iltimos, sababini yozing.")
        else:
            late_text = "-"
            user_states[user_id] = None
            await msg.reply(f"✅ Ishga kelgan vaqt: <b>{now_str}</b>\n⏰ {late_text}", reply_markup=full_keyboard)

        # Google Sheetsga yozish
        sheet.append_row([
            user_name,
            now_str,
            "-",  # Ketgan vaqti
            "-",  # Ishlagan vaqt
            late_text,
            "-",  # Sababi
            "-"   # Ketish sababi
        ])

        user_rows[user_id] = len(sheet.col_values(1))  # oxirgi qator

        # Guruhga xabar
        await bot.send_video_note(chat_id=log_chat_id, video_note=video.file_id)
        await bot.send_message(chat_id=log_chat_id, text=f"👤 {user_name}\n🕒 {now_str}\n⏰ {late_text}")

        # Admin uchun
        await bot.send_message(admin_id,
            f"👤 <b>{user_name}</b>\n"
            f"🕒 Ishga keldi: <b>{now_str}</b>\n"
            f"⏰ {late_text}"
        )

# 📝 Sabablarni qabul qilish (kechikish yoki erta ketish)
@dp.message()
async def reason_handler(msg: Message):
    user_id = msg.from_user.id
    state = user_states.get(user_id)
    if state not in ["late_reason", "early_leave_reason"]:
        return

    reason_text = msg.text
    row = user_rows.get(user_id)
    if not row:
        await msg.reply("⚠️ Google Sheets’da yozuv topilmadi.")
        return

    if state == "late_reason":
        sheet.update_cell(row, 6, reason_text)  # Kechikish sababi
        await msg.reply("✅ Kechikish sababi saqlandi.", reply_markup=full_keyboard)
        user_states[user_id] = None  # ishlash davom etadi

    elif state == "early_leave_reason":
        sheet.update_cell(row, 7, reason_text)  # Ketish sababi

        # Vaqtlarni hisoblash
        end_dt = datetime.now(tz)
        end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        start_time_str = sheet.cell(row, 2).value
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        start_time = tz.localize(start_time)  # ❗ tz qo‘shildi

        worked = end_dt - start_time
        soat = worked.seconds // 3600
        minut = (worked.seconds % 3600) // 60

        # Google Sheets yangilash
        sheet.update_cell(row, 3, end_time_str)
        sheet.update_cell(row, 4, f"{soat} soat {minut} daqiqa")

        await msg.reply("✅ Erta chiqish sababi saqlandi.", reply_markup=only_start_keyboard)

        # Tozalash
        user_states.pop(user_id, None)
        user_times.pop(user_id, None)
        user_rows.pop(user_id, None)



# Botni ishga tushurish
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
