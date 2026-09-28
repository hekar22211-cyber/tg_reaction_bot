import os
import telebot
from telebot import types
from dotenv import load_dotenv

# .env ফাইল থেকে টোকেন লোড করা
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "8940347817:AAHOQY5ZzDYPsf2PG6KHRVSMDFK0sk39bRc")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8454171811"))

bot = telebot.TeleBot(TOKEN)

# ==========================================
# কনফিগারেশন ও মেমোরি ডাটাবেস
# ==========================================

# আপনার চ্যানেল/গ্রুপের ইউজারনেমগুলো এখানে দিন
ADMIN_GROUPS = ["@channel_or_group_1", "@channel_or_group_2"]

# রেফারেল বোনাস পরিমাণ (টাকা)
REFERRAL_BONUS = 10.0

# ইউজার ডাটা সংরক্ষণের মেমোরি
users = {}

def get_user_data(user_id):
    """ইউজার ডাটা থাকলে রিটার্ন করে, না থাকলে নতুন তৈরি করে"""
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
    """ইউজার নির্দিষ্ট চ্যানেল/গ্রুপে জয়েন করেছে কিনা চেক করে"""
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
    """মূল মেনু কিবোর্ড"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_profile = types.KeyboardButton("👤 প্রোফাইল")
    btn_refer = types.KeyboardButton("🔗 রেফার")
    btn_withdraw = types.KeyboardButton("💳 উইথড্র")
    markup.add(btn_profile, btn_refer, btn_withdraw)
    return markup

def verify_keyboard():
    """গ্রুপ জয়েন ও ভেরিফাই বাটন"""
    markup = types.InlineKeyboardMarkup()
    for idx, group in enumerate(ADMIN_GROUPS, 1):
        link = f"https://t.me/{group.replace('@', '')}" if group.startswith('@') else group
        markup.add(types.InlineKeyboardButton(text=f"📢 জয়েন করুন {idx}", url=link))
    markup.add(types.InlineKeyboardButton(text="✅ ভেরিফাই করুন", callback_data="check_verification"))
    return markup

def admin_keyboard():
    """এডমিন প্যানেল কিবোর্ড"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ইউজার লিস্ট ও তথ্য", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton(text="🔗 গ্রুপ লিংকসমূহ", callback_data="admin_groups"))
    return markup

# ==========================================
# কমান্ড হ্যান্ডলার
# ==========================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    # রেফারেল আইডি প্রসেস করা
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
            "স্বাগতম! নিচের মেনু থেকে অপশন সিলেক্ট করুন:",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            "⚠️ বটের সমস্ত সুবিধা পেতে অবশ্যই আমাদের নিচের ২টি গ্রুপে জয়েন করতে হবে:",
            reply_markup=verify_keyboard()
        )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "⚙️ **এডমিন প্যানেল:**",
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
            
            # রেফার করার জন্য বোনাস প্রদান
            if user_data['ref_by'] and user_data['ref_by'] in users:
                ref_user = users[user_data['ref_by']]
                ref_user['balance'] += REFERRAL_BONUS
                ref_user['referrals'] += 1
                try:
                    bot.send_message(
                        user_data['ref_by'],
                        f"🎉 নতুন ইউজার ভেরিফাই করেছে! আপনি {REFERRAL_BONUS} BDT রেফার বোনাস পেয়েছেন।"
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
        msg = f"👥 **মোট ইউজার সংখ্যা:** {total_registered}\n"
        msg += "📈 **Monthly users:** 3753\n\n"
        msg += "📋 **ইউজার তালিকা:**\n"
        if not users:
            msg += "কোনো ইউজার নিবন্ধিত নেই।"
        else:
            for uid, info in users.items():
                msg += f"• ID: `{uid}` | Verified: {info['verified']}\n"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif call.data == "admin_groups":
        msg = "🔗 **বর্তমান জয়েনিং গ্রুপসমূহ:**\n\n"
        for idx, grp in enumerate(ADMIN_GROUPS, 1):
            msg += f"{idx}. {grp}\n"
        bot.send_message(call.message.chat.id, msg)

# ==========================================
# মেনু মেসেজ হ্যান্ডলার
# ==========================================

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    # ভেরিফিকেশন চেক
    if not check_join(user_id):
        bot.send_message(
            user_id,
            "⚠️ সেবাটি ব্যবহার করতে আগে গ্রুপে জয়েন করুন।",
            reply_markup=verify_keyboard()
        )
        return

    text = message.text

    if text == "👤 প্রোফাইল":
        name = message.from_user.first_name
        profile_msg = (
            f"👤 **ইউজার প্রোফাইল**\n\n"
            f"🏷 **নাম:** {name}\n"
            f"🆔 **ইউজার আইডি:** `{user_id}`\n"
            f"💰 **ব্যালেন্স:** {user_data['balance']} BDT\n"
            f"👥 **মোট রেফার:** {user_data['referrals']}\n"
            f"📉 **Monthly user:** 3753"
        )
        bot.send_message(user_id, profile_msg, parse_mode="Markdown")

    elif text == "🔗 রেফার":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_msg = (
            f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
            f"🎁 প্রতি সফল রেফারে পাবেন {REFERRAL_BONUS} BDT (ইউজারকে গ্রুপে জয়েন করে ভেরিফাই করতে হবে)।"
        )
        bot.send_message(user_id, ref_msg, parse_mode="Markdown")

    elif text == "💳 উইথড্র":
        withdraw_msg = (
            f"💳 **উইথড্র সিস্টেম**\n\n"
            f"💰 আপনার বর্তমান ব্যালেন্স: {user_data['balance']} BDT\n"
            f"⚠️ সর্বনিম্ন উইথড্র: ৫০ BDT\n\n"
            f"উইথড্র করতে এডমিনের সাথে যোগাযোগ করুন।"
        )
        bot.send_message(user_id, withdraw_msg)

if __name__ == "__main__":
    print("Bot starting...")
    bot.infinity_polling()
