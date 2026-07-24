import os
import asyncio
from bale import Bot

client = Bot(token=os.environ["BOT_TOKEN"])

CHANNEL_ID = 6191660398
YOUR_USER_ID = 1924418661

async def main():
    async with client:
        await client.get_me()  # جایگزین connect() برای فقط باز کردن session و تایید توکن
        try:
            member = await client.get_chat_member(CHANNEL_ID, YOUR_USER_ID)
            print("member object:", member)
            print("to_dict:", member.to_dict() if member else None)
            print("status:", member.status if member else None)
            print("is_member:", member.is_member if member else None)
            print("is_admin:", member.is_admin if member else None)
            print("is_owner:", member.is_owner if member else None)
        except Exception as e:
            print("EXCEPTION:", type(e), e)

asyncio.run(main())