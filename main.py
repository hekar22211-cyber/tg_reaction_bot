import os
import telebot
from telebot import types
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "8940347817:AAFisnF-SD7vAqlV0BtTvyuLwEbIyNF7tRg")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8454171811"))

bot = telebot.TeleBot(TOKEN)

# ==========================================
# Web Server for Render
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ==========================================
# Database & Configuration
# ==========================================
# আপনার আসল চ্যানেল যুক্ত করা হলো
ADMIN_GROUPS = ["@Gaming_Rahim_YT"] 

REFERRAL_BONUS = 10.0
MIN_WITHDRAW = 500.0

users = {}
user_states = {}

def get_user_data(user_id):
    if user_id not in users:
        users[user_id] = {
            "balance": 0.0,
            "ref_by": None,
            "referrals": 0,
            "verified": False
        }
    return users[user_id]

def check_join(user_id):
    # অ্যাডমিন হলে জয়েনিং চেক বাইপাস হবে
    if user_id == ADMIN_ID:
        return True
        
    if not ADMIN_GROUPS:
        return True
        
    for group in ADMIN_GROUPS:
        try:
            member = bot.get_chat_member(group, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception:
            return False
    return True

# ==========================================
# Keyboards
# ==========================================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_profile = types.KeyboardButton("👤 প্রোফাইল")
    btn_refer = types.KeyboardButton("🔗 রেফার")
    btn_withdraw = types.KeyboardButton("💳 উইথড্র")
    markup.add(btn_profile, btn_refer, btn_withdraw)
    return markup

def verify_keyboard():
    markup = types.InlineKeyboardMarkup()
    for idx, group in enumerate(ADMIN_GROUPS, 1):
        clean_username = group.replace('@', '')
        link = f"https://t.me/{clean_username}"
        markup.add(types.InlineKeyboardButton(text=f"📢 জয়েন করুন {idx} ({group})", url=link))
    markup.add(types.InlineKeyboardButton(text="✅ ভেরিফাই করুন", callback_data="check_verification"))
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ইউজার লিস্ট ও তথ্য", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton(text="🎁 রেফার বোনাস পরিবর্তন", callback_data="admin_set_bonus"))
    markup.add(types.InlineKeyboardButton(text="➕ চ্যানেল যোগ করুন", callback_data="admin_add_channel"))
    markup.add(types.InlineKeyboardButton(text="❌ চ্যানেল ডিলিট করুন", callback_data="admin_del_channel"))
    markup.add(types.InlineKeyboardButton(text="🔗 চ্যানেল লিস্ট দেখুন", callback_data="admin_list_channel"))
    return markup

def payment_method_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(text="📱 বিকাশ (Bkash)", callback_data="pay_Bkash"),
        types.InlineKeyboardButton(text="📲 নগদ (Nagad)", callback_data="pay_Nagad")
    )
    return markup

# ==========================================
# Command Handlers
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    command_args = message.text.split()
    if len(command_args) > 1 and not user_data['verified']:
        try:
            referrer_id = int(command_args[1])
            if referrer_id != user_id and user_data['ref_by'] is None:
                user_data['ref_by'] = referrer_id
        except ValueError:
            pass

    if check_join(user_id):
        user_data['verified'] = True
        bot.send_message(
            user_id,
            "✨ **স্বাগতম!** নিচের মেনু থেকে অপশন সিলেক্ট করুন:",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            "⚠️ বটের সুবিধা পেতে অবশ্যই আমাদের চ্যানেল/গ্রুপগুলোতে জয়েন করতে হবে:",
            reply_markup=verify_keyboard()
        )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            f"⚙️ **এডমিন প্যানেল:**\n\nবর্তমান রেফার বোনাস: `{REFERRAL_BONUS}` BDT",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
    else:
        bot.send_message(message.chat.id, "❌ আপনি এই বটের এডমিন নন।")

