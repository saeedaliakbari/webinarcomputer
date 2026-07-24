from balepy import Client, filters

bot = Client("MyBot", os.environ["BOT_TOKEN"])

@bot.on_message(filters.command("start"))
async def start_handler(message):
    await message.reply("سلام! ربات شروع شد 🌿")

@bot.on_message(filters.text)
async def echo(message):
    await message.reply(message.text)

bot.run()