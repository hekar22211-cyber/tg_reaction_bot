import os
import telebot
from telebot import types
from dotenv import load_dotenv

# .env ফাইল থেকে টোকেন লোড করা
load_dotenv()

# বট টোকেন ও এডমিন আইডি
TOKEN = os.getenv("BOT_TOKEN", "8940347817:AAFisnF-SD7vAqlV0BtTvyuLwEbIyNF7tRg")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8454171811"))

bot = telebot.TeleBot(TOKEN)

# ==========================================
# কনফিগারেশন ও মেমোরি ডাটাবেস
# ==========================================

ADMIN_GROUPS = ["@channel_or_group_1", "@channel_or_group_2"]

# ডিফল্ট রেফারেল বোনাস ও সর্বনিম্ন উইথড্র অ্যামাউন্ট
REFERRAL_BONUS = 10.0
MIN_WITHDRAW = 500.0

# ইউজার ও প্রসেস ডাটা সংরক্ষণের মেমোরি
users = {}
user_states = {}  # উইথড্র ও এডমিন ইনপুট ট্র্যাকিংয়ের জন্য

def get_user_data(user_id):
    if user_id not in users:
        users[user_id] = {
            "balance": 0.0,
            "ref_by": None,
            "referrals": 0,
            "verified": False
        }
    return users[user_id]

# ==========================================
# হেল্পার ফাংশন
# ==========================================

def check_join(user_id):
    for group in ADMIN_GROUPS:
        try:
            member = bot.get_chat_member(group, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception:
            return False
    return True

# ==========================================
# কিবোর্ড ও বাটন
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
        link = f"https://t.me/{group.replace('@', '')}" if group.startswith('@') else group
        markup.add(types.InlineKeyboardButton(text=f"📢 জয়েন করুন {idx}", url=link))
    markup.add(types.InlineKeyboardButton(text="✅ ভেরিফাই করুন", callback_data="check_verification"))
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ইউজার লিস্ট ও তথ্য", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton(text="🎁 রেফার বোনাস পরিবর্তন", callback_data="admin_set_bonus"))
    return markup

def payment_method_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(text="📱 বিকাশ (Bkash)", callback_data="pay_Bkash"),
        types.InlineKeyboardButton(text="📲 নগদ (Nagad)", callback_data="pay_Nagad")
    )
    return markup

# ==========================================
# কমান্ড হ্যান্ডলার
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
            "✨ **স্বাগতম!** নিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন:",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            "⚠️ বটের সমস্ত সুবিধা পেতে অবশ্যই নিচের অফিশিয়াল গ্রুপে জয়েন করতে হবে:",
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

