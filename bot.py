 import os
import sys
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO)

# Мини-сервер для порта Render
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# Конфигурация бота
BOT_TOKEN = "8528672756:AAFekL_eklAvcJXaLxozRdZ1wfARz-tN-lY"
TIMEZONE_NAME = "Asia/Sakhalin"
TZ = pytz.timezone(TIMEZONE_NAME)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TZ)

# Расписание ОЭ-2401 (0 = Понедельник, 1 = Вторник, ..., 6 = Воскресенье)
SCHEDULE = {
    0: [
        {"num": 1, "time": "09:40 - 11:00", "subject": "ТРМиНЭиЭМО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 2, "time": "11:10 - 12:30", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 3, "time": "13:00 - 14:20", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 4, "time": "14:30 - 15:50", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
    ],
    1: [
        {
            "num": 1, 
            "time": "09:00 - 10:20", 
            "subject": "Иностранный язык в ПД", 
            "subgroups": [
                {"name": "1 п/г", "teacher": "Мезенцева В.А.", "room": "34"},
                {"name": "2 п/г", "teacher": "Прошакова И.В.", "room": "41"},
            ]
        },
        {"num": 2, "time": "10:30 - 11:50", "subject": "БЖД", "teacher": "Горбунова А.Л.", "room": "8"},
        {"num": 3, "time": "12:20 - 13:40", "subject": "БЖД", "teacher": "Горбунова А.Л.", "room": "8"},
        {"num": 4, "time": "13:50 - 15:10", "subject": "Физическая культура", "teacher": "Родя К.С.", "room": "СЗ"},
    ],
    2: [
        {"num": 1, "time": "09:00 - 10:20", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 2, "time": "10:30 - 11:50", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 3, "time": "12:20 - 13:40", "subject": "ТРМиНЭиЭМО", "teacher": "Тучин В.В.", "room": "32"},
    ],
    3: [
        {"num": 1, "time": "09:00 - 10:20", "subject": "БЖД", "teacher": "Горбунова А.Л.", "room": "8"},
        {"num": 2, "time": "10:30 - 11:50", "subject": "БЖД", "teacher": "Горбунова А.Л.", "room": "8"},
    ],
    4: [
        {"num": 1, "time": "09:00 - 10:20", "subject": "ТРМиНЭиЭМО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 2, "time": "10:30 - 11:50", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
        {"num": 3, "time": "12:20 - 13:40", "subject": "ООРпоИДЭО", "teacher": "Тучин В.В.", "room": "32"},
    ],
    5: [],
    6: []
}

site_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🌐 Открыть сайт СПЭТ", url="https://time.spetpro.ru/#s/OE-2401")]
])

def render_schedule(target_date: datetime) -> str:
    weekday = target_date.weekday()
    date_label = target_date.strftime("%d.%m.%Y")
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = days_ru[weekday]

    lessons = SCHEDULE.get(weekday, [])

    if not lessons:
        return f"📅 <b>{day_name}, {date_label}</b>\n\n🎉 Занятий нет, выходной день!"

    text = f"📚 <b>Расписание ОЭ-2401 на {day_name} ({date_label}):</b>\n\n"

    for item in lessons:
        num = item["num"]
        time_slot = item["time"]
        subject = item["subject"]

        text += f"🔹 <b>{num} пара ({time_slot})</b>\n"
        text += f"📖 <b>{subject}</b>\n"

        if "subgroups" in item:
            for sg in item["subgroups"]:
                text += f"  ▫️ {sg['name']}: {sg['teacher']} | Каб: <b>{sg['room']}</b>\n"
        else:
            text += f"🚪 Кабинет: <b>{item['room']}</b> | 👤 {item['teacher']}\n"
        text += "\n"

    return text

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Бот расписания для группы <b>ОЭ-2401</b> готов!\n\n"
        "Команды:\n"
        "▪ /today — Расписание на сегодня\n"
        "▪ /tomorrow — Расписание на завтра\n"
        "▪ /now — Текущая пара",
        reply_markup=site_keyboard,
        parse_mode="HTML"
    )

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    now = datetime.now(TZ)
    text = render_schedule(now)
    await message.answer(text, reply_markup=site_keyboard, parse_mode="HTML")

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.now(TZ) + timedelta(days=1)
    text = render_schedule(tomorrow)
    await message.answer(text, reply_markup=site_keyboard, parse_mode="HTML")

@dp.message(Command("now"))
async def cmd_now(message: types.Message):
    now = datetime.now(TZ)
    weekday = now.weekday()
    current_time = now.strftime("%H:%M")
    lessons = SCHEDULE.get(weekday, [])

    if not lessons:
        await message.answer("🎉 Сегодня пар нет!", reply_markup=site_keyboard)
        return

    current_item = None
    next_item = None

    for item in lessons:
        start_str, end_str = item["time"].split(" - ")
        if start_str <= current_time <= end_str:
            current_item = item
            break
        elif current_time < start_str and next_item is None:
            next_item = item

    if current_item:
        msg = f"⏱ <b>Сейчас идет {current_item['num']}-я пара ({current_item['time']})</b>\n"
        msg += f"📖 {current_item['subject']}\n"
        if "subgroups" in current_item:
            for sg in current_item["subgroups"]:
                msg += f"  ▫️ {sg['name']}: каб. <b>{sg['room']}</b> ({sg['teacher']})\n"
        else:
            msg += f"🚪 Кабинет: <b>{current_item['room']}</b> ({current_item['teacher']})"
        await message.answer(msg, reply_markup=site_keyboard, parse_mode="HTML")
    elif next_item:
        start_str = next_item["time"].split(" - ")[0]
        msg = f"☕️ <b>Сейчас перемена!</b>\n"
        msg += f"Следующая <b>{next_item['num']}-я пара</b> начнется в <b>{start_str}</b>:\n"
        msg += f"📖 {next_item['subject']}"
        await message.answer(msg, reply_markup=site_keyboard, parse_mode="HTML")
    else:
        await message.answer("🌙 Все пары на сегодня уже завершены!", reply_markup=site_keyboard)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
