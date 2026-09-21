import os
import re
import time
from threading import Thread
from flask import Flask
import telebot
from telebot import types

# Render Keep-Alive Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "All 5 Reaction Bots Active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# ------ ৫টি বটের টোকেন এবং ইমোজি সেটআপ ------
BOT_CONFIGS = [
    {"token": "8252013112:AAE-18UOcabbh9CgQPrMoQEV_9mppYv5iVo", "emoji": "🔥"},
    {"token": "8844690824:AAHIMT-6Y4aviEtN9kCNKVYMnZE1Hxo1ixw", "emoji": "❤️"},
    {"token": "8762438201:AAEcG7Sj1zDbodjQPUaQZObjm0_ycn5EsRs", "emoji": "👍"},
    {"token": "8687924053:AAHgMaL8ltL64Lj_ggjgWsOxX_unBRhqDQI", "emoji": "🎉"},
    {"token": "8835772612:AAF3GQ1C5YdEjp0y-T-rinwtqV3Buf2zQI4", "emoji": "😍"}
]

MAIN_CHANNEL_LINK = "https://t.me/Gaming_Rahim_YT"

# সব বট তৈরি করা
bot_instances = []
for config in BOT_CONFIGS:
    try:
        b = telebot.TeleBot(config["token"], parse_mode=None)
        bot_instances.append({"bot": b, "emoji": config["emoji"]})
    except Exception as e:
        print(f"Bot init error: {e}")

main_bot = bot_instances[0]["bot"]

# ৫টি বট থেকে পোস্ট বা মেসেজে রিয়্যাকশন দেওয়া
def send_multi_reactions(chat_id, message_id):
    def run():
        for item in bot_instances:
            try:
                b = item["bot"]
                emoji = item["emoji"]
                reaction_obj = types.ReactionTypeEmoji(type="emoji", emoji=emoji)
                b.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[reaction_obj]
                )
                time.sleep(0.3) # টেলিগ্রাম সার্ভার লিমিট এড়াতে বিরতি
            except Exception as e:
                print(f"Reaction fail for a bot: {e}")
    Thread(target=run).start()

# Inline Buttons তৈরি করার ফাংশন
def get_start_buttons(bot_username):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    add_channel_url = f"https://t.me/{bot_username}?startchannel=true"
    add_group_url = f"https://t.me/{bot_username}?startgroup=true"
    
    btn_channel = types.InlineKeyboardButton("➕ Add Channel", url=add_channel_url)
    btn_group = types.InlineKeyboardButton("➕ Add Group", url=add_group_url)
    btn_main = types.InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)
    
    markup.add(btn_channel, btn_group)
    markup.add(btn_main)
    return markup

# সবকটি বটের জন্য /start কমান্ড সেটআপ
for item in bot_instances:
    current_bot = item["bot"]
    @current_bot.message_handler(commands=['start'])
    def send_welcome(message, b=current_bot):
        try:
            bot_info = b.get_me()
            buttons = get_start_buttons(bot_info.username)
            text = (
                f"👋 **হ্যালো {message.from_user.first_name}!**\n\n"
                f"আমি একটি **Multi Auto Reaction Bot**। আমাকে চ্যানেল বা গ্রুপে অ্যাডমিন বানিয়ে দিন, "
                f"অথবা পোস্টের লিংক পাঠান—আমাদের ৫টি বট রিয়্যাকশন দিয়ে দেবে!"
            )
            b.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            print(f"Start Error: {e}")

# চ্যানেল ও গ্রুপের নতুন পোস্ট এবং লিংকের জন্য হ্যান্ডলার
@main_bot.channel_post_handler(func=lambda message: True)
@main_bot.message_handler(func=lambda message: True)
def handle_messages(message):
    text = message.text or ""
    
    if "t.me/" in text:
        pub_match = re.search(r't\.me/([^/]+)/(\d+)', text)
        priv_match = re.search(r't\.me/c/(\d+)/(\d+)', text)

        chat_id = None
        msg_id = None

        if priv_match:
            chat_id = int(f"-100{priv_match.group(1)}")
            msg_id = int(priv_match.group(2))
        elif pub_match and pub_match.group(1) != 'c':
            chat_id = f"@{pub_match.group(1)}"
            msg_id = int(pub_match.group(2))

        if chat_id and msg_id:
            send_multi_reactions(chat_id, msg_id)
            main_bot.reply_to(message, "✅ ৫টি বট থেকেই পোস্টটিতে রিয়্যাকশন দেওয়া হচ্ছে!")
        else:
            send_multi_reactions(message.chat.id, message.message_id)
    else:
        send_multi_reactions(message.chat.id, message.message_id)

# প্রতিটি বটকে ব্যাকগ্রাউন্ডে পোলিং শুরু করার কাজ
def start_polling(bot_obj):
    try:
        bot_obj.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Polling error: {e}")

if __name__ == "__main__":
    print("৫টি বটই চালু করা হচ্ছে...")
    
    # ২য় থেকে ৫ নম্বর বট ব্যাকগ্রাউন্ড থ্রেডে চলবে
    for item in bot_instances[1:]:
        Thread(target=start_polling, args=(item["bot"],), daemon=True).start()
        
    # ১ম বট মূল থ্রেডে কাজ করবে
    main_bot.infinity_polling(skip_pending=True)
