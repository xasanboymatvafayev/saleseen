import asyncio
from aiogram import Bot
import logging

# Enable logging
logging.basicConfig(level=logging.INFO)

# Your bot token
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your actual bot token
ADMIN_ID = 7657015533  # The admin ID we're testing with

async def test_send_message():
    bot = Bot(token=BOT_TOKEN)
    try:
        # Try to send a test message to the admin
        await bot.send_message(
            chat_id=ADMIN_ID,
            text="🔔 Test xabar: Sizga xabarlar tushadimi?"
        )
        print("✅ Xabar muvaffaqiyatli yuborildi!")
    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")
        print("\nIltimos, quyidagilarni tekshiring:")
        print("1. Bot admin tomonidan ishga tushirilganmi?")
        print("2. Admin botni bloklaganmi?")
        print("3. Bot tokeni to'g'rimi?")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_send_message())
