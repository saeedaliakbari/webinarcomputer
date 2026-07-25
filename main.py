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
BOT_USERNAME = "webinarcomputerbot"
ADMIN_ID = 1924418661
# CHANNEL_USERNAME = "testnotif"
# CHANNEL_ID = 6191660398
CHANNEL_USERNAME = "computer_webinar"
CHANNEL_ID = 4863203707

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "bot_database.db")

admin_states = {}

# ---------- دکمه‌ها ----------
BTN_NEW_AD = "➕ ثبت آگهی جدید"
BTN_LIST_ADS = "📋 لیست آگهی‌ها"
BTN_BACK_TO_USER_MENU = "🔙 بازگشت به منوی کاربری"
BTN_PROFILE = "👤 پروفایل من"
BTN_MY_REMINDERS = "🔔 یادآوری‌های من"
BTN_PAST_EVENTS = "📅 رویدادهای گذشته"
BTN_HELP = "ℹ️ راهنما"
SKIP_TEXT = "⏭ رد کردن (بدون بنر)"
BTN_ADD_SESSION = "➕ افزودن جلسه دیگر"
BTN_FINISH_SESSIONS = "✅ پایان و ثبت آگهی"
ADMIN_PANEL_COMMAND = "مدیریت"
BTN_SUBMIT_EVENT = "📝 ثبت رویداد"
BTN_PENDING_EVENTS = "📥 درخواست‌های رویداد"

def build_admin_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=BTN_NEW_AD), row=1)
    markup.add(MenuKeyboardButton(text=BTN_LIST_ADS), row=1)
    markup.add(MenuKeyboardButton(text=BTN_PENDING_EVENTS), row=2)
    markup.add(MenuKeyboardButton(text=BTN_BACK_TO_USER_MENU), row=3)
    return markup

def build_user_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=BTN_PROFILE), row=1)
    markup.add(MenuKeyboardButton(text=BTN_MY_REMINDERS), row=1)
    markup.add(MenuKeyboardButton(text=BTN_PAST_EVENTS), row=2)
    markup.add(MenuKeyboardButton(text=BTN_SUBMIT_EVENT), row=2)
    markup.add(MenuKeyboardButton(text=BTN_HELP), row=3)
    return markup

def build_skip_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=SKIP_TEXT), row=1)
    return markup

def build_session_decision_menu():
    markup = MenuKeyboardMarkup()
    markup.add(MenuKeyboardButton(text=BTN_ADD_SESSION), row=1)
    markup.add(MenuKeyboardButton(text=BTN_FINISH_SESSIONS), row=1)
    return markup


def get_db():
    return sqlite3.connect(DB_PATH)

def to_jalali_display(gregorian_str: str) -> str:
    gregorian_dt = datetime.strptime(gregorian_str, "%Y-%m-%d %H:%M:%S")
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=gregorian_dt)
    return jalali_dt.strftime("%Y/%m/%d - %H:%M")

def parse_jalali_date(text: str):
    text = text.strip()
    if len(text) != 8 or not text.isdigit():
        raise ValueError("invalid format")
    return jdatetime.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))

def parse_time(text: str):
    text = text.strip()
    if len(text) != 4 or not text.isdigit():
        raise ValueError("invalid format")
    hour, minute = int(text[0:2]), int(text[2:4])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("invalid time")
    return hour, minute

def format_remaining(event_time: datetime) -> str:
    diff = event_time - datetime.now()
    total_seconds = int(diff.total_seconds())
    if total_seconds <= 0:
        return "به زودی"
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes and not days:
        parts.append(f"{minutes} دقیقه")
    return (" و ".join(parts) + " مانده") if parts else "کمتر از یک دقیقه مانده"


# ================= ready =================
@client.event
async def on_ready():
    print(client.user, "آماده است")
    asyncio.create_task(reminder_loop())


