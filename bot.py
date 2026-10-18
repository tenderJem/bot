import asyncio
from datetime import datetime, timedelta
import pytz
import requests

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= КОНФИГУРАЦИЯ =================
# 1. Токен от @BotFather:
BOT_TOKEN = "8528672756:AAFxLXisoJaFlwifjehh_SMd2m2lQEBZ3S0"
# 2. Твой личный ID от @userinfobot:
USER_CHAT_ID = 8380835222

# Группа и таймзона (Asia/Sakhalin для СПЭТ, UTC+11)
GROUP_NAME = "ОЭ-2401"
TIMEZONE_NAME = "Asia/Sakhalin"
TIMEZONE = pytz.timezone(TIMEZONE_NAME)
# ================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Сетка звонков колледжа
TIME_SLOT_MAP = {
    1: ("09:00", "10:20"),
    2: ("10:30", "11:50"),
    3: ("12:20", "13:40"),
    4: ("13:50", "15:20"),
    5: ("15:30", "17:00"),
    6: ("17:10", "18:40"),
}


def get_schedule_for_date(target_date: datetime.date) -> list:
    """Получает расписание для группы с API time.spetpro.ru."""
    date_str = target_date.strftime("%Y-%m-%d")

    api_urls = [
        f"https://time.spetpro.ru/api/schedule?group={GROUP_NAME}&date={date_str}",
        f"https://time.spetpro.ru/api/timetable?group={GROUP_NAME}&date={date_str}",
        f"https://time.spetpro.ru/api/groups/{GROUP_NAME}?date={date_str}"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://time.spetpro.ru/"
    }

    data = None
    for url in api_urls:
        try:
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                break
        except Exception:
            continue

    lessons = []
    if not data:
        return lessons

    raw_lessons = data if isinstance(data, list) else data.get("lessons", data.get("schedule", []))

    for item in raw_lessons:
        subject = item.get("subject", item.get("name", item.get("discipline", "Пара")))
        room = item.get("room", item.get("cabinet", item.get("auditory", "Не указан")))
        start_time = item.get("start", item.get("time_start", item.get("time", "")))
        end_time = item.get("end", item.get("time_end", ""))
        teacher = item.get("teacher", "")
        pair_num = item.get("num", item.get("pair", ""))

        try:
            p_int = int(pair_num)
            if not start_time and p_int in TIME_SLOT_MAP:
                start_time, end_time = TIME_SLOT_MAP[p_int]
        except (ValueError, TypeError):
            pass

        lessons.append({
            "num": pair_num,
            "subject": subject,
            "room": room,
            "start": start_time,
            "end": end_time,
            "teacher": teacher
        })

    return lessons


def format_schedule(lessons: list, title: str) -> str:
    if not lessons:
        return f"🎉 <b>{title}</b>\n\nПар нет! Можно отдыхать."

    text = f"📅 <b>{title}</b>\n\n"
    for i, l in enumerate(lessons, 1):
        num_str = f"[{l['num']} пара] " if l.get("num") else f"{i}. "
        time_str = f" ({l['start']} - {l['end']})" if l.get("start") else ""
        text += f"🔹 <b>{num_str}{l['subject']}</b>{time_str}\n"
        text += f"   🚪 Кабинет: <code>{l['room']}</code>\n"
        if l.get("teacher"):
            text += f"   👨‍🏫 Преподаватель: {l['teacher']}\n"
        text += "\n"
    return text


# ================= АВТОМАТИЧЕСКИЕ ПУШИ =================

