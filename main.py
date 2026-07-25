import os
import sqlite3
import jdatetime
import asyncio
from datetime import datetime, timedelta
from bale import (
    Bot, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    MenuKeyboardMarkup, MenuKeyboardButton, InputFile
)
from bale.error import BaleError

client = Bot(token=os.environ["BOT_TOKEN"])
CHANNEL_USERNAME = "testnotif"
BOT_USERNAME = "webinarcomputerbot"
ADMIN_ID = 1924418661
CHANNEL_ID = 6191660398

admin_states = {}

# ---------- منوها ----------
BTN_NEW_AD = "➕ ثبت آگهی جدید"
BTN_LIST_ADS = "📋 لیست آگهی‌ها"
BTN_HELP = "ℹ️ راهنما"
SKIP_TEXT = "⏭ رد کردن (بدون بنر)"

def build_skip_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=SKIP_TEXT), row=1)
    return markup

def build_admin_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=BTN_NEW_AD), row=1)
    markup.add(MenuKeyboardButton(text=BTN_LIST_ADS), row=1)
    return markup

def build_user_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=BTN_HELP), row=1)
    return markup


def get_db():
    return sqlite3.connect("bot_database.db")

def to_jalali_display(gregorian_str: str) -> str:
    gregorian_dt = datetime.strptime(gregorian_str, "%Y-%m-%d %H:%M:%S")
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=gregorian_dt)
    return jalali_dt.strftime("%Y/%m/%d - %H:%M")


# ---------- ready ----------
@client.event
async def on_ready():
    print(client.user, "آماده است")
    asyncio.create_task(reminder_loop())


# ---------- پیام‌ها ----------
@client.event
async def on_message(message: Message):
    user_id = message.from_user.id
    content = (message.content or "").strip()

    # ---- شروع (کاربر یا ادمین) ----
    if content.startswith("/start"):
        parts = content.split(" ", 1)
        payload = parts[1] if len(parts) > 1 else "none"

        if user_id == ADMIN_ID:
            await message.reply("سلام ادمین 👋 خوش آمدید.", components=build_admin_menu())
            return

        if not await is_user_member(user_id):
            await send_join_required(user_id, payload)
            return

        await handle_start_payload(user_id, payload)
        await message.reply("از منوی زیر استفاده کنید:", components=build_user_menu())
        return

    # ---- دکمه راهنما برای کاربر عادی ----
    if content == BTN_HELP:
        await message.reply("این ربات برای دریافت یادآوری رویدادهای کانال است. کافیست روی دکمه یادآوری زیر هر آگهی در کانال بزنید.")
        return

    # ---- از اینجا به بعد فقط ادمین ----
    if user_id != ADMIN_ID:
        return

    # دکمه‌های منوی ادمین
    if content == BTN_NEW_AD:
        admin_states[user_id] = {"mode": "newad", "step": "title", "data": {}}
        await message.reply("عنوان رویداد رو بفرست:")
        return

    if content == BTN_LIST_ADS:
        await send_ads_list(user_id)
        return

    # ---- ادامه‌ی مکالمه‌ی جاری (ثبت یا ویرایش) ----
    if user_id in admin_states:
        await handle_admin_conversation(message, admin_states[user_id])


