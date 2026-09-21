import os
import re
from threading import Thread
from flask import Flask
import telebot
from telebot import types

# Render Keep-Alive Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Multi-Bot Reaction System is Active!"

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

# সব বট ইনিশিয়ালাইজ করা
bot_instances = []
for config in BOT_CONFIGS:
    b = telebot.TeleBot(config["token"])
    bot_instances.append({"bot": b, "emoji": config["emoji"]})

# মূল বট (প্রথমটি দিয়ে মেসেজ লিস্টেন করা হবে)
main_bot = bot_instances[0]["bot"]

# ৫টি বট থেকে এক সাথে রিয়্যাকশন দেওয়ার ফাংশন
def react_with_all_bots(chat_id, message_id):
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
        except Exception as e:
            print(f"Reaction Error: {e}")

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

# ------ স্টার্ট কমান্ড হ্যান্ডলার (সব বটের জন্যই কাজ করবে) ------
for item in bot_instances:
    current_bot = item["bot"]
    
    @current_bot.message_handler(commands=['start'])
    def send_welcome(message, b=current_bot):
        try:
            bot_info = b.get_me()
            buttons = get_start_buttons(bot_info.username)
            text = (
                f"👋 **হ্যালো {message.from_user.first_name}!**\n\n"
                f"আমি একটি **Auto Reaction Bot**। আমাকে আপনার চ্যানেল বা গ্রুপে অ্যাডমিন বানিয়ে দিন, "
                f"অথবা আমাকে যেকোনো পোস্টের লিংক পাঠান—আমি রিয়্যাকশন দিয়ে দেব!"
            )
            b.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            print(f"Start Error: {e}")

# ------ অটো রিয়্যাকশন এবং লিংক হ্যান্ডলার ------
@main_bot.channel_post_handler(func=lambda message: True)
@main_bot.message_handler(func=lambda message: True)
def handle_messages(message):
    text = message.text or ""
    
    # লিংক পাঠানো হলে
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
            react_with_all_bots(chat_id, msg_id)
            main_bot.reply_to(message, "✅ ৫টি বট থেকে সফলভাবে পোস্টটিতে রিয়্যাকশন দেওয়া হয়েছে!")
        else:
            react_with_all_bots(message.chat.id, message.message_id)
    else:
        # সাধারণ মেসেজ বা চ্যানেলের নতুন পোস্টে
        react_with_all_bots(message.chat.id, message.message_id)

# একাধিক বট একসাথে পোলিং করার সিস্টেম
def start_bot(bot_obj):
    bot_obj.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    print("সবগুলো বট সফলভাবে চালু হচ্ছে...")
    
    # ২য় থেকে ৫ম বট ব্যাকগ্রাউন্ড থ্রেডে চালু হবে
    for item in bot_instances[1:]:
        Thread(target=start_bot, args=(item["bot"],), daemon=True).start()
        
    # ১ম বট মূল থ্রেডে চলবে
    main_bot.infinity_polling(skip_pending=True)