async def send_evening_digest():
    """Каждый вечер шлет расписание на завтра."""
    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    lessons = get_schedule_for_date(tomorrow)
    msg = format_schedule(lessons, f"Расписание на завтра ({tomorrow.strftime('%d.%m.%Y')})")
    try:
        await bot.send_message(USER_CHAT_ID, msg, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки вечернего дайджеста: {e}")


async def check_current_and_upcoming_lesson():
    """Проверка каждые 5 минут: напоминание за 10 мин и в момент звонка."""
    now = datetime.now(TIMEZONE)
    today = now.date()
    lessons = get_schedule_for_date(today)

    for l in lessons:
        if not l.get("start"):
            continue

        try:
            lesson_start = datetime.strptime(f"{today} {l['start']}", "%Y-%m-%d %H:%M")
            lesson_start = TIMEZONE.localize(lesson_start)

            diff_minutes = (lesson_start - now).total_seconds() / 60

            # За 10 минут до звонка
            if 6 <= diff_minutes <= 11:
                alert = (
                    f"⏰ <b>Скоро пара (через 10 минут)!</b>\n\n"
                    f"📖 <b>{l['subject']}</b>\n"
                    f"🚪 Кабинет: <code>{l['room']}</code>\n"
                    f"⏱ Начало: {l['start']}"
                )
                await bot.send_message(USER_CHAT_ID, alert, parse_mode="HTML")

            # В момент звонка
            elif 0 <= -diff_minutes <= 4:
                alert = (
                    f"🔔 <b>Пара началась!</b>\n\n"
                    f"📖 <b>{l['subject']}</b>\n"
                    f"🚪 Кабинет: <code>{l['room']}</code>"
                )
                await bot.send_message(USER_CHAT_ID, alert, parse_mode="HTML")

        except Exception:
            continue


# ================= РУЧНЫЕ КОМАНДЫ =================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Бот расписания для группы <b>ОЭ-2401</b> готов к работе!\n\n"
        "Команды:\n"
        "▫️ /today — расписание на сегодня\n"
        "▫️ /tomorrow — расписание на завтра\n"
        "▫️ /now — какая пара сейчас и какой кабинет\n\n"
        "<i>Уведомления за 10 мин до пары и каждый вечер на завтра приходят на автомате.</i>",
        parse_mode="HTML"
    )


@dp.message(Command("today"))
async def cmd_today(message: Message):
    today = datetime.now(TIMEZONE).date()
    lessons = get_schedule_for_date(today)
    msg = format_schedule(lessons, f"Расписание на сегодня ({today.strftime('%d.%m.%Y')})")
    await message.answer(msg, parse_mode="HTML")


@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message):
    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    lessons = get_schedule_for_date(tomorrow)
    msg = format_schedule(lessons, f"Расписание на завтра ({tomorrow.strftime('%d.%m.%Y')})")
    await message.answer(msg, parse_mode="HTML")


@dp.message(Command("now"))
async def cmd_now(message: Message):
    now = datetime.now(TIMEZONE)
    today = now.date()
    lessons = get_schedule_for_date(today)

    current_lesson = None
    next_lesson = None

    for l in lessons:
        if not l.get("start") or not l.get("end"):
            continue
        start = TIMEZONE.localize(datetime.strptime(f"{today} {l['start']}", "%Y-%m-%d %H:%M"))
        end = TIMEZONE.localize(datetime.strptime(f"{today} {l['end']}", "%Y-%m-%d %H:%M"))

        if start <= now <= end:
            current_lesson = l
            break
        elif start > now and next_lesson is None:
            next_lesson = l

    if current_lesson:
        await message.answer(
            f"📍 <b>Сейчас идет пара:</b>\n\n"
            f"📖 <b>{current_lesson['subject']}</b>\n"
            f"🚪 Кабинет: <code>{current_lesson['room']}</code>\n"
            f"⏱ Идет до: {current_lesson['end']}",
            parse_mode="HTML"
        )
    elif next_lesson:
        await message.answer(
            f"☕ <b>Сейчас перемена.</b>\n\n"
            f"Следующая пара: <b>{next_lesson['subject']}</b>\n"
            f"🚪 Кабинет: <code>{next_lesson['room']}</code>\n"
            f"⏱ Начало в: {next_lesson['start']}",
            parse_mode="HTML"
        )
    else:
        await message.answer("Сейчас никаких пар нет.")


# ================= ТОЧКА ВХОДА =================

async def main():
    # Вечерняя рассылка на завтра в 19:30
    scheduler.add_job(send_evening_digest, "cron", hour=19, minute=30)

    # Проверка приближающейся пары каждые 5 минут
    scheduler.add_job(check_current_and_upcoming_lesson, "interval", minutes=5)

    scheduler.start()
    print("Бот расписания запущен и слушает команды...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