# ================= پیام‌ها =================
@client.event
async def on_message(message: Message):
    if message.from_user is None:
        return

    user_id = message.from_user.id
    content = (message.content or "").strip()

    # ---- شروع ----
    if content.startswith("/start"):
        parts = content.split(" ", 1)
        payload = parts[1] if len(parts) > 1 else "none"
        if not await is_user_member(user_id):
            await send_join_required(user_id, payload)
            return
        await handle_start_payload(user_id, payload)
        await message.reply("از منوی زیر استفاده کنید:", components=build_user_menu())
        return

    # ---- ورود ادمین به پنل مدیریت ----
    if content == ADMIN_PANEL_COMMAND and user_id == ADMIN_ID:
        await message.reply("🔧 وارد پنل مدیریت شدید.", components=build_admin_menu())
        return

    # ---- ادامه‌ی مکالمه‌ی جاری (چه ادمین چه کاربر عادی) ----
    if user_id in admin_states:
        await handle_admin_conversation(message, admin_states[user_id])
        return

    # ---- دکمه ثبت رویداد (کاربر عادی) ----
    if content == BTN_SUBMIT_EVENT:
        admin_states[user_id] = {"mode": "submitevent", "step": "title", "data": {"sessions": []}}
        await message.reply("عنوان رویداد پیشنهادی رو بفرست:")
        return

    # ---- دکمه‌های منوی کاربر ----
    if content == BTN_PROFILE:
        await send_profile(message)
        return
    if content == BTN_MY_REMINDERS:
        await send_my_reminders(user_id)
        return
    if content == BTN_PAST_EVENTS:
        await send_past_events(user_id)
        return
    if content == BTN_HELP:
        await message.reply("این ربات برای دریافت یادآوری رویدادهای کانال است. کافیست روی دکمه یادآوری زیر هر آگهی در کانال بزنید.")
        return

    # ---- از اینجا فقط ادمین ----
    if user_id != ADMIN_ID:
        return

    if content == BTN_BACK_TO_USER_MENU:
        await message.reply("بازگشت به منوی کاربری:", components=build_user_menu())
        return
    if content == BTN_NEW_AD:
        admin_states[user_id] = {"mode": "newad", "step": "title", "data": {"sessions": []}}
        await message.reply("عنوان رویداد رو بفرست:")
        return
    if content == BTN_LIST_ADS:
        await send_ads_list(user_id)
        return
    if content == BTN_PENDING_EVENTS:
        await send_pending_events(user_id)
        return

