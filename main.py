import os
from threading import Thread
from flask import Flask
import telebot

# Render-কে লাইভ রাখার জন্য ফ্ল্যাঙ্ক সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ব্যাকগ্রাউন্ডে ফ্ল্যাঙ্ক ওয়েব সার্ভার স্টার্ট
Thread(target=run_web, daemon=True).start()

# ------ টেলিগ্রাম বট কনফিগারেশন ------
# এখানে আপনার বটের টোকেন দেওয়া আছে
BOT_TOKEN = "8858854627:AAHkOHPcYDrkdp5wpeXaYZsZrpPuUAYtGV4"
bot = telebot.TeleBot(BOT_TOKEN)

# অটো-রিয়েকশন ইমোজি (পছন্দমতো ইমোজি বসাতে পারেন)
REACTION_EMOJI = "🔥"

# চ্যানেলে নতুন কোনো পোস্ট আসলেই রিয়েকশন দেবে
@bot.channel_post_handler(func=lambda message: True)
def auto_react(message):
    try:
        bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[telebot.types.ReactionTypeEmoji(REACTION_EMOJI)]
        )
        print(f"Post ID {message.message_id}-এ রিয়েকশন দেওয়া হয়েছে!")
    except Exception as e:
        print(f"এরর: {e}")

if __name__ == "__main__":
    print("বট সফলভাবে চালু হয়েছে...")
    bot.infinity_polling(skip_pending=True)