@bot.callback_query_handler(func=lambda call: call.data == "check_verification")
def callback_verify(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    if check_join(user_id):
        if not user_data['verified']:
            user_data['verified'] = True
            if user_data['ref_by'] and user_data['ref_by'] in users:
                ref_user = users[user_data['ref_by']]
                ref_user['balance'] += REFERRAL_BONUS
                ref_user['referrals'] += 1
                try:
                    bot.send_message(
                        user_data['ref_by'],
                        f"🎉 **অভিনন্দন!** নতুন ইউজার ভেরিফাই করেছে। আপনি {REFERRAL_BONUS} BDT বোনাস পেয়েছেন।"
                    )
                except Exception:
                    pass

        bot.answer_callback_query(call.id, "✅ ভেরিফিকেশন সফল হয়েছে!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
            
        # ভেরিফাই করার পর মেসেজ পাঠানোর সাথে সাথে কাস্টম বাটন নিচে সেট করে দেবে
        bot.send_message(
            user_id,
            "🎉 **ধন্যবাদ!** আপনার অ্যাকাউন্ট ভেরিফাই হয়েছে। নিচের মেনু থেকে অপশন সিলেক্ট করুন:",
            reply_markup=main_keyboard()
        )
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো সবগুলো চ্যানেল/গ্রুপে জয়েন করেননি!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    if call.data == "admin_users":
        total_registered = len(users)
        msg = f"👥 **মোট ইউজার সংখ্যা:** {total_registered}\n\n"
        if not users:
            msg += "কোনো ইউজার নিবন্ধিত নেই।"
        else:
            for uid, info in users.items():
                msg += f"• ID: `{uid}` | Balance: {info['balance']} | Verified: {info['verified']}\n"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif call.data == "admin_set_bonus":
        user_states[call.from_user.id] = {"action": "set_bonus"}
        bot.send_message(call.message.chat.id, "✏️ নতুন রেফার বোনাসের পরিমাণ লিখে সেন্ড করুন:")

    elif call.data == "admin_add_channel":
        user_states[call.from_user.id] = {"action": "add_channel"}
        bot.send_message(call.message.chat.id, "➕ **নতুন চ্যানেলের ইউজারনেম দিন:**\nউদাহরণ: `@mychannel`")

    elif call.data == "admin_del_channel":
        if not ADMIN_GROUPS:
            bot.send_message(call.message.chat.id, "❌ কোনো চ্যানেল যুক্ত নেই।")
            return
        user_states[call.from_user.id] = {"action": "del_channel"}
        msg = "❌ **যে ইউজারনেমটি ডিলিট করতে চান তা লিখে সেন্ড করুন:**\n\n"
        for grp in ADMIN_GROUPS:
            msg += f"• `{grp}`\n"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif call.data == "admin_list_channel":
        if not ADMIN_GROUPS:
            msg = "🔗 কোনো চ্যানেল যুক্ত করা নেই।"
        else:
            msg = "🔗 **বর্তমান চ্যানেল/গ্রুপসমূহ:**\n\n"
            for idx, grp in enumerate(ADMIN_GROUPS, 1):
                msg += f"{idx}. {grp}\n"
        bot.send_message(call.message.chat.id, msg)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def withdraw_method_select(call):
    user_id = call.from_user.id
    method = call.data.split("_")[1]
    user_states[user_id] = {"action": "withdraw_number", "method": method}
    bot.edit_message_text(
        f"📱 **{method} মেথড সিলেক্ট করেছেন।**\n\nবিকাশ/নগদ নম্বরটি লিখে সেন্ড করুন:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    user_data = get_user_data(user_id)

    if user_id in user_states:
        state = user_states[user_id]
        
        if state.get("action") == "set_bonus" and user_id == ADMIN_ID:
            try:
                global REFERRAL_BONUS
                REFERRAL_BONUS = float(text)
                del user_states[user_id]
                bot.send_message(user_id, f"✅ সফলভাবে রেফার বোনাস **{REFERRAL_BONUS} BDT** সেট করা হয়েছে।", parse_mode="Markdown")
            except ValueError:
                bot.send_message(user_id, "❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন।")
            return

        elif state.get("action") == "add_channel" and user_id == ADMIN_ID:
            if not text.startswith("@"):
                bot.send_message(user_id, "❌ ইউজারনেমের শুরুতে অবশ্যই `@` থাকতে হবে। (যেমন: `@mychannel`)")
                return
            if text in ADMIN_GROUPS:
                bot.send_message(user_id, "⚠️ এই চ্যানেলটি ইতিমধ্যেই যুক্ত আছে।")
            else:
                ADMIN_GROUPS.append(text)
                bot.send_message(user_id, f"✅ চ্যানেল `{text}` সফলভাবে যুক্ত করা হয়েছে!", parse_mode="Markdown")
            del user_states[user_id]
            return

        elif state.get("action") == "del_channel" and user_id == ADMIN_ID:
            if text in ADMIN_GROUPS:
                ADMIN_GROUPS.remove(text)
                bot.send_message(user_id, f"✅ চ্যানেল `{text}` সফলভাবে মুছে ফেলা হয়েছে!", parse_mode="Markdown")
            else:
                bot.send_message(user_id, "❌ এই ইউজারনেমটি তালিকায় খুঁজে পাওয়া যায়নি।")
            del user_states[user_id]
            return

        elif state.get("action") == "withdraw_number":
            state["number"] = text
            state["action"] = "withdraw_amount"
            bot.send_message(user_id, f"✅ **নম্বর:** `{text}`\n\nকত টাকা উইথড্র করতে চান তা লিখুন (সর্বনিম্ন ৫০০ BDT):", parse_mode="Markdown")
            return

        elif state.get("action") == "withdraw_amount":
            try:
                amount = float(text)
                if amount < MIN_WITHDRAW:
                    bot.send_message(user_id, f"⚠️ **উইথড্র দেওয়া সম্ভব নয়!**\nসর্বনিম্ন উইথড্র অ্যামাউন্ট ৫০০ টাকা। আপনার ইনপুটকৃত অ্যামাউন্ট: {amount} BDT।")
                    return
                
                if amount > user_data["balance"]:
                    bot.send_message(user_id, f"❌ **অপর্যাপ্ত ব্যালেন্স!**\nআপনার বর্তমান ব্যালেন্স: {user_data['balance']} BDT।")
                    del user_states[user_id]
                    return

                method = state["method"]
                num = state["number"]
                user_data["balance"] -= amount
                del user_states[user_id]

                bot.send_message(
                    user_id,
                    f"🎉 **উইথড্র রিকোয়েস্ট সফল হয়েছে!**\n\n💳 মেথড: {method}\n📱 নম্বর: `{num}`\n💰 পরিমাণ: {amount} BDT\n\nএডমিন খুব শীঘ্রই পেমেন্ট প্রসেস করবেন।",
                    parse_mode="Markdown"
                )

                try:
                    bot.send_message(
                        ADMIN_ID,
                        f"📥 **নতুন উইথড্র রিকোয়েস্ট!**\n\n👤 ইউজার ID: `{user_id}`\n💳 মেথড: {method}\n📱 নম্বর: `{num}`\n💰 পরিমাণ: {amount} BDT",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            except ValueError:
                bot.send_message(user_id, "❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন।")
            return

    if not check_join(user_id):
        bot.send_message(user_id, "⚠️ সেবাটি ব্যবহার করতে আগে চ্যানেলগুলোতে জয়েন করুন।", reply_markup=verify_keyboard())
        return

    if text == "👤 প্রোফাইল":
        name = message.from_user.first_name
        profile_msg = f"👤 **ইউজার প্রোফাইল**\n\n🏷 **নাম:** {name}\n🆔 **ইউজার আইডি:** `{user_id}`\n💰 **ব্যালেন্স:** {user_data['balance']} BDT\n👥 **মোট রেফার:** {user_data['referrals']}"
        bot.send_message(user_id, profile_msg, parse_mode="Markdown")

    elif text == "🔗 রেফার":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_msg = f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n🎁 প্রতি সফল রেফারে পাবেন **{REFERRAL_BONUS} BDT**।"
        bot.send_message(user_id, ref_msg, parse_mode="Markdown")

    elif text == "💳 উইথড্র":
        withdraw_msg = f"💳 **উইথড্র সিস্টেম**\n\n💰 আপনার বর্তমান ব্যালেন্স: **{user_data['balance']} BDT**\n⚠️ সর্বনিম্ন উইথড্র: **৫০০ BDT**\n\nনিচ থেকে পেমেন্ট মেথড সিলেক্ট করুন:"
        bot.send_message(user_id, withdraw_msg, parse_mode="Markdown", reply_markup=payment_method_keyboard())

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    bot.infinity_polling()
