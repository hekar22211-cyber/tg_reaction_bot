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
BOT_TOKEN = "8858854627:AAF2bSIK_NjutApjPrc35hGVLh5MMRreQzk"
bot = telebot.TeleBot(BOT_TOKEN)

# অটো-রিয়েকশন ইমোজি (এখানে ইচ্ছেমতো ইমোজি দিতে পারেন)
REACTION_EMOJI = "🔥"

# চ্যানেল পোস্ট, গ্রুপ মেসেজ এবং প্রাইভেট মেসেজ—সব জায়গায় রিয়েকশন দেবে
@bot.channel_post_handler(func=lambda message: True)
@bot.message_handler(func=lambda message: True)
def auto_react(message):
    try:
        reaction_obj = telebot.types.ReactionTypeEmoji(type="emoji", emoji=REACTION_EMOJI)
        bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[reaction_obj]
        )
        print(f"Message ID {message.message_id}-এ রিয়েকশন সফল!")
    except Exception as e:
        print(f"এরর: {e}")

if __name__ == "__main__":
    print("বট সফলভাবে চালু হয়েছে...")
    bot.infinity_polling(skip_pending=True)
