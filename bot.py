import os
import sys
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import pytz
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Сброс буфера логов
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO)

# Заглушка веб-сервера для Render (чтобы не убивал бота из-за портов)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass  # глушим мусорные логи запросов проверки от Render

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# Запуск фонового веб-сервера
threading.Thread(target=run_web_server, daemon=True).start()

# Настройки бота
BOT_TOKEN = "8528672756:AAFxLXisoJaFlwifjehh_SMd2m21QEBZ3S0"
TIMEZONE_NAME = "Asia/Sakhalin"
TZ = pytz.timezone(TIMEZONE_NAME)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TZ)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Бот расписания для группы ОЭ-2401 работает!\n\n"
        "Команды:\n"
        "/today — Расписание на сегодня\n"
        "/tomorrow — Расписание на завтра\n"
        "/now — Текущая пара"
    )

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    now = datetime.now(TZ)
    await message.answer(f"📅 Сегодня {now.strftime('%d.%m.%Y')}, расписание обновляется на сайте.")

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.now(TZ) + timedelta(days=1)
    await message.answer(f"📅 Завтра {tomorrow.strftime('%d.%m.%Y')}, расписание обновляется на сайте.")

@dp.message(Command("now"))
async def cmd_now(message: types.Message):
    await message.answer("🔍 Проверка текущей пары...")

async def main():
    print("Удаляем вебхук...", flush=True)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Вебхук удален, запускаем Telegram polling...", flush=True)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


