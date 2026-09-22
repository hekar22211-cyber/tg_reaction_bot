import os
import re
import time
from datetime import datetime
from threading import Thread
from flask import Flask, request
import telebot
from telebot import types

# Render Web Server
app = Flask(__name__)

# ------ ৭টি বটের টোকেন এবং ইমোজি সেটআপ ------
BOT_CONFIGS = [
    {"token": "8252013112:AAE-18UOcabbh9CgQPrMoQEV_9mppYv5iVo", "emoji": "🔥"},
    {"token": "8844690824:AAHIMT-6Y4aviEtN9kCNKVYMnZE1Hxo1ixw", "emoji": "❤️"},
    {"token": "8762438201:AAEcG7Sj1zDbodjQPUaQZObjm0_ycn5EsRs", "emoji": "👍"},
    {"token": "8687924053:AAHgMaL8ltL64Lj_ggjgWsOxX_unBRhqDQI", "emoji": "🎉"},
    {"token": "8835772612:AAF3GQ1C5YdEjp0y-T-rinwtqV3Buf2zQI4", "emoji": "😍"},
    {"token": "8875207866:AAG8WsNHOljlMPkjL7DEZdevCq3N_a10NHI", "emoji": "👏"},
    {"token": "8964970848:AAHJ__OgdkYlpjg-NICmMxsN5BXy5vY8X_8", "emoji": "⚡"}
]

MAIN_CHANNEL_LINK = "https://t.me/Gaming_Rahim_YT"

# 👤 আপনার এডমিন টেলিগ্রাম ইউজার আইডি
OWNER_ID = 8454171811

bots = {}
bot_list = []

for index, config in enumerate(BOT_CONFIGS):
    b = telebot.TeleBot(config["token"], parse_mode=None)
    item = {"bot": b, "emoji": config["emoji"], "id": index, "token": config["token"]}
    bots[config["token"]] = item
    bot_list.append(item)

main_bot = bot_list[0]["bot"]

# ৭টি বট থেকে পোস্ট বা মেসেজে রিয়্যাকশন দেওয়ার ফাংশন
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

def get_start_buttons(bot_username):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_channel = types.InlineKeyboardButton("➕ Add Channel", url=f"https://t.me/{bot_username}?startchannel=true")
    btn_group = types.InlineKeyboardButton("➕ Add Group", url=f"https://t.me/{bot_username}?startgroup=true")
    btn_main = types.InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)
    markup.add(btn_channel, btn_group)
    markup.add(btn_main)
    return markup

# /start কমান্ড হ্যান্ডলার
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
                f"অথবা পোস্টের লিংক পাঠান—আমাদের ৭টি বট একসাথে রিয়্যাকশন দিয়ে দেবে!"
            )
            b.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            print(f"Start Error: {e}")

# 🔔 কোনো গ্রুপ বা চ্যানেলে বট যুক্ত হলে এডমিন আইডিতে বিস্তারিত নোটিফিকেশন পাঠানোর হ্যান্ডলার
def process_chat_member_update(my_chat_member, bot_obj):
    new_status = my_chat_member.new_chat_member.status
    chat = my_chat_member.chat
    user = my_chat_member.from_user

    # বট যদি সদস্য বা অ্যাডমিন হিসেবে যুক্ত হয়
    if new_status in ["administrator", "member"]:
        # চ্যাট/গ্রুপের ইউজারনেম বা লিংক বের করা
        if chat.username:
            chat_link = f"https://t.me/{chat.username}"
        else:
            try:
                chat_link = bot_obj.export_chat_invite_link(chat.id)
            except Exception:
                chat_link = "No Public Link / Admin access needed to generate link"

        # মেম্বার সংখ্যা গণনা
        try:
            member_count = bot_obj.get_chat_members_count(chat.id)
        except Exception:
            member_count = "Unknown"

        # ইউজারের তথ্য
        user_mention = f"[{user.first_name}](tg://user?id={user.id})"
        username_str = f"@{user.username}" if user.username else "No Username"
        added_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        text = (
            f"🔔 **নতুন চ্যাটে বট যুক্ত হয়েছে!**\n\n"
            f"📌 **চ্যাট/গ্রুপের বিস্তারিত:**\n"
            f"• **নাম:** {chat.title}\n"
            f"• **ID:** `{chat.id}`\n"
            f"• **টাইপ:** {chat.type.capitalize()}\n"
            f"• **মোট সদস্য:** {member_count}\n"
            f"• **লিংক:** {chat_link}\n\n"
            f"👤 **যুক্ত করেছে যে ইউজার:**\n"
            f"• **নাম:** {user_mention}\n"
            f"• **ইউজারনেম:** {username_str}\n"
            f"• **ইউজার ID:** `{user.id}`\n\n"
            f"🤖 **যে বট যুক্ত করা হয়েছে:** @{bot_obj.get_me().username}\n"
            f"⏰ **সময়:** `{added_time}`"
        )

        try:
            main_bot.send_message(OWNER_ID, text, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            print(f"Notification Send Error: {e}")

# সবকটি বটের জন্য চ্যাট মেম্বার আপডেট হ্যান্ডলার
for item in bot_list:
    current_bot = item["bot"]
    @current_bot.my_chat_member_handler()
    def handle_my_chat_member(my_chat_member, b=current_bot):
        process_chat_member_update(my_chat_member, b)

# অটো রিয়্যাকশন এবং পোস্ট লিঙ্ক হ্যান্ডলার
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
            main_bot.reply_to(message, "✅ ৭টি বট থেকেই পোস্টটিতে রিয়্যাকশন দেওয়া হচ্ছে!")
        else:
            send_multi_reactions(message.chat.id, message.message_id)
    else:
        send_multi_reactions(message.chat.id, message.message_id)

@app.route('/')
def home():
    return "7 Bots Notification Reaction System is Live!"

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
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        for item in bot_list:
            b = item["bot"]
            token = item["token"]
            webhook_url = f"{render_url}/webhook/{token}"
            try:
                b.remove_webhook()
                b.set_webhook(url=webhook_url, allowed_updates=["message", "channel_post", "my_chat_member"])
            except Exception as e:
                print(f"Webhook error: {e}")

if __name__ == "__main__":
    Thread(target=setup_webhooks, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