async def handle_admin_conversation(message: Message, state: dict):
    user_id = message.from_user.id
    content = (message.content or "").strip()
    mode = state["mode"]

    # ===================== ثبت آگهی جدید (چند جلسه‌ای) =====================
    if mode == "newad":
        step = state["step"]

        if step == "title":
            state["data"]["title"] = content
            state["step"] = "description"
            await message.reply("توضیحات رویداد رو بفرست:")

        elif step == "description":
            state["data"]["description"] = content
            state["step"] = "session_date"
            await message.reply(f"تاریخ جلسه {len(state['data']['sessions']) + 1} رو بفرست (فرمت: 14050503):")

        elif step == "session_date":
            try:
                jalali_date = parse_jalali_date(content)
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 14050503):")
                return
            state["_pending_date"] = jalali_date
            state["step"] = "session_time"
            await message.reply("ساعت این جلسه رو بفرست (فرمت: 1730):")

        elif step == "session_time":
            try:
                hour, minute = parse_time(content)
                jalali_date = state["_pending_date"]
                jalali_dt = jdatetime.datetime(jalali_date.year, jalali_date.month, jalali_date.day, hour, minute)
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت ساعت اشتباهه. دوباره امتحان کن (مثال: 1730):")
                return

            state["data"]["sessions"].append(gregorian_dt.strftime("%Y-%m-%d %H:%M:%S"))
            state["step"] = "session_decision"
            await message.reply(
                f"جلسه {len(state['data']['sessions'])} ثبت شد ✅\n"
                f"اگه جلسه دیگه‌ای داری اضافه کن، وگرنه پایان بده:",
                components=build_session_decision_menu()
            )

        elif step == "session_decision":
            if content == BTN_ADD_SESSION:
                state["step"] = "session_date"
                await message.reply(f"تاریخ جلسه {len(state['data']['sessions']) + 1} رو بفرست (فرمت: 14050503):")
            elif content == BTN_FINISH_SESSIONS:
                state["step"] = "banner"
                await message.reply("اگه بنر داری بفرست، یا از دکمه زیر رد کن:", components=build_skip_menu())
            else:
                await message.reply("لطفاً از دکمه‌های زیر استفاده کن:", components=build_session_decision_menu())

        elif step == "banner":
            if content == SKIP_TEXT or content == "/skip":
                state["data"]["photo_file_id"] = None
            elif message.photos:
                state["data"]["photo_file_id"] = message.photos[-1].file_id
            else:
                await message.reply("لطفاً یک عکس بفرست یا از دکمه رد کردن استفاده کن:", components=build_skip_menu())
                return

            await finalize_ad(state["data"])
            await client.send_message(user_id, "بازگشت به منو:", components=build_admin_menu())
            del admin_states[user_id]

    # ===================== ویرایش جلسات (جایگزینی کامل) =====================
    elif mode == "editsessions":
        step = state["step"]

        if step == "session_date":
            try:
                jalali_date = parse_jalali_date(content)
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 14050503):")
                return
            state["_pending_date"] = jalali_date
            state["step"] = "session_time"
            await message.reply("ساعت این جلسه رو بفرست (فرمت: 1730):")

        elif step == "session_time":
            try:
                hour, minute = parse_time(content)
                jalali_date = state["_pending_date"]
                jalali_dt = jdatetime.datetime(jalali_date.year, jalali_date.month, jalali_date.day, hour, minute)
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت ساعت اشتباهه. دوباره امتحان کن (مثال: 1730):")
                return

            state["sessions"].append(gregorian_dt.strftime("%Y-%m-%d %H:%M:%S"))
            state["step"] = "session_decision"
            await message.reply(
                f"جلسه {len(state['sessions'])} ثبت شد ✅",
                components=build_session_decision_menu()
            )

        elif step == "session_decision":
            if content == BTN_ADD_SESSION:
                state["step"] = "session_date"
                await message.reply(f"تاریخ جلسه {len(state['sessions']) + 1} رو بفرست (فرمت: 14050503):")
            elif content == BTN_FINISH_SESSIONS:
                await replace_ad_sessions(state["ad_id"], state["sessions"])
                await client.send_message(user_id, "جلسات با موفقیت به‌روزرسانی شد ✅", components=build_admin_menu())
                del admin_states[user_id]
            else:
                await message.reply("لطفاً از دکمه‌های زیر استفاده کن:", components=build_session_decision_menu())

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
    # ===================== تایید اگهی=====================
    elif mode == "submitevent":
        step = state["step"]

        if step == "title":
            state["data"]["title"] = content
            state["step"] = "description"
            await message.reply("توضیحات رویداد رو بفرست:")

        elif step == "description":
            state["data"]["description"] = content
            state["step"] = "session_date"
            await message.reply(f"تاریخ جلسه {len(state['data']['sessions']) + 1} رو بفرست (فرمت: 14050503):")

        elif step == "session_date":
            try:
                jalali_date = parse_jalali_date(content)
            except ValueError:
                await message.reply("فرمت تاریخ اشتباهه. دوباره امتحان کن (مثال: 14050503):")
                return
            state["_pending_date"] = jalali_date
            state["step"] = "session_time"
            await message.reply("ساعت این جلسه رو بفرست (فرمت: 1730):")

        elif step == "session_time":
            try:
                hour, minute = parse_time(content)
                jalali_date = state["_pending_date"]
                jalali_dt = jdatetime.datetime(jalali_date.year, jalali_date.month, jalali_date.day, hour, minute)
                gregorian_dt = jalali_dt.togregorian()
            except ValueError:
                await message.reply("فرمت ساعت اشتباهه. دوباره امتحان کن (مثال: 1730):")
                return

            state["data"]["sessions"].append(gregorian_dt.strftime("%Y-%m-%d %H:%M:%S"))
            state["step"] = "session_decision"
            await message.reply(
                f"جلسه {len(state['data']['sessions'])} ثبت شد ✅\nاگه جلسه دیگه‌ای داری اضافه کن، وگرنه پایان بده:",
                components=build_session_decision_menu()
            )

        elif step == "session_decision":
            if content == BTN_ADD_SESSION:
                state["step"] = "session_date"
                await message.reply(f"تاریخ جلسه {len(state['data']['sessions']) + 1} رو بفرست (فرمت: 14050503):")
            elif content == BTN_FINISH_SESSIONS:
                state["step"] = "banner"
                await message.reply("اگه بنر داری بفرست، یا از دکمه زیر رد کن:", components=build_skip_menu())
            else:
                await message.reply("لطفاً از دکمه‌های زیر استفاده کن:", components=build_session_decision_menu())

        elif step == "banner":
            if content == SKIP_TEXT or content == "/skip":
                state["data"]["photo_file_id"] = None
            elif message.photos:
                state["data"]["photo_file_id"] = message.photos[-1].file_id
            else:
                await message.reply("لطفاً یک عکس بفرست یا از دکمه رد کردن استفاده کن:", components=build_skip_menu())
                return

            await submit_pending_event(user_id, state["data"])
            await client.send_message(user_id, "بازگشت به منو:", components=build_user_menu())
            del admin_states[user_id]

    # ===================== رد کردن با دلیل (ادمین) =====================
    elif mode == "rejectreason":
        await reject_pending_event(state["pending_id"], content)
        await message.reply("رویداد رد شد و به کاربر اطلاع داده شد.", components=build_admin_menu())
        del admin_states[user_id]
