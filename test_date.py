import jdatetime
from datetime import datetime

# ورودی فرضی که ادمین می‌فرسته
user_input = "1404-05-10 18:00"

try:
    jalali_dt = jdatetime.datetime.strptime(user_input, "%Y-%m-%d %H:%M")
    gregorian_dt = jalali_dt.togregorian()
    print("تاریخ شمسی:", jalali_dt)
    print("تاریخ میلادی:", gregorian_dt)
    print("نوع gregorian_dt:", type(gregorian_dt))
except ValueError as e:
    print("فرمت اشتباه:", e)

# تست مقایسه با زمان الان (چیزی که در scheduler لازم داریم)
now = datetime.now()
print("الان (میلادی):", now)
print("آیا رویداد در آینده است؟", gregorian_dt > now)