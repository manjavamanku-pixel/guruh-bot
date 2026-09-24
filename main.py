import asyncio
import logging
import re
import os
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ChatPermissions
from aiogram.enums import ChatMemberStatus
from aiohttp import web

TOKEN = "8873391012:AAFQOmY_ZJ01qAD90BV--grmb5X4lSW18lU"
OWNER_ID = 8618374917
DB_URL = "postgresql://postgres:Alixan005!uz@db.evfuwvxvjbtgkgivgcfw.supabase.co:5432/postgres"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
db_pool = None

BAD_WORDS_PATTERN = re.compile(r'\b(so\'kinish|haqorat|jalab|qanjiq|chmo|reklama|link)\b', re.IGNORECASE)

async def init_db():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DB_URL)
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    except Exception as e:
        logging.error(f"Baza xatosi (Bot ishlashda davom etadi): {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply("Assalomu alaykum! Men guruhni nazorat qiluvchi aqlli botman.")

async def is_admin(message: types.Message):
    if message.from_user.id == OWNER_ID:
        return True
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message:
        return await message.reply("Ban qilish uchun o'sha odamning xabariga 'reply' qiling.")
    try:
        await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply("Foydalanuvchi guruhdan haydaldi.")
    except Exception:
        await message.reply("Xatolik yuz berdi.")

@dp.message(Command("mute"))
async def cmd_mute(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message:
        return await message.reply("Mute qilish uchun xabarga 'reply' qiling.")
    try:
        await bot.restrict_chat_member(
            message.chat.id, 
            message.reply_to_message.from_user.id, 
            permissions=ChatPermissions(can_send_messages=False)
        )
        await message.reply("Foydalanuvchi yozish huquqidan mahrum qilindi (Mute).")
    except Exception:
        await message.reply("Xatolik yuz berdi.")

@dp.message(Command("unmute"))
async def cmd_unmute(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message:
        return await message.reply("Unmute qilish uchun xabarga 'reply' qiling.")
    try:
        await bot.restrict_chat_member(
            message.chat.id, 
            message.reply_to_message.from_user.id, 
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True,
                can_send_documents=True, can_send_photos=True,
                can_send_videos=True, can_send_other_messages=True
            )
        )
        await message.reply("Foydalanuvchining yozish huquqi tiklandi.")
    except Exception:
        pass

@dp.message(Command("allban"))
async def cmd_allban(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    if not db_pool:
        return await message.reply("Baza hozircha ulanmagan.")
    async with db_pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")
        count = 0
        for row in users:
            try:
                await bot.ban_chat_member(chat_id=message.chat.id, user_id=row['user_id'])
                count += 1
            except Exception:
                pass
        await message.reply(f"Maxfiy buyruq: Bazadan {count} ta a'zo haydaldi.")
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    # Faqat siz (Owner) ishlata olasiz
    if message.from_user.id != OWNER_ID: return
    if not db_pool:
        return await message.reply("Baza hozircha ulanmagan.")
    
    async with db_pool.acquire() as conn:
        # Bazadan hamma foydalanuvchilarni olish
        users = await conn.fetch("SELECT user_id, username FROM users")
        
    if not users:
        return await message.reply("Bazada hali a'zolar yig'ilmagan.")
        
    # Guruh nomini aniqlash (agar guruhda yozilsa)
    if message.chat.type in ["group", "supergroup"]:
        group_name = message.chat.title
    else:
        group_name = "Baza (Shaxsiy chatdan tekshirildi)"
        
    text = f"🏢 Guruh nomi: {group_name}\n👥 Bazaga yig'ilgan barcha a'zolar:\n\n"
    
    count = 1
    for row in users:
        if row['username']:
            text += f"{count}. @{row['username']}\n"
        else:
            text += f"{count}. 🆔 {row['user_id']} (Usernami yo'q)\n"
        count += 1
        
        # Telegram xabari o'ta uzun bo'lib ketsa, bo'lib jo'natish uchun
        if len(text) > 3900:
            await message.answer(text)
            text = ""
            
    if text.strip():
        await message.answer(text)

@dp.message()
async def check_message(message: types.Message):
    if not message.from_user.is_bot and db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO users (user_id, username) 
                    VALUES ($1, $2) 
                    ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
                ''', message.from_user.id, message.from_user.username)
        except Exception:
            pass

    if message.text and BAD_WORDS_PATTERN.search(message.text):
        try:
            await message.delete()
            msg = await message.answer(f"Hurmatli {message.from_user.full_name}, guruhda yomon so'zlar yozish taqiqlangan!")
            await asyncio.sleep(4)
            await msg.delete()
        except Exception:
            pass

# RENDER UCHUN "YOLG'ONCHI" VEB-SERVER
async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="Bot ishlayapti!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await init_db()
    asyncio.create_task(web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
