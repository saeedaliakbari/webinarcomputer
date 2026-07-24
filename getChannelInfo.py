import os
from bale import Bot, Message

client = Bot(token=os.environ["BOT_TOKEN"])

@client.event
async def on_message(message: Message):
    print("chat_id:", message.chat.id, "| type:", message.chat.type, "| title:", getattr(message.chat, "title", None))

client.run()