async def handle_admin_conversation(message: Message, state: dict):
    user_id = message.from_user.id
    content = (message.content or "").strip()
    mode = state["mode"]

    # ===================== ثبت آگهی جدید =====================
    if mode == "newad":
        if state["step"] == "title":
            state["data"]["title"] = content
            state["step"] = "description"
            await message.reply("توضیحات رویداد رو بفرست:")

        elif state["step"] == "description":
            state["data"]["description"] = content
            state["step"] = "date"
            await message.reply("تاریخ رویداد رو بفرست (فرمت: 1404/05/10):")

        elif state["step"] == "date":
            try:
                jdatetime.datetime.strptime(content, "%Y/%m/%d")
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 1404/05/10):")
                return
            state["data"]["date_str"] = content
            state["step"] = "time"
            await message.reply("ساعت رویداد رو بفرست (فرمت: 18:00):")

        elif state["step"] == "time":
            try:
                full_str = f"{state['data']['date_str']} {content}"
                jalali_dt = jdatetime.datetime.strptime(full_str, "%Y/%m/%d %H:%M")
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت ساعت اشتباهه. دوباره امتحان کن (مثال: 18:00):")
                return
            state["data"]["event_time"] = gregorian_dt.strftime("%Y-%m-%d %H:%M:%S")
            state["step"] = "banner"
            await message.reply("اگه بنر داری بفرست، یا از دکمه زیر رد کن:", components=build_skip_menu())

        elif state["step"] == "banner":
            if content == SKIP_TEXT or content == "/skip":
                state["data"]["photo_file_id"] = None
            elif message.photos:
                state["data"]["photo_file_id"] = message.photos[-1].file_id
            else:
                await message.reply("لطفاً یک عکس بفرست یا از دکمه رد کردن استفاده کن:", components=build_skip_menu())
                return

            await client.send_message(user_id, "بازگشت به منو:", components=build_admin_menu())
            del admin_states[user_id]

    # ===================== ویرایش یک فیلد آگهی =====================
    elif mode == "editfield":
        field = state["field"]
        ad_id = state["ad_id"]

        if field == "title":
            await update_ad_field(ad_id, "title", content)
            await message.reply("عنوان با موفقیت ویرایش شد ✅", components=build_admin_menu())
            del admin_states[user_id]

        elif field == "description":
            await update_ad_field(ad_id, "description", content)
            await message.reply("توضیحات با موفقیت ویرایش شد ✅", components=build_admin_menu())
            del admin_states[user_id]

        elif field == "date":
            try:
                jdatetime.datetime.strptime(content, "%Y/%m/%d")
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 1404/05/10):")
                return
            state["date_str"] = content
            state["field"] = "date_time"
            await message.reply("ساعت جدید رو بفرست (فرمت: 18:00):")

        elif field == "date_time":
            try:
                full_str = f"{state['date_str']} {content}"
                jalali_dt = jdatetime.datetime.strptime(full_str, "%Y/%m/%d %H:%M")
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت ساعت اشتباهه. دوباره امتحان کن (مثال: 18:00):")
                return
            new_event_time = gregorian_dt.strftime("%Y-%m-%d %H:%M:%S")
            await update_ad_field(ad_id, "event_time", new_event_time)
            await message.reply("تاریخ و ساعت با موفقیت ویرایش شد ✅", components=build_admin_menu())
            del admin_states[user_id]

        elif field == "banner":
            if content == SKIP_TEXT or content == "/skip":
                new_photo_id = None
            elif message.photos:
                new_photo_id = message.photos[-1].file_id
            else:
                await message.reply("لطفاً یک عکس بفرست یا از دکمه رد کردن استفاده کن:", components=build_skip_menu())
                return
            await update_ad_field(ad_id, "photo_file_id", new_photo_id)
            await message.reply("بنر با موفقیت به‌روزرسانی شد ✅", components=build_admin_menu())
            del admin_states[user_id]


# ---------- ثبت نهایی آگهی جدید ----------
async def finalize_ad(data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ads (title, description, event_time, photo_file_id) VALUES (?, ?, ?, ?)",
        (data["title"], data["description"], data["event_time"], data.get("photo_file_id"))
    )
    ad_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await post_ad_to_channel(ad_id)
    await client.send_message(ADMIN_ID, "✅ آگهی با موفقیت در کانال ثبت و ارسال شد.", components=build_admin_menu())


# ---------- ارسال/بازارسال آگهی به کانال ----------
async def post_ad_to_channel(ad_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, description, event_time, photo_file_id FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return

    title, description, event_time, photo_file_id = row
    jalali_display = to_jalali_display(event_time)
    text = f"📢 {title}\n\n{description}\n\n🕒 زمان: {jalali_display}"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        text="یادآوری بگیر 🔔",
        url=f"https://ble.ir/{BOT_USERNAME}?start=remind_{ad_id}"
    ))

    if photo_file_id:
        photo = InputFile(photo_file_id)
        sent_message = await client.send_photo(CHANNEL_ID, photo, caption=text, components=markup)
    else:
        sent_message = await client.send_message(CHANNEL_ID, text, components=markup)

    cursor.execute("UPDATE ads SET channel_message_id = ? WHERE id = ?", (sent_message.message_id, ad_id))
    conn.commit()
    conn.close()