# ==========================================
# কলব্যাক হ্যান্ডলার
# ==========================================

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
                        f"🎉 **অভিনন্দন!** নতুন ইউজার ভেরিফাই করেছে। আপনি {REFERRAL_BONUS} BDT রেফার বোনাস পেয়েছেন।"
                    )
                except Exception:
                    pass

        bot.answer_callback_query(call.id, "✅ ভেরিফিকেশন সফল হয়েছে!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(
            user_id,
            "ধন্যবাদ! আপনার অ্যাকাউন্ট সফলভাবে ভেরিফাই হয়েছে।",
            reply_markup=main_keyboard()
        )
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো সবগুলো গ্রুপে জয়েন করেননি!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    if call.data == "admin_users":
        total_registered = len(users)
        msg = f"👥 **মোট ইউজার সংখ্যা:** {total_registered}\n\n"
        msg += "📋 **ইউজার তালিকা:**\n"
        if not users:
            msg += "কোনো ইউজার নিবন্ধিত নেই।"
        else:
            for uid, info in users.items():
                msg += f"• ID: `{uid}` | Balance: {info['balance']} | Verified: {info['verified']}\n"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif call.data == "admin_set_bonus":
        user_states[call.from_user.id] = {"action": "set_bonus"}
        bot.send_message(
            call.message.chat.id,
            "✏️ **নতুন রেফার বোনাসের পরিমাণ লিখুন (শুধু সংখ্যা):**\nযেমন: 10, 15, 20"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def withdraw_method_select(call):
    user_id = call.from_user.id
    method = call.data.split("_")[1]
    
    user_states[user_id] = {
        "action": "withdraw_number",
        "method": method
    }
    
    bot.edit_message_text(
        f"📱 **{method} মেথড সিলেক্ট করেছেন।**\n\nবিকাশ/নগদ নম্বরটি লিখে সেন্ড করুন:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

# ==========================================
# মেনু ও ইনপুট মেসেজ হ্যান্ডলার
# ==========================================

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    user_data = get_user_data(user_id)

    # এডমিন ও উইথড্র ইনপুট প্রসেসিং
    if user_id in user_states:
        state = user_states[user_id]
        
        # এডমিন বোনাস চেঞ্জ ইনপুট
        if state.get("action") == "set_bonus" and user_id == ADMIN_ID:
            try:
                global REFERRAL_BONUS
                REFERRAL_BONUS = float(text)
                del user_states[user_id]
                bot.send_message(user_id, f"✅ সফলভাবে রেফার বোনাস **{REFERRAL_BONUS} BDT** সেট করা হয়েছে।", parse_mode="Markdown")
            except ValueError:
                bot.send_message(user_id, "❌ অনগ্রহ করে সঠিক সংখ্যা লিখুন (যেমন: 15)।")
            return

        # উইথড্র নম্বর ইনপুট
        elif state.get("action") == "withdraw_number":
            state["number"] = text
            state["action"] = "withdraw_amount"
            bot.send_message(
                user_id,
                f"✅ **নম্বর:** `{text}`\n\nএখন কত টাকা উইথড্র করতে চান তা লিখুন (সর্বনিম্ন ৫০০ BDT):",
                parse_mode="Markdown"
            )
            return

        # উইথড্র অ্যামাউন্ট ইনপুট
        elif state.get("action") == "withdraw_amount":
            try:
                amount = float(text)
                if amount < MIN_WITHDRAW:
                    bot.send_message(
                        user_id,
                        f"⚠️ **উইথড্র দেওয়া সম্ভব নয়!**\nসর্বনিম্ন উইথড্র অ্যামাউন্ট ৫০০ টাকা। আপনার ইনপুটকৃত অ্যামাউন্ট: {amount} BDT।"
                    )
                    return
                
                if amount > user_data["balance"]:
                    bot.send_message(
                        user_id,
                        f"❌ **অপর্যাপ্ত ব্যালেন্স!**\nআপনার বর্তমান ব্যালেন্স: {user_data['balance']} BDT।"
                    )
                    del user_states[user_id]
                    return

                # সফল উইথড্র প্রসেস
                method = state["method"]
                num = state["number"]
                user_data["balance"] -= amount
                del user_states[user_id]

                bot.send_message(
                    user_id,
                    f"🎉 **উইথড্র রিকোয়েস্ট সফল হয়েছে!**\n\n"
                    f"💳 মেথড: {method}\n"
                    f"📱 নম্বর: `{num}`\n"
                    f"💰 পরিমাণ: {amount} BDT\n\n"
                    f"এডমিন খুব শীঘ্রই আপনার পেমেন্ট প্রসেস করবেন।",
                    parse_mode="Markdown"
                )

                # এডমিনকে নোটিফিকেশন পাঠানো
                try:
                    bot.send_message(
                        ADMIN_ID,
                        f"📥 **নতুন উইথড্র রিকোয়েস্ট!**\n\n"
                        f"👤 ইউজার ID: `{user_id}`\n"
                        f"💳 মেথড: {method}\n"
                        f"📱 নম্বর: `{num}`\n"
                        f"💰 পরিমাণ: {amount} BDT",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            except ValueError:
                bot.send_message(user_id, "❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন (যেমন: 500)।")
            return

    # সাধারণ মেনু বাটন হ্যান্ডলিং
    if not check_join(user_id):
        bot.send_message(
            user_id,
            "⚠️ সেবাটি ব্যবহার করতে আগে অফিশিয়াল গ্রুপে জয়েন করুন।",
            reply_markup=verify_keyboard()
        )
        return

    if text == "👤 প্রোফাইল":
        name = message.from_user.first_name
        profile_msg = (
            f"👤 **ইউজার প্রোফাইল**\n\n"
            f"🏷 **নাম:** {name}\n"
            f"🆔 **ইউজার আইডি:** `{user_id}`\n"
            f"💰 **ব্যালেন্স:** {user_data['balance']} BDT\n"
            f"👥 **মোট রেফার:** {user_data['referrals']}"
        )
        bot.send_message(user_id, profile_msg, parse_mode="Markdown")

    elif text == "🔗 রেফার":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_msg = (
            f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
            f"🎁 প্রতি সফল রেফারে পাবেন **{REFERRAL_BONUS} BDT** (ইউজারকে ভেরিফাই করতে হবে)।"
        )
        bot.send_message(user_id, ref_msg, parse_mode="Markdown")

    elif text == "💳 উইথড্র":
        withdraw_msg = (
            f"💳 **উইথড্র সিস্টেম**\n\n"
            f"💰 আপনার বর্তমান ব্যালেন্স: **{user_data['balance']} BDT**\n"
            f"⚠️ সর্বনিম্ন উইথড্র: **৫০০ BDT**\n\n"
            f"নিচ থেকে পেমেন্ট গ্রহণের মেথড সিলেক্ট করুন:"
        )
        bot.send_message(user_id, withdraw_msg, parse_mode="Markdown", reply_markup=payment_method_keyboard())

if __name__ == "__main__":
    print("Bot starting...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending_updates=True)
