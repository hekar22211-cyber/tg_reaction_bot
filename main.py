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
    return "All 5 Reaction Bots System Active!"

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

# সবকটি বটের ইনস্ট্যান্স তৈরি (এখানে পোলিং শুরু হবে না)
bot_instances = []
for config in BOT_CONFIGS:
    try:
        b = telebot.TeleBot(config["token"], parse_mode=None)
        bot_instances.append({"bot": b, "emoji": config["emoji"]})
    except Exception as e:
        print(f"Bot init error: {e}")

# কেবল ১ম বটটি ইনকামিং মেসেজ হ্যান্ডেল করবে
main_bot = bot_instances[0]["bot"]

# ৫টি বট থেকে একসাথে পোস্ট বা মেসেজে রিয়্যাকশন দেওয়ার ফাংশন
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
                time.sleep(0.2) # Telegram API speed limit bypass
            except Exception as e:
                print(f"Reaction error for bot ({item['emoji']}): {e}")
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

# মেইন বটের জন্য /start কমান্ড
@main_bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        bot_info = main_bot.get_me()
        buttons = get_start_buttons(bot_info.username)
        text = (
            f"👋 **হ্যালো {message.from_user.first_name}!**\n\n"
            f"আমি একটি **Multi Auto Reaction Bot**। আমাকে চ্যানেল বা গ্রুপে অ্যাডমিন বানিয়ে দিন, "
            f"অথবা পোস্টের লিংক পাঠান—আমাদের ৫টি বট একসাথে রিয়্যাকশন দিয়ে দেবে!"
        )
        main_bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=buttons)
    except Exception as e:
        print(f"Start Error: {e}")

# চ্যানেল/গ্রুপের পোস্ট এবং পোস্টের লিংকের হ্যান্ডলার
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
            send_multi_reactions(chat_id, msg_id)
            main_bot.reply_to(message, "✅ ৫টি বট থেকেই পোস্টটিতে রিয়্যাকশন দেওয়া হচ্ছে!")
        else:
            send_multi_reactions(message.chat.id, message.message_id)
    else:
        # সাধারণ মেসেজ বা চ্যানেলে নতুন পোস্ট এলে
        send_multi_reactions(message.chat.id, message.message_id)

if __name__ == "__main__":
    print("শুধুমাত্র মেইন বট পোলিং নিয়ে চালু হচ্ছে (Conflict মুক্ত)...")
    
    # পুরোনো সেশন/কানেকশন ক্লিয়ার করা
    main_bot.remove_webhook()
    time.sleep(1)
    
    # শুধুমাত্র ১টি বটের পোলিং চলবে
    main_bot.infinity_polling(skip_pending=True)
