import os
import sqlite3
import jdatetime
import asyncio
from datetime import datetime, timedelta
from bale import Bot, Message, InlineKeyboardMarkup, InlineKeyboardButton

client = Bot(token=os.environ["BOT_TOKEN"])

BOT_USERNAME = "webinarcomputerbot"
ADMIN_ID = 1924418661
CHANNEL_ID = 6191660398

# state هر ادمین: در چه مرحله‌ای از ثبت آگهی هست
admin_states = {}

def get_db():
    return sqlite3.connect("bot_database.db")

@client.event
async def on_ready():
    print(client.user, "آماده است")

@client.event
async def on_message(message: Message):
    user_id = message.from_user.id
    content = message.content or ""

    # مدیریت لینک عمیق یادآوری - قبل از چک ادمین بودن!
    if content.startswith("/start remind_"):
        ad_id = int(content.split("remind_")[1])
        await handle_reminder_request(ad_id, user_id)
        return

    # فقط ادمین اجازه ثبت آگهی داره
    if user_id != ADMIN_ID:
        return

    # شروع فرآیند ثبت آگهی
    if message.content == "/newad":
        admin_states[user_id] = {"step": "title", "data": {}}
        await message.reply("عنوان رویداد رو بفرست:")
        return

    # اگه ادمین وسط فرآیند ثبت آگهیه
    if user_id in admin_states:
        state = admin_states[user_id]

        if state["step"] == "title":
            state["data"]["title"] = message.content
            state["step"] = "description"
            await message.reply("توضیحات رویداد رو بفرست:")

        elif state["step"] == "description":
            state["data"]["description"] = message.content
            state["step"] = "datetime"
            await message.reply("تاریخ و ساعت رویداد رو بفرست (فرمت: 1404-05-10 18:00):")

        elif state["step"] == "datetime":
            try:
                jalali_dt = jdatetime.datetime.strptime(message.content, "%Y-%m-%d %H:%M")
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 1404-05-10 18:00):")
                return  # از state خارج نمیشه، دوباره همین مرحله رو تلاش می‌کنه

            state["data"]["event_time"] = gregorian_dt.strftime("%Y-%m-%d %H:%M:%S")
            await finalize_ad(state["data"])
            del admin_states[user_id]

async def finalize_ad(data):
    # ذخیره در دیتابیس
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ads (title, description, event_time) VALUES (?, ?, ?)",
        (data["title"], data["description"], data["event_time"])
    )
    ad_id = cursor.lastrowid
    conn.commit()

    # ساخت دکمه و ارسال به کانال
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
    text="یادآوری بگیر 🔔",
    url=f"https://ble.ir/{BOT_USERNAME}?start=remind_{ad_id}"
    ))

    text = f"📢 {data['title']}\n\n{data['description']}\n\n🕒 زمان: {data['event_time']}"
    sent_message = await client.send_message(CHANNEL_ID, text, components=markup)

    # ذخیره message_id برای استفاده احتمالی بعدی
    cursor.execute(
        "UPDATE ads SET channel_message_id = ? WHERE id = ?",
        (sent_message.message_id, ad_id)
    )
    conn.commit()
    conn.close()

    await client.send_message(ADMIN_ID, "✅ آگهی با موفقیت در کانال ثبت و ارسال شد.")

@client.event

async def handle_reminder_request(ad_id: int, user_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT title, event_time FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        await client.send_message(user_id, "این آگهی دیگر معتبر نیست.")
        return

    title, event_time_str = row
    event_time = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M:%S")

    # چک کن آیا زمان رویداد گذشته
    if event_time <= datetime.now():
        conn.close()
        event_time_display = event_time.strftime("%Y/%m/%d ساعت %H:%M")
        await client.send_message(
            user_id,
            f"⛔ زمان رویداد «{title}» ({event_time_display}) گذشته است و امکان ثبت یادآوری برای آن وجود ندارد."
        )
        return

    remind_at = event_time - timedelta(minutes=30)
    remind_at_str = remind_at.strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute(
            "INSERT INTO reminders (ad_id, user_id, remind_at) VALUES (?, ?, ?)",
            (ad_id, user_id, remind_at_str)
        )
        conn.commit()
        already_registered = False
    except sqlite3.IntegrityError:
        already_registered = True

    conn.close()

    event_time_display = event_time.strftime("%Y/%m/%d ساعت %H:%M")

    if already_registered:
        text = f"شما قبلاً برای رویداد «{title}» یادآوری ثبت کرده‌اید. ✅"
    else:
        text = (
            f"✅ یادآوری شما با موفقیت ثبت شد!\n\n"
            f"📌 رویداد: {title}\n"
            f"🕒 زمان برگزاری: {event_time_display}\n\n"
            f"نیم ساعت قبل از شروع، پیامی از طرف ربات دریافت خواهید کرد."
        )

    await client.send_message(user_id, text)



async def reminder_loop():
    while True:
        await asyncio.sleep(60)  # هر ۶۰ ثانیه چک می‌کنه

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT reminders.id, reminders.user_id, ads.title FROM reminders "
            "JOIN ads ON reminders.ad_id = ads.id "
            "WHERE reminders.sent = 0 AND reminders.remind_at <= ?",
            (now_str,)
        )
        due_reminders = cursor.fetchall()

        for reminder_id, user_id, ad_title in due_reminders:
            try:
                await client.send_message(
                    user_id,
                   f"⏰ یادآوری رویداد!\n\n📌 «{ad_title}»\n\nنیم ساعت دیگر این رویداد آغاز می‌شود."
                )
                cursor.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
                conn.commit()
            except Exception as e:
                print(f"خطا در ارسال یادآوری به {user_id}: {e}")

        conn.close()


@client.event
async def on_ready():
    print(client.user, "آماده است")
    asyncio.create_task(reminder_loop())




client.run()