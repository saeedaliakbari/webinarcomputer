import os
import sqlite3
import asyncio
from datetime import datetime
from bale import Bot, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import jdatetime

client = Bot(token=os.environ["BOT_TOKEN"])
BOT_USERNAME = "webinarcomputerbot"
CHANNEL_ID = 4863203707
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "bot_database.db")
MAX_MESSAGE_LENGTH = 3900


def get_db():
    return sqlite3.connect(DB_PATH)


def to_jalali_display(gregorian_str: str) -> str:
    gregorian_dt = datetime.strptime(gregorian_str, "%Y-%m-%d %H:%M:%S")
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=gregorian_dt)
    return jalali_dt.strftime("%Y/%m/%d - %H:%M")


from urllib.parse import quote
from datetime import timedelta

IRAN_UTC_OFFSET = timedelta(hours=3, minutes=30)

CALENDAR_DESCRIPTION_MAX_LEN = 150

def build_google_calendar_link(title: str, description: str, start_dt: datetime, duration_minutes: int = 60) -> str:
    short_description = description[:CALENDAR_DESCRIPTION_MAX_LEN]
    if len(description) > CALENDAR_DESCRIPTION_MAX_LEN:
        short_description = short_description.rstrip() + "…"

    start_utc = start_dt - IRAN_UTC_OFFSET
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")
    end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": short_description,
    }
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"


def calculate_message_length(title, description, session_count):
    header = f"📢 {title}\n\n"
    footer_sample = "\n\n🕒 جلسات:\n" + "\n".join(["1️⃣ 1405/05/05 - 18:00"] * session_count)
    return len(header) + len(description) + len(footer_sample)


async def post_ad_to_channel(ad_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, description, photo_file_id FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return
    title, description, photo_file_id = row

    cursor.execute("SELECT id, session_time, video_link FROM ad_sessions WHERE ad_id = ? ORDER BY session_time ASC", (ad_id,))
    sessions = cursor.fetchall()
    conn.close()

    session_lines = []
    markup = InlineKeyboardMarkup()
    row_num = 1

    if len(sessions) > 1:
        markup.add(InlineKeyboardButton(text="🔔 یادآوری همه جلسات", url=f"https://ble.ir/{BOT_USERNAME}?start=remind_all_{ad_id}"), row=row_num)
        row_num += 1

    numerals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, (session_id, session_time, video_link) in enumerate(sessions):
        display = to_jalali_display(session_time)
        emoji = numerals[idx] if idx < len(numerals) else f"{idx+1}."
        session_lines.append(f"{emoji} {display}")

        label = f"🔔 یادآوری جلسه {idx+1}" if len(sessions) > 1 else "🔔 یادآوری بگیر"
        markup.add(InlineKeyboardButton(text=label, url=f"https://ble.ir/{BOT_USERNAME}?start=remind_sess_{session_id}"), row=row_num)
        row_num += 1

        if video_link:
            video_label = f"🎥 ویدیوی جلسه {idx+1}" if len(sessions) > 1 else "🎥 مشاهده ویدیو"
            markup.add(InlineKeyboardButton(text=video_label, url=video_link), row=row_num)
            row_num += 1

        session_dt = datetime.strptime(session_time, "%Y-%m-%d %H:%M:%S")
        calendar_link = build_google_calendar_link(title, description, session_dt)
        calendar_label = f"📅 افزودن جلسه {idx+1} به تقویم" if len(sessions) > 1 else "📅 افزودن به تقویم گوگل"
        markup.add(InlineKeyboardButton(text=calendar_label, url=calendar_link), row=row_num)
        row_num += 1

    sessions_text = "\n".join(session_lines)
    header = f"📢 {title}\n\n"
    footer = f"\n\n🕒 جلسات:\n{sessions_text}"
    max_description_len = MAX_MESSAGE_LENGTH - len(header) - len(footer) - 20

    safe_description = description
    if len(safe_description) > max_description_len:
        safe_description = safe_description[:max_description_len].rstrip() + "…"

    text = f"{header}{safe_description}{footer}"

    photo_message_id = None
    if photo_file_id:
        photo = InputFile(photo_file_id)
        photo_message = await client.send_photo(CHANNEL_ID, photo)
        photo_message_id = photo_message.message_id

    try:
        sent_message = await client.send_message(CHANNEL_ID, text, components=markup)
    except Exception as e:
        if photo_message_id:
            try:
                await client.delete_message(CHANNEL_ID, photo_message_id)
            except Exception:
                pass
        raise e

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE ads SET channel_message_id = ?, channel_photo_message_id = ? WHERE id = ?", (sent_message.message_id, photo_message_id, ad_id))
    conn.commit()
    conn.close()


async def republish_ad(ad_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_message_id, channel_photo_message_id FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    conn.close()

    old_text_id = row[0] if row else None
    old_photo_id = row[1] if row else None

    await post_ad_to_channel(ad_id)

    if old_text_id:
        try:
            await client.delete_message(CHANNEL_ID, old_text_id)
        except Exception as e:
            print(f"  حذف پیام متن قدیمی fail شد: {e}")
    if old_photo_id:
        try:
            await client.delete_message(CHANNEL_ID, old_photo_id)
        except Exception as e:
            print(f"  حذف پیام عکس قدیمی fail شد: {e}")


async def main():
    async with client:
        await client.get_me()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description FROM ads")
        ads = cursor.fetchall()

        print(f"بررسی {len(ads)} آگهی...\n")

        long_ads = []
        for ad_id, title, description in ads:
            cursor.execute("SELECT COUNT(*) FROM ad_sessions WHERE ad_id = ?", (ad_id,))
            session_count = cursor.fetchone()[0]
            length = calculate_message_length(title, description, session_count)
            if length > MAX_MESSAGE_LENGTH:
                long_ads.append((ad_id, title, length))
                print(f"⚠️  آگهی #{ad_id} «{title}» — طول تخمینی: {length} (بیش از حد مجاز)")

        conn.close()

        if not long_ads:
            print("هیچ آگهی طولانی‌ای پیدا نشد. نیازی به اصلاح نیست.")
            return

        print(f"\n{len(long_ads)} آگهی طولانی پیدا شد. شروع اصلاح خودکار...\n")

        fixed, failed = [], []
        for ad_id, title, length in long_ads:
            try:
                await republish_ad(ad_id)
                fixed.append((ad_id, title))
                print(f"✅ آگهی #{ad_id} «{title}» با موفقیت اصلاح شد.")
            except Exception as e:
                failed.append((ad_id, title, str(e)))
                print(f"❌ آگهی #{ad_id} «{title}» ناموفق: {e}")
            await asyncio.sleep(2)

        print(f"\n--- خلاصه ---")
        print(f"اصلاح‌شده: {len(fixed)}")
        print(f"ناموفق: {len(failed)}")


asyncio.run(main())