# ================= ثبت نهایی آگهی جدید =================
async def finalize_ad(data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ads (title, description, photo_file_id) VALUES (?, ?, ?)",
        (data["title"], data["description"], data.get("photo_file_id"))
    )
    ad_id = cursor.lastrowid

    for session_time in data["sessions"]:
        cursor.execute(
            "INSERT INTO ad_sessions (ad_id, session_time) VALUES (?, ?)",
            (ad_id, session_time)
        )

    conn.commit()
    conn.close()

    await post_ad_to_channel(ad_id)
    await client.send_message(ADMIN_ID, "✅ آگهی با موفقیت در کانال ثبت و ارسال شد.")


async def replace_ad_sessions(ad_id: int, sessions: list):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ad_sessions WHERE ad_id = ?", (ad_id,))
    old_session_ids = [r[0] for r in cursor.fetchall()]
    for sid in old_session_ids:
        cursor.execute("DELETE FROM reminders WHERE session_id = ?", (sid,))
    cursor.execute("DELETE FROM ad_sessions WHERE ad_id = ?", (ad_id,))
    for session_time in sessions:
        cursor.execute("INSERT INTO ad_sessions (ad_id, session_time) VALUES (?, ?)", (ad_id, session_time))
    conn.commit()
    conn.close()
    await republish_ad_after_edit(ad_id)


