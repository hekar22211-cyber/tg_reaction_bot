import os
import re
import time
from threading import Thread
from flask import Flask, request
import telebot
from telebot import types

# Render Web Server Setup
app = Flask(__name__)

# ------ ৫টি বটের টোকেন এবং ইমোজি সেটআপ ------
BOT_CONFIGS = [
    {"token": "8252013112:AAE-18UOcabbh9CgQPrMoQEV_9mppYv5iVo", "emoji": "🔥"},
    {"token": "8844690824:AAHIMT-6Y4aviEtN9kCNKVYMnZE1Hxo1ixw", "emoji": "❤️"},
    {"token": "8762438201:AAEcG7Sj1zDbodjQPUaQZObjm0_ycn5EsRs", "emoji": "👍"},
    {"token": "8687924053:AAHgMaL8ltL64Lj_ggjgWsOxX_unBRhqDQI", "emoji": "🎉"},
    {"token": "8835772612:AAF3GQ1C5YdEjp0y-T-rinwtqV3Buf2zQI4", "emoji": "😍"}
]

MAIN_CHANNEL_LINK = "https://t.me/Gaming_Rahim_YT"

# সব বট তৈরি ও ডিকশনারিতে ম্যাপ করা
bots = {}
bot_list = []

for index, config in enumerate(BOT_CONFIGS):
    b = telebot.TeleBot(config["token"], parse_mode=None)
    item = {"bot": b, "emoji": config["emoji"], "id": index, "token": config["token"]}
    bots[config["token"]] = item
    bot_list.append(item)

# ৫টি বট থেকে পোস্ট বা মেসেজে রিয়্যাকশন দেওয়ার ফাংশন
def send_multi_reactions(chat_id, message_id):
    def run():
        for item in bot_list:
            try:
                b = item["bot"]
                emoji = item["emoji"]
                reaction_obj = types.ReactionTypeEmoji(type="emoji", emoji=emoji)
                b.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[reaction_obj]
                )
                time.sleep(0.1)
            except Exception as e:
                print(f"Reaction error: {e}")
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

# সবকটি বটের জন্য ইভেন্ট হ্যান্ডলার রেজিস্টার করা
for item in bot_list:
    current_bot = item["bot"]

    @current_bot.message_handler(commands=['start'])
    def send_welcome(message, b=current_bot):
        try:
            bot_info = b.get_me()
            buttons = get_start_buttons(bot_info.username)
            text = (
                f"👋 **হ্যালো {message.from_user.first_name}!**\n\n"
                f"আমি একটি **Multi Auto Reaction Bot**। আমাকে চ্যানেল বা গ্রুপে অ্যাডমিন বানিয়ে দিন, "
                f"অথবা পোস্টের লিংক পাঠান—আমাদের ৫টি বট একসাথে রিয়্যাকশন দিয়ে দেবে!"
            )
            b.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            print(f"Start Error: {e}")

    @current_bot.channel_post_handler(func=lambda message: True)
    @current_bot.message_handler(func=lambda message: True)
    def handle_messages(message, b=current_bot):
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
                b.reply_to(message, "✅ ৫টি বট থেকেই পোস্টটিতে রিয়্যাকশন দেওয়া হচ্ছে!")
            else:
                send_multi_reactions(message.chat.id, message.message_id)
        else:
            send_multi_reactions(message.chat.id, message.message_id)

# Flask Webhook Endpoints
@app.route('/')
def home():
    return "All 5 Bots are running smoothly!"

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    if token in bots:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bots[token]["bot"].process_new_updates([update])
        return 'OK', 200
    return 'Unauthorized', 403

def setup_webhooks():
    time.sleep(2)
    # Render-এর নিজস্ব URL সংগ্রহ
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        for item in bot_list:
            b = item["bot"]
            token = item["token"]
            webhook_url = f"{render_url}/webhook/{token}"
            try:
                b.remove_webhook()
                b.set_webhook(url=webhook_url)
                print(f"Webhook set for bot: {token[:10]}")
            except Exception as e:
                print(f"Webhook setup error: {e}")

if __name__ == "__main__":
    Thread(target=setup_webhooks, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