async def republish_ad_after_edit(ad_id: int):
    """پیام قدیمی کانال رو پاک می‌کند و نسخه جدید را می‌فرستد."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_message_id FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        try:
            await client.delete_message(CHANNEL_ID, row[0])
        except Exception as e:
            print(f"خطا در حذف پیام قدیمی کانال: {e}")

    await post_ad_to_channel(ad_id)


async def update_ad_field(ad_id: int, field: str, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE ads SET {field} = ? WHERE id = ?", (value, ad_id))
    conn.commit()
    conn.close()
    await republish_ad_after_edit(ad_id)


# ---------- لیست آگهی‌ها ----------
async def send_ads_list(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, event_time FROM ads ORDER BY id DESC")
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await client.send_message(user_id, "هنوز هیچ آگهی‌ای ثبت نشده است.")
        return

    for ad_id, title, event_time in ads:
        jalali_display = to_jalali_display(event_time)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"editad|{ad_id}"))
        markup.add(InlineKeyboardButton(text="🗑 حذف", callback_data=f"delad|{ad_id}"))
        text = f"📌 {title}\n🕒 {jalali_display}"
        await client.send_message(user_id, text, components=markup)


# ---------- callback ها ----------
@client.event
async def on_callback(callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data.startswith("checkjoin_"):
        payload = data.split("checkjoin_", 1)[1]
        if await is_user_member(user_id):
            await handle_start_payload(user_id, payload)
        else:
            await client.send_message(user_id, "هنوز عضو کانال نشده‌اید. لطفاً ابتدا عضو شوید.")
        return

    if user_id != ADMIN_ID:
        return  # فقط ادمین اجازه مدیریت آگهی داره

    if data.startswith("editad|"):
        ad_id = int(data.split("|")[1])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="عنوان", callback_data=f"ef|title|{ad_id}"))
        markup.add(InlineKeyboardButton(text="توضیحات", callback_data=f"ef|description|{ad_id}"))
        markup.add(InlineKeyboardButton(text="تاریخ و ساعت", callback_data=f"ef|date|{ad_id}"))
        markup.add(InlineKeyboardButton(text="بنر", callback_data=f"ef|banner|{ad_id}"))
        await client.send_message(user_id, "کدام بخش را می‌خواهید ویرایش کنید؟", components=markup)
        return

    if data.startswith("ef|"):
        _, field, ad_id_str = data.split("|")
        ad_id = int(ad_id_str)
        admin_states[user_id] = {"mode": "editfield", "field": field, "ad_id": ad_id}

        if field == "banner":
            await client.send_message(user_id, "بنر جدید را بفرستید، یا از دکمه زیر رد کنید:", components=build_skip_menu())
            return

        prompts = {
            "title": "عنوان جدید را بفرستید:",
            "description": "توضیحات جدید را بفرستید:",
            "date": "تاریخ جدید را بفرستید (فرمت: 1404/05/10):",
        }
        await client.send_message(user_id, prompts[field])
        return

    if data.startswith("delad|"):
        ad_id = int(data.split("|")[1])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="بله، حذف کن ❌", callback_data=f"delconfirm|{ad_id}"))
        markup.add(InlineKeyboardButton(text="انصراف", callback_data=f"delcancel|{ad_id}"))
        await client.send_message(user_id, "آیا از حذف این آگهی مطمئن هستید؟", components=markup)
        return

    if data.startswith("delconfirm|"):
        ad_id = int(data.split("|")[1])

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT channel_message_id FROM ads WHERE id = ?", (ad_id,))
        row = cursor.fetchone()

        if row and row[0]:
            try:
                await client.delete_message(CHANNEL_ID, row[0])
            except Exception as e:
                print(f"خطا در حذف پیام کانال: {e}")

        cursor.execute("DELETE FROM reminders WHERE ad_id = ?", (ad_id,))
        cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        conn.commit()
        conn.close()

        await client.send_message(user_id, "آگهی با موفقیت حذف شد ✅")
        return

    if data.startswith("delcancel|"):
        await client.send_message(user_id, "حذف لغو شد.")
        return


# ---------- یادآوری‌ها ----------
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
    now = datetime.now()
    event_time_display = to_jalali_display(event_time_str)

    if event_time <= now:
        conn.close()
        await client.send_message(
            user_id,
            f"⛔ زمان رویداد «{title}» ({event_time_display}) گذشته است و امکان ثبت یادآوری برای آن وجود ندارد."
        )
        return

    remind_at = event_time - timedelta(minutes=30)

    if remind_at <= now:
        minutes_left = int((event_time - now).total_seconds() // 60)
        try:
            cursor.execute(
                "INSERT INTO reminders (ad_id, user_id, remind_at, sent) VALUES (?, ?, ?, 1)",
                (ad_id, user_id, remind_at.strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            already_registered = False
        except sqlite3.IntegrityError:
            already_registered = True
        conn.close()

        if already_registered:
            text = f"شما قبلاً برای رویداد «{title}» یادآوری ثبت کرده‌اید. ✅"
        else:
            text = f"⏰ توجه!\n\n📌 رویداد: {title}\n🕒 زمان: {event_time_display}\n\nکمتر از {minutes_left} دقیقه به شروع باقی مانده است."
        await client.send_message(user_id, text)
        return

    try:
        cursor.execute(
            "INSERT INTO reminders (ad_id, user_id, remind_at) VALUES (?, ?, ?)",
            (ad_id, user_id, remind_at.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        already_registered = False
    except sqlite3.IntegrityError:
        already_registered = True
    conn.close()

    if already_registered:
        text = f"شما قبلاً برای رویداد «{title}» یادآوری ثبت کرده‌اید. ✅"
    else:
        text = (
            f"✅ یادآوری شما با موفقیت ثبت شد!\n\n"
            f"📌 رویداد: {title}\n🕒 زمان برگزاری: {event_time_display}\n\n"
            f"نیم ساعت قبل از شروع، پیامی از طرف ربات دریافت خواهید کرد."
        )
    await client.send_message(user_id, text)


async def handle_start_payload(user_id: int, payload: str):
    if payload.startswith("remind_"):
        ad_id = int(payload.split("remind_")[1])
        await handle_reminder_request(ad_id, user_id)
    else:
        await client.send_message(user_id, "سلام! به ربات خوش آمدید 🌿")


async def reminder_loop():
    while True:
        await asyncio.sleep(60)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reminders.id, reminders.user_id, ads.title, ads.event_time FROM reminders "
            "JOIN ads ON reminders.ad_id = ads.id "
            "WHERE reminders.sent = 0 AND reminders.remind_at <= ?",
            (now_str,)
        )
        due_reminders = cursor.fetchall()

        for reminder_id, user_id, ad_title, ad_event_time in due_reminders:
            try:
                event_time_display = to_jalali_display(ad_event_time)
                await client.send_message(
                    user_id,
                    f"⏰ یادآوری رویداد!\n\n📌 «{ad_title}»\n🕒 زمان: {event_time_display}\n\nنیم ساعت دیگر این رویداد آغاز می‌شود."
                )
                cursor.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
                conn.commit()
            except Exception as e:
                print(f"خطا در ارسال یادآوری به {user_id}: {e}")

        conn.close()


# ---------- عضویت ----------
async def is_user_member(user_id: int) -> bool:
    try:
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        if member is None:
            return False
        return member.status not in ("left", "kicked")
    except BaleError:
        return False
    except Exception:
        return False


async def send_join_required(user_id: int, pending_action: str):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="عضویت در کانال 📢", url=f"https://ble.ir/{CHANNEL_USERNAME}"))
    markup.add(InlineKeyboardButton(text="بررسی مجدد ✅", callback_data=f"checkjoin_{pending_action}"))
    await client.send_message(
        user_id,
        "برای استفاده از ربات، ابتدا باید عضو کانال شوید. پس از عضویت، روی دکمه «بررسی مجدد» بزنید.",
        components=markup
    )



client.run()