# ================= ارسال/بازارسال آگهی به کانال =================
async def post_ad_to_channel(ad_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, description, photo_file_id FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return
    title, description, photo_file_id = row

    cursor.execute("SELECT id, session_time FROM ad_sessions WHERE ad_id = ? ORDER BY session_time ASC", (ad_id,))
    sessions = cursor.fetchall()
    conn.close()

    session_lines = []
    markup = InlineKeyboardMarkup()
    row_num = 1

    if len(sessions) > 1:
        markup.add(InlineKeyboardButton(
            text="🔔 یادآوری همه جلسات",
            url=f"https://ble.ir/{BOT_USERNAME}?start=remind_all_{ad_id}"
        ),row=row_num)
        row_num+=1

    numerals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, (session_id, session_time) in enumerate(sessions):
        display = to_jalali_display(session_time)
        emoji = numerals[idx] if idx < len(numerals) else f"{idx+1}."
        session_lines.append(f"{emoji} {display}")

        label = f"🔔 یادآوری جلسه {idx+1}" if len(sessions) > 1 else "🔔 یادآوری بگیر"
        markup.add(InlineKeyboardButton(
            text=label,
            url=f"https://ble.ir/{BOT_USERNAME}?start=remind_sess_{session_id}"
        ),row=row_num)
        row_num+=1

    sessions_text = "\n".join(session_lines)
    text = f"📢 {title}\n\n{description}\n\n🕒 جلسات:\n{sessions_text}"

    if photo_file_id:
        photo = InputFile(photo_file_id)
        sent_message = await client.send_photo(CHANNEL_ID, photo, caption=text, components=markup)
    else:
        sent_message = await client.send_message(CHANNEL_ID, text, components=markup)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE ads SET channel_message_id = ? WHERE id = ?", (sent_message.message_id, ad_id))
    conn.commit()
    conn.close()


async def republish_ad_after_edit(ad_id: int):
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


# ================= لیست آگهی‌ها =================
async def send_ads_list(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM ads ORDER BY id DESC")
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await client.send_message(user_id, "هنوز هیچ آگهی‌ای ثبت نشده است.")
        return

    for ad_id, title in ads:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"editad|{ad_id}"))
        markup.add(InlineKeyboardButton(text="🗑 حذف", callback_data=f"delad|{ad_id}"))
        await client.send_message(user_id, f"📌 {title}", components=markup)


