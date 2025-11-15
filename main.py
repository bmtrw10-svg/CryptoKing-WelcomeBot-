import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ChatMemberOwner, ChatMemberAdministrator
from aiogram.exceptions import TelegramForbiddenError

# === CONFIG ===
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "welcome_message": "🚀 Welcome to CryptoKing Signals!  \n⚡ We drop 3–5 high-accuracy signals daily.  \n📌 **RULES** (must read or you’ll be muted):  \n1️⃣ No spam, no promo, no links  \n2️⃣ No begging for free signals  \n3️⃣ Use /help for commands  \n4️⃣ English only  \n5️⃣ No screenshots of signals outside this group  \n🔗 Pinned message has full FAQ  \nIntroduce yourself: *Name + Country*  \nLet’s make money! 💰",
    "delay_seconds": 7,
    "batch_delay": 2
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

config = load_config()

# === LOGGING ===
logging.basicConfig(level=logging.INFO)

# === BOT ===
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

sent_welcomes = set()
join_queue = []
queue_lock = asyncio.Lock()

async def is_admin(member: types.ChatMember):
    return isinstance(member, (ChatMemberOwner, ChatMemberAdministrator))

@dp.chat_member()
async def handle_new_member(update: types.ChatMemberUpdated):
    if update.new_chat_member.status not in ["member", "administrator", "creator"]:
        return
    user = update.new_chat_member.user
    chat = update.chat
    member = await bot.get_chat_member(chat.id, user.id)
    if await is_admin(member):
        return
    async with queue_lock:
        join_queue.append((user, chat, datetime.now()))

async def process_queue():
    while True:
        batch = []
        async with queue_lock:
            now = datetime.now()
            if join_queue:
                first = join_queue[0][2]
                batch = [x for x in join_queue if now - x[2] <= timedelta(seconds=10)]
                join_queue = [x for x in join_queue if x not in batch]
        if batch:
            batch.sort(key=lambda x: x[2])
            for i, (user, chat, _) in enumerate(batch):
                if user.id in sent_welcomes: continue
                await asyncio.sleep(config["delay_seconds"] if i == 0 else config["batch_delay"])
                try:
                    await bot.send_message(user.id, config["welcome_message"], parse_mode="Markdown")
                    sent_welcomes.add(user.id)
                except TelegramForbiddenError:
                    try:
                        msg = await bot.send_message(chat.id, f"@{user.username or user.first_name} please enable DMs!")
                        await asyncio.sleep(30)
                        await msg.delete()
                    except: pass
                except Exception as e: print(e)
        await asyncio.sleep(1)

@dp.message(Command("setwelcome"))
async def setwelcome(message: types.Message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if not await is_admin(member):
        return await message.reply("❌ Admin only")
    if not message.reply_to_message:
        return await message.reply("Reply to a message with new welcome text.")
    new_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if new_text.strip():
        config["welcome_message"] = new_text
        save_config(config)
        await message.reply("✅ Welcome updated!")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.reply("/help - this\n/setwelcome - admin only")

async def main():
    print("Bot starting...")
    asyncio.create_task(process_queue())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
