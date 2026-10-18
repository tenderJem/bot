import os
import sys
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
import requests
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Буферизация вывода
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO)

# Мини веб-сервер для удержания порта на Render
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

# Конфигурация
BOT_TOKEN = "8528672756:AAFxLXisoJaFlwifjehh_SMd2m21QEBZ3S0"
TIMEZONE_NAME = "Asia/Sakhalin"
TZ = pytz.timezone(TIMEZONE_NAME)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TZ)

GROUP_QUERY = "OE-2401"
API_BASE_URL = "https://time.spetpro.ru/api"

# Звонки пар по умолчанию (для команды /now)
LESSON_BELLS = {
    1: ("08:30", "10:00"),
    2: ("10:15", "11:45"),
    3: ("12:15", "13:45"),
    4: ("14:00", "15:30"),
    5: ("15:45", "17:15"),
    6: ("17:25", "18:55"),
}

def fetch_group_schedule(target_date: datetime):
    date_str = target_date.strftime("%Y-%m-%d")
    urls_to_try = [
        f"{API_BASE_URL}/timetable?group={GROUP_QUERY}&date={date_str}",
        f"{API_BASE_URL}/schedule/{GROUP_QUERY}?date={date_str}",
        f"{API_BASE_URL}/schedule?group={GROUP_QUERY}",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    for url in urls_to_try:
        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                if data:
                    return data
        except Exception as e:
            logging.warning(f"Ошибка запроса {url}: {e}")

    return None

def format_schedule_message(target_date: datetime, data) -> str:
    date_label = target_date.strftime("%d.%m.%Y")
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = days_ru[target_date.weekday()]

    if not data:
        return (
            f"📅 <b>{day_name}, {date_label}</b>\n\n"
            f"⚠️ Расписание на сайте еще не опубликовано или пар нет.\n"
            f"Ссылка на сайт: https://time.spetpro.ru/#s/{GROUP_QUERY}"
        )

    lessons = []
    if isinstance(data, dict):
        lessons = data.get("lessons") or data.get("items") or data.get("schedule") or []
    elif isinstance(data, list):
        lessons = data

    if not lessons:
        return f"📅 <b>{day_name}, {date_label}</b>\n\n🎉 Пар нет, выходной день!"

    text = f"📚 <b>Расписание ОЭ-2401 на {day_name} ({date_label}):</b>\n\n"

    for idx, item in enumerate(lessons, 1):
        num = item.get("num") or item.get("lesson_number") or idx
        subject = item.get("subject") or item.get("name") or "Дисциплина не указана"
        room = item.get("room") or item.get("cabinet") or "—"
        teacher = item.get("teacher") or item.get("fio") or ""
        time_slot = LESSON_BELLS.get(int(num), ("", ""))
        time_text = f" ({time_slot[0]} - {time_slot[1]})" if time_slot[0] else ""

        text += f"🔹 <b>{num} пара{time_text}</b>\n"
        text += f"📖 <i>{subject}</i>\n"
        text += f"🚪 Кабинет: <b>{room}</b>"
        if teacher:
            text += f" | 👤 {teacher}"
        text += "\n\n"

    return text

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Бот расписания для группы <b>ОЭ-2401</b> запущен!\n\n"
        "Доступные команды:\n"
        "▪ /today — Расписание на сегодня\n"
        "▪ /tomorrow — Расписание на завтра\n"
        "▪ /now — Текущая пара\n\n"
        "🌐 Ссылка: https://time.spetpro.ru/#s/OE-2401",
        parse_mode="HTML"
    )

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    now = datetime.now(TZ)
    data = fetch_group_schedule(now)
    text = format_schedule_message(now, data)
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.now(TZ) + timedelta(days=1)
    data = fetch_group_schedule(tomorrow)
    text = format_schedule_message(tomorrow, data)
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("now"))
async def cmd_now(message: types.Message):
    now = datetime.now(TZ)
    current_time = now.strftime("%H:%M")
    
    current_lesson = None
    next_lesson = None

    for num, (start, end) in LESSON_BELLS.items():
        if start <= current_time <= end:
            current_lesson = num
            break
        elif current_time < start and next_lesson is None:
            next_lesson = (num, start)

    if current_lesson:
        await message.answer(
            f"⏱ Сейчас идет <b>{current_lesson}-я пара</b> (звонок до {LESSON_BELLS[current_lesson][1]}).\n"
            f"Посмотреть аудиторию: /today",
            parse_mode="HTML"
        )
    elif next_lesson:
        await message.answer(
            f"☕️ Сейчас перемена или пары еще не начались.\n"
            f"Следующая пара: <b>{next_lesson[0]}-я</b>, начало в <b>{next_lesson[1]}</b>.",
            parse_mode="HTML"
        )
    else:
        await message.answer("🌙 Все пары на сегодня уже закончились!", parse_mode="HTML")

async def main():
    print("Сбрасываем вебхук...", flush=True)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот готов к обработке команд!", flush=True)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
