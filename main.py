import asyncio
import os
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message

# Render Health Check-এর জন্য ডামি ফ্ল্যাঙ্ক সার্ভার
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running fine!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

# ব্যাকগ্রাউন্ডে ফ্ল্যাঙ্ক ওয়েব সার্ভার চালু
Thread(target=run_web, daemon=True).start()

# ------ টেলিগ্রাম বটের কনফিগারেশন ------
# my.telegram.org থেকে আপনার আসল API_ID ও API_HASH বসাবেন
API_ID = 12345678  
API_HASH = "YOUR_API_HASH_HERE"

# বটের টোকেন তালিকা (এখানে একাধিক টোকেন যোগ করতে পারেন)
BOT_TOKENS = [
    "8858854627:AAHkOHPcYDrkdp5wpeXaYZsZrpPuUAYtGV4",
]

# অটো-রিয়েকশন ইমোজি (পছন্দ মতো পরিবর্তন করতে পারেন)
REACTION_EMOJI = "🔥"

apps = []

for index, token in enumerate(BOT_TOKENS):
    app = Client(
        name=f"bot_session_{index}",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=token
    )
    apps.append(app)

def setup_handlers(app):
    @app.on_message(filters.channel)
    async def auto_react(client: Client, message: Message):
        try:
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=REACTION_EMOJI
            )
            print(f"[{client.name}] রিয়েকশন সফলভাবে দেওয়া হয়েছে!")
        except Exception as e:
            print(f"[{client.name}] এরর: {e}")

for app in apps:
    setup_handlers(app)

async def main():
    print("বট চালু হচ্ছে...")
    await asyncio.gather(*(app.start() for app in apps))
    print("সবগুলো বট সক্রিয় এবং নতুন পোস্টের জন্য প্রস্তুত!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Python 3.10+ Event Loop Fix
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