# ================= callback ها =================
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

    # ---- لغو یک یادآوری ----
    if data.startswith("cancelrem|"):
        reminder_id = int(data.split("|")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
        conn.commit()
        conn.close()
        await client.send_message(user_id, "یادآوری لغو شد ✅")
        return

    if data == "cancelallrem":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="بله، لغو کن", callback_data="cancelallrem_confirm"))
        markup.add(InlineKeyboardButton(text="انصراف", callback_data="cancelallrem_cancel"))
        await client.send_message(user_id, "آیا مطمئن هستید می‌خواهید همه‌ی یادآوری‌های فعال را لغو کنید؟", components=markup)
        return

    if data == "cancelallrem_confirm":
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reminders WHERE user_id = ? AND session_id IN "
            "(SELECT id FROM ad_sessions WHERE session_time > ?)",
            (user_id, now_str)
        )
        conn.commit()
        conn.close()
        await client.send_message(user_id, "همه‌ی یادآوری‌های فعال شما لغو شد ✅")
        return

    if data == "cancelallrem_cancel":
        await client.send_message(user_id, "لغو انجام نشد.")
        return

    # ---- از اینجا فقط ادمین ----
    if user_id != ADMIN_ID:
        return

    if data.startswith("editad|"):
        ad_id = int(data.split("|")[1])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="عنوان", callback_data=f"ef|title|{ad_id}"))
        markup.add(InlineKeyboardButton(text="توضیحات", callback_data=f"ef|description|{ad_id}"))
        markup.add(InlineKeyboardButton(text="جلسات (تاریخ/ساعت)", callback_data=f"ef|sessions|{ad_id}"))
        markup.add(InlineKeyboardButton(text="بنر", callback_data=f"ef|banner|{ad_id}"))
        await client.send_message(user_id, "کدام بخش را می‌خواهید ویرایش کنید؟", components=markup)
        return

    if data.startswith("ef|"):
        _, field, ad_id_str = data.split("|")
        ad_id = int(ad_id_str)

        if field == "sessions":
            admin_states[user_id] = {"mode": "editsessions", "ad_id": ad_id, "sessions": [], "step": "session_date"}
            await client.send_message(user_id, "جلسات قبلی حذف و جلسات جدید جایگزین می‌شود.\nتاریخ جلسه ۱ را بفرستید (فرمت: 14050503):")
            return

        admin_states[user_id] = {"mode": "editfield", "field": field, "ad_id": ad_id}

        if field == "banner":
            await client.send_message(user_id, "بنر جدید را بفرستید، یا از دکمه زیر رد کنید:", components=build_skip_menu())
            return

        prompts = {
            "title": "عنوان جدید را بفرستید:",
            "description": "توضیحات جدید را بفرستید:",
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

        cursor.execute("SELECT id FROM ad_sessions WHERE ad_id = ?", (ad_id,))
        session_ids = [r[0] for r in cursor.fetchall()]
        for sid in session_ids:
            cursor.execute("DELETE FROM reminders WHERE session_id = ?", (sid,))
        cursor.execute("DELETE FROM ad_sessions WHERE ad_id = ?", (ad_id,))
        cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        conn.commit()
        conn.close()

        await client.send_message(user_id, "آگهی با موفقیت حذف شد ✅")
        return

    if data.startswith("delcancel|"):
        await client.send_message(user_id, "حذف لغو شد.")
        return

    if data.startswith("pendapprove|"):
        pending_id = int(data.split("|")[1])
        await approve_pending_event(pending_id)
        await client.send_message(user_id, "رویداد تایید و منتشر شد ✅")
        return

    if data.startswith("pendreject|"):
        pending_id = int(data.split("|")[1])
        admin_states[user_id] = {"mode": "rejectreason", "pending_id": pending_id}
        await client.send_message(user_id, "دلیل رد کردن رو بنویس (یا برای رد بدون دلیل بنویس /skip):")
        return


# ================= یادآوری‌ها (بر پایه جلسه) =================
async def register_session_reminder(session_id: int, user_id: int):
    """خروجی: (status, title, session_time_str) - status یکی از: not_found, past, near, registered, already"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ads.title, ad_sessions.session_time FROM ad_sessions "
        "JOIN ads ON ad_sessions.ad_id = ads.id WHERE ad_sessions.id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return "not_found", None, None

    title, session_time_str = row
    session_time = datetime.strptime(session_time_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()

    if session_time <= now:
        conn.close()
        return "past", title, session_time_str

    remind_at = session_time - timedelta(minutes=30)
    sent_flag = 1 if remind_at <= now else 0

    try:
        cursor.execute(
            "INSERT INTO reminders (session_id, user_id, remind_at, sent) VALUES (?, ?, ?, ?)",
            (session_id, user_id, remind_at.strftime("%Y-%m-%d %H:%M:%S"), sent_flag)
        )
        conn.commit()
        status = "near" if sent_flag else "registered"
    except sqlite3.IntegrityError:
        status = "already"

    conn.close()
    return status, title, session_time_str


async def handle_single_session_click(session_id: int, user_id: int):
    status, title, session_time_str = await register_session_reminder(session_id, user_id)

    if status == "not_found":
        await client.send_message(user_id, "این جلسه دیگر معتبر نیست.")
        return

    display = to_jalali_display(session_time_str)

    if status == "past":
        await client.send_message(user_id, f"⛔ زمان جلسه «{title}» ({display}) گذشته است و امکان ثبت یادآوری وجود ندارد.")
    elif status == "already":
        await client.send_message(user_id, f"شما قبلاً برای «{title}» ({display}) یادآوری ثبت کرده‌اید. ✅")
    elif status == "near":
        session_time = datetime.strptime(session_time_str, "%Y-%m-%d %H:%M:%S")
        minutes_left = int((session_time - datetime.now()).total_seconds() // 60)
        await client.send_message(
            user_id,
            f"⏰ توجه!\n\n📌 {title}\n🕒 {display}\n\nکمتر از {minutes_left} دقیقه به شروع باقی مانده است."
        )
    else:
        await client.send_message(
            user_id,
            f"✅ یادآوری شما ثبت شد!\n\n📌 {title}\n🕒 {display}\n\nنیم ساعت قبل از شروع، پیامی دریافت خواهید کرد."
        )


async def handle_all_sessions_click(ad_id: int, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        await client.send_message(user_id, "این آگهی دیگر معتبر نیست.")
        return
    title = row[0]

    cursor.execute("SELECT id FROM ad_sessions WHERE ad_id = ? ORDER BY session_time ASC", (ad_id,))
    session_ids = [r[0] for r in cursor.fetchall()]
    conn.close()

    registered, already, past = 0, 0, 0
    for sid in session_ids:
        status, _, _ = await register_session_reminder(sid, user_id)
        if status in ("registered", "near"):
            registered += 1
        elif status == "already":
            already += 1
        elif status == "past":
            past += 1

    text = f"📌 {title}\n\n"
    if registered:
        text += f"✅ یادآوری {registered} جلسه ثبت شد.\n"
    if already:
        text += f"ℹ️ {already} جلسه قبلاً ثبت شده بود.\n"
    if past:
        text += f"⛔ {past} جلسه زمانش گذشته بود.\n"
    await client.send_message(user_id, text)


async def handle_start_payload(user_id: int, payload: str):
    if payload.startswith("remind_sess_"):
        session_id = int(payload.split("remind_sess_")[1])
        await handle_single_session_click(session_id, user_id)
    elif payload.startswith("remind_all_"):
        ad_id = int(payload.split("remind_all_")[1])
        await handle_all_sessions_click(ad_id, user_id)
    else:
        await client.send_message(user_id, "سلام! به ربات خوش آمدید 🌿")


async def reminder_loop():
    while True:
        await asyncio.sleep(60)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reminders.id, reminders.user_id, ads.title, ad_sessions.session_time "
            "FROM reminders "
            "JOIN ad_sessions ON reminders.session_id = ad_sessions.id "
            "JOIN ads ON ad_sessions.ad_id = ads.id "
            "WHERE reminders.sent = 0 AND reminders.remind_at <= ?",
            (now_str,)
        )
        due_reminders = cursor.fetchall()

        for reminder_id, user_id, ad_title, session_time in due_reminders:
            try:
                display = to_jalali_display(session_time)
                await client.send_message(
                    user_id,
                    f"⏰ یادآوری رویداد!\n\n📌 «{ad_title}»\n🕒 {display}\n\nنیم ساعت دیگر این جلسه آغاز می‌شود."
                )
                cursor.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
                conn.commit()
            except Exception as e:
                print(f"خطا در ارسال یادآوری به {user_id}: {e}")

        conn.close()


# ================= پروفایل / یادآوری‌های من / گذشته =================
async def send_profile(message: Message):
    user = message.from_user
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM reminders r JOIN ad_sessions s ON r.session_id = s.id "
        "WHERE r.user_id = ? AND s.session_time > ?",
        (user.id, now_str)
    )
    active_count = cursor.fetchone()[0]
    conn.close()

    username_display = f"@{user.username}" if user.username else "ندارد"
    text = (
        f"👤 پروفایل شما\n\n"
        f"🆔 شناسه عددی: {user.id}\n"
        f"نام کاربری: {username_display}\n"
        f"نام: {user.first_name}\n\n"
        f"🔔 تعداد یادآوری‌های فعال: {active_count}"
    )
    await message.reply(text)


async def send_my_reminders(user_id: int):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT r.id, ads.title, s.session_time FROM reminders r "
        "JOIN ad_sessions s ON r.session_id = s.id "
        "JOIN ads ON s.ad_id = ads.id "
        "WHERE r.user_id = ? AND s.session_time > ? ORDER BY s.session_time ASC",
        (user_id, now_str)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await client.send_message(user_id, "شما در حال حاضر یادآوری فعالی ندارید.")
        return

    for reminder_id, title, session_time_str in rows:
        session_time = datetime.strptime(session_time_str, "%Y-%m-%d %H:%M:%S")
        remaining = format_remaining(session_time)
        display = to_jalali_display(session_time_str)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="❌ لغو یادآوری", callback_data=f"cancelrem|{reminder_id}"))

        text = f"📌 {title}\n🕒 {display}\n⏳ {remaining}"
        await client.send_message(user_id, text, components=markup)

    markup_all = InlineKeyboardMarkup()
    markup_all.add(InlineKeyboardButton(text="🔕 لغو همه یادآوری‌ها", callback_data="cancelallrem"))
    await client.send_message(user_id, "برای لغو همه‌ی یادآوری‌ها:", components=markup_all)


async def send_past_events(user_id: int):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ads.title, s.session_time FROM reminders r "
        "JOIN ad_sessions s ON r.session_id = s.id "
        "JOIN ads ON s.ad_id = ads.id "
        "WHERE r.user_id = ? AND s.session_time <= ? ORDER BY s.session_time DESC LIMIT 25",
        (user_id, now_str)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await client.send_message(user_id, "شما رویداد گذشته‌ای ندارید.")
        return

    lines = [f"📌 {title} — {to_jalali_display(session_time_str)}" for title, session_time_str in rows]
    text = "📅 رویدادهای گذشته‌ی شما:\n\n" + "\n".join(lines)
    await client.send_message(user_id, text)


# ================= عضویت =================
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

async def submit_pending_event(user_id: int, data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pending_events (submitted_by, title, description, photo_file_id) VALUES (?, ?, ?, ?)",
        (user_id, data["title"], data["description"], data.get("photo_file_id"))
    )
    pending_id = cursor.lastrowid
    for session_time in data["sessions"]:
        cursor.execute(
            "INSERT INTO pending_event_sessions (pending_event_id, session_time) VALUES (?, ?)",
            (pending_id, session_time)
        )
    conn.commit()
    conn.close()

    await client.send_message(user_id, "✅ رویداد شما ثبت شد و برای بررسی مدیر ارسال گردید.")
    await client.send_message(ADMIN_ID, f"📥 یک رویداد جدید در انتظار تایید است.\nبرای بررسی، از منوی «{BTN_PENDING_EVENTS}» استفاده کنید.")


async def send_pending_events(admin_user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, submitted_by FROM pending_events ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await client.send_message(admin_user_id, "هیچ رویداد در انتظار تاییدی وجود ندارد.")
        return

    for pid, title, submitted_by in rows:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="✅ تایید و انتشار", callback_data=f"pendapprove|{pid}"), row=1)
        markup.add(InlineKeyboardButton(text="❌ رد کردن", callback_data=f"pendreject|{pid}"), row=2)
        await client.send_message(
            admin_user_id,
            f"📌 {title}\n👤 ثبت‌کننده: {submitted_by}",
            components=markup
        )


async def approve_pending_event(pending_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT submitted_by, title, description, photo_file_id FROM pending_events WHERE id = ?", (pending_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return None

    submitted_by, title, description, photo_file_id = row
    cursor.execute("SELECT session_time FROM pending_event_sessions WHERE pending_event_id = ?", (pending_id,))
    sessions = [r[0] for r in cursor.fetchall()]

    cursor.execute(
        "INSERT INTO ads (title, description, photo_file_id) VALUES (?, ?, ?)",
        (title, description, photo_file_id)
    )
    ad_id = cursor.lastrowid
    for session_time in sessions:
        cursor.execute("INSERT INTO ad_sessions (ad_id, session_time) VALUES (?, ?)", (ad_id, session_time))

    cursor.execute("DELETE FROM pending_event_sessions WHERE pending_event_id = ?", (pending_id,))
    cursor.execute("DELETE FROM pending_events WHERE id = ?", (pending_id,))
    conn.commit()
    conn.close()

    await post_ad_to_channel(ad_id)
    await client.send_message(submitted_by, f"✅ رویداد پیشنهادی شما «{title}» تایید و در کانال منتشر شد.")
    return ad_id


async def reject_pending_event(pending_id: int, reason: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT submitted_by, title FROM pending_events WHERE id = ?", (pending_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return

    submitted_by, title = row
    cursor.execute("DELETE FROM pending_event_sessions WHERE pending_event_id = ?", (pending_id,))
    cursor.execute("DELETE FROM pending_events WHERE id = ?", (pending_id,))
    conn.commit()
    conn.close()

    reason_text = f"\nدلیل: {reason}" if reason and reason != "/skip" else ""
    await client.send_message(submitted_by, f"❌ رویداد پیشنهادی شما «{title}» رد شد.{reason_text}")

client.run()