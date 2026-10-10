import asyncio
import html
import logging
import os
import re
import sqlite3

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Message,
    KeyboardButton, ReplyKeyboardMarkup,
)

# ======================= সেটিংস =======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8940347817:AAFVPMrQYDaAZbE7ms4MLcIJ_Ou0Ki746nI")   # Render Environment-এ BOT_TOKEN দিন
OWNER_ID = 8454171811              # মূল এডমিন (একে বাদ দেওয়া যায় না)
DEFAULT_CHANNEL = "https://t.me/Gaming_Rahim_YT"   # প্রথমবার চালালে এটা যোগ হবে
DEFAULT_BONUS = 5.0
DEFAULT_MIN_WITHDRAW = 500.0
CURRENCY = "৳"
# =======================================================

BTN_PROFILE = "👤 প্রোফাইল"
BTN_REF = "🔗 রেফার লিংক"
BTN_WD = "💸 উইথড্র"
BTN_ADMIN = "🛠 এডমিন প্যানেল"
LINE = "━━━━━━━━━━━━━━"

logging.basicConfig(level=logging.INFO)
router = Router()
BOT_USERNAME = ""
esc = html.escape

# ----------------------------- ডাটাবেস -----------------------------
db = sqlite3.connect("bot.db")
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
    referrer_id INTEGER, verified INTEGER DEFAULT 0,
    balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0, banned INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
    method TEXT, status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, chat_id TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
""")
db.commit()


def fmt(x):
    return f"{x:g}"


def get_setting(key, default):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return float(r["value"]) if r else default


def set_setting(key, value):
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
    db.commit()


def get_user(uid):
    return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def is_admin(uid):
    return uid == OWNER_ID or db.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,)).fetchone() is not None


def all_admin_ids():
    ids = {OWNER_ID}
    ids.update(r["user_id"] for r in db.execute("SELECT user_id FROM admins"))
    return list(ids)


def bonus():
    return get_setting("bonus", DEFAULT_BONUS)


def min_wd():
    return get_setting("min_withdraw", DEFAULT_MIN_WITHDRAW)


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name or "User")}</a>'


async def notify_admins(bot: Bot, text, kb=None):
    for a in all_admin_ids():
        try:
            await bot.send_message(a, text, reply_markup=kb)
        except Exception:
            pass


def parse_channel_input(text):
    """'@name' বা 'https://t.me/name' (পাবলিক) অথবা 'chat_id|invite_link' (প্রাইভেট)"""
    text = text.strip()
    if "|" in text:
        chat_id, url = [p.strip() for p in text.split("|", 1)]
        return chat_id, url
    m = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    name = m.group(1) if m else text.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{4,}", name):
        return None, None
    return "@" + name, f"https://t.me/{name}"


def chat_ref(chat_id):
    return int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id


# প্রথমবার ডিফল্ট চ্যানেল যোগ
if not db.execute("SELECT 1 FROM channels").fetchone():
    cid, url = parse_channel_input(DEFAULT_CHANNEL)
    db.execute("INSERT INTO channels (title, chat_id, url) VALUES (?,?,?)", ("Channel", cid, url))
    db.commit()


# ----------------------------- কিবোর্ড -----------------------------
def join_kb():
    rows = [[Btn(text=f"📢 {c['title']} জয়েন করুন", url=c["url"])]
            for c in db.execute("SELECT * FROM channels")]
    rows.append([Btn(text="✅ ভেরিফাই করুন", callback_data="verify")])
    return Kb(inline_keyboard=rows)


def main_kb(uid=0):
    """নিচে স্থায়ীভাবে থাকা মেইন বাটন"""
    rows = [
        [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_REF)],
        [KeyboardButton(text=BTN_WD)],
    ]
    if is_admin(uid):
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


async def is_joined_all(bot: Bot, uid: int) -> bool:
    for c in db.execute("SELECT * FROM channels"):
        try:
            m = await bot.get_chat_member(chat_ref(c["chat_id"]), uid)
            if m.status in ("left", "kicked"):
                return False
        except Exception as e:
            logging.warning("মেম্বার চেক ব্যর্থ %s: %s", c["chat_id"], e)
            return False
    return True


JOIN_TEXT = (
    "👋 <b>স্বাগতম!</b>\n"
    f"{LINE}\n"
    "বট ব্যবহার করতে নিচের সব চ্যানেল/গ্রুপে জয়েন করুন,\n"
    "তারপর <b>✅ ভেরিফাই করুন</b> বাটনে চাপ দিন।"
)


# ----------------------------- /start -----------------------------
@router.message(CommandStart())
async def start(msg: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()
    uid = msg.from_user.id
    user = get_user(uid)

    if not user:
        ref = None
        if command.args and command.args.startswith("ref_"):
            try:
                ref = int(command.args[4:])
            except ValueError:
                ref = None
            if ref == uid or not get_user(ref or 0):
                ref = None
        db.execute(
            "INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?,?,?,?)",
            (uid, msg.from_user.username, msg.from_user.full_name, ref))
        db.commit()
        user = get_user(uid)

        if ref:
            rf = get_user(ref)
            await notify_admins(
                bot,
                "🆕 <b>নতুন রেফার জয়েন</b>\n"
                f"{LINE}\n"
                f"👤 নতুন ইউজার: {mention(uid, msg.from_user.full_name)} (<code>{uid}</code>)\n"
                f"🔗 রেফারার: {mention(ref, rf['full_name'])} (<code>{ref}</code>)\n"
                "⏳ স্ট্যাটাস: ভেরিফাই বাকি")

    # এডমিনকে ভেরিফাই ছাড়াই ঢুকতে দেওয়া হয়
    if is_admin(uid) and not user["verified"]:
        db.execute("UPDATE users SET verified=1 WHERE user_id=?", (uid,))
        db.commit()
        user = get_user(uid)

    if user["banned"] and not is_admin(uid):
        return await msg.answer("🚫 আপনি ব্যান হয়েছেন।")
    if user["verified"]:
        return await msg.answer(
            f"🏠 <b>মেইন মেনু</b>\n{LINE}\nস্বাগতম, {esc(msg.from_user.full_name)}!\nনিচের বাটন থেকে বেছে নিন 👇",
            reply_markup=main_kb(uid))

    await msg.answer(JOIN_TEXT, reply_markup=join_kb())


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❎ বাতিল করা হয়েছে।", reply_markup=main_kb(msg.from_user.id))


@router.callback_query(F.data == "home")
async def go_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer("🏠 <b>মেইন মেনু</b>", reply_markup=main_kb(cb.from_user.id))
    await cb.answer()


# ----------------------------- ভেরিফাই -----------------------------
@router.callback_query(F.data == "verify")
async def verify(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    user = get_user(uid)
    if not user:
        return await cb.answer("আগে /start দিন", show_alert=True)
    if user["banned"]:
        return await cb.answer("🚫 আপনি ব্যান হয়েছেন", show_alert=True)
    if user["verified"]:
        return await cb.answer("আপনি আগেই ভেরিফাইড", show_alert=True)
    if not await is_joined_all(bot, uid):
        return await cb.answer("❌ সব চ্যানেল/গ্রুপে জয়েন করুন, তারপর ভেরিফাই করুন", show_alert=True)

    db.execute("UPDATE users SET verified=1 WHERE user_id=?", (uid,))
    ref = user["referrer_id"]
    b = bonus()
    if ref:
        db.execute("UPDATE users SET balance=balance+?, referrals=referrals+1 WHERE user_id=?", (b, ref))
    db.commit()

    if ref:
        rf = get_user(ref)
        try:
            await bot.send_message(
                ref,
                f"🎉 <b>রেফার সফল!</b>\n{LINE}\n"
                f"আপনার রেফারে {esc(cb.from_user.full_name)} ভেরিফাই করেছে।\n"
                f"💰 বোনাস: <b>+{fmt(b)}{CURRENCY}</b>")
        except Exception:
            pass
        await notify_admins(
            bot,
            "✅ <b>রেফার ভেরিফাইড</b>\n"
            f"{LINE}\n"
            f"👤 ইউজার: {mention(uid, cb.from_user.full_name)} (<code>{uid}</code>)\n"
            f"🔗 রেফারার: {mention(ref, rf['full_name'])} (<code>{ref}</code>)\n"
            f"💰 বোনাস দেওয়া হয়েছে: {fmt(b)}{CURRENCY}")

    await cb.message.edit_text("✅ <b>ভেরিফাই সম্পন্ন!</b>\nএখন বট ব্যবহার করতে পারবেন।")
    await cb.message.answer("🏠 <b>মেইন মেনু</b>\nনিচের বাটন থেকে বেছে নিন 👇", reply_markup=main_kb(uid))
    await cb.answer()


# ----------------------------- গার্ড -----------------------------
async def guard_msg(msg: Message):
    user = get_user(msg.from_user.id)
    if not user:
        await msg.answer("আগে /start দিন")
        return None
    if user["banned"]:
        await msg.answer("🚫 আপনি ব্যান হয়েছেন।")
        return None
    if not user["verified"]:
        await msg.answer(JOIN_TEXT, reply_markup=join_kb())
        return None
    return user


async def guard_cb(cb: CallbackQuery):
    user = get_user(cb.from_user.id)
    if not user or not user["verified"] or user["banned"]:
        await cb.answer("আগে /start দিয়ে ভেরিফাই করুন", show_alert=True)
        return None
    return user


# ----------------------------- প্রোফাইল -----------------------------
def profile_text(u):
    total = db.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (u["user_id"],)).fetchone()["c"]
    refs = db.execute(
        "SELECT user_id, full_name, verified FROM users WHERE referrer_id=? ORDER BY rowid DESC LIMIT 20",
        (u["user_id"],)).fetchall()
    uname = f"@{esc(u['username'])}" if u["username"] else "নেই"
    text = (
        "👤 <b>আপনার প্রোফাইল</b>\n"
        f"{LINE}\n"
        f"🙍 নাম: <b>{esc(u['full_name'] or '')}</b>\n"
        f"🆔 আইডি: <code>{u['user_id']}</code>\n"
        f"📛 ইউজারনেম: {uname}\n"
        f"{LINE}\n"
        f"💰 ব্যালেন্স: <b>{u['balance']:.2f}{CURRENCY}</b>\n"
        f"👥 সফল রেফার: <b>{u['referrals']}</b>\n"
        f"📨 মোট জয়েন: <b>{total}</b>\n"
        f"{LINE}\n"
        "📋 <b>রেফার লিস্ট</b>\n"
    )
    if not refs:
        text += "এখনো কেউ রেফার হয়নি।"
    else:
        for i, r in enumerate(refs, 1):
            mark = "✅" if r["verified"] else "⏳"
            text += f"{i}. {mark} {esc(r['full_name'] or 'User')}\n"
        if total > 20:
            text += f"… আরও {total - 20} জন"
        text += "\n\n✅ ভেরিফাইড  ⏳ ভেরিফাই বাকি"
    return text


@router.message(F.text == BTN_PROFILE)
async def profile(msg: Message, state: FSMContext):
    await state.clear()
    user = await guard_msg(msg)
    if not user:
        return
    await msg.answer(profile_text(user))


@router.message(F.text == BTN_REF)
async def refer(msg: Message, state: FSMContext):
    await state.clear()
    user = await guard_msg(msg)
    if not user:
        return
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{msg.from_user.id}"
    await msg.answer(
        "🔗 <b>আপনার রেফার লিংক</b>\n"
        f"{LINE}\n"
        f"<code>{link}</code>\n"
        f"{LINE}\n"
        f"🎁 প্রতি সফল রেফারে পাবেন <b>{fmt(bonus())}{CURRENCY}</b>\n"
        "বন্ধু জয়েন করে ভেরিফাই করলে তবেই বোনাস পাবেন।")


@router.message(F.text == BTN_ADMIN)
async def admin_btn(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("🛠 <b>এডমিন প্যানেল</b>", reply_markup=panel_kb())


# ----------------------------- উইথড্র -----------------------------
class WithdrawState(StatesGroup):
    number = State()
    amount = State()


@router.message(F.text == BTN_WD)
async def withdraw(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = await guard_msg(msg)
    if not user:
        return

    # ব্যালেন্স থাকুক বা না থাকুক, এডমিনের কাছে মেসেজ যাবে
    await notify_admins(
        bot,
        "💸 <b>উইথড্র বাটনে ক্লিক</b>\n"
        f"{LINE}\n"
        f"👤 {mention(user['user_id'], user['full_name'])} (<code>{user['user_id']}</code>)\n"
        f"💰 ব্যালেন্স: {user['balance']:.2f}{CURRENCY}\n"
        f"{'✅ মিনিমাম পূরণ হয়েছে' if user['balance'] >= min_wd() else '⚠️ ব্যালেন্স কম'}")

    if user["balance"] < min_wd():
        return await msg.answer(
            "❌ <b>ব্যালেন্স কম</b>\n"
            f"{LINE}\n"
            f"💰 আপনার ব্যালেন্স: {user['balance']:.2f}{CURRENCY}\n"
            f"🎯 মিনিমাম উইথড্র: {fmt(min_wd())}{CURRENCY}\n\n"
            f"আগে {fmt(min_wd())}{CURRENCY} করুন, তারপর উইথড্র দিন।")

    kb = Kb(inline_keyboard=[
        [Btn(text="🟣 বিকাশ", callback_data="wdm:bKash"),
         Btn(text="🟠 নগদ", callback_data="wdm:Nagad")],
    ])
    await msg.answer(
        f"💸 <b>উইথড্র</b>\n{LINE}\n💰 ব্যালেন্স: {user['balance']:.2f}{CURRENCY}\n\nপেমেন্ট মেথড সিলেক্ট করুন 👇",
        reply_markup=kb)


@router.callback_query(F.data.startswith("wdm:"))
async def wd_method(cb: CallbackQuery, state: FSMContext):
    user = await guard_cb(cb)
    if not user:
        return
    if user["balance"] < min_wd():
        return await cb.answer("ব্যালেন্স কম", show_alert=True)
    method = cb.data.split(":")[1]
    await state.set_state(WithdrawState.number)
    await state.update_data(method=method)
    await cb.message.edit_text(f"✅ মেথড: <b>{method}</b>")
    await cb.message.answer(
        f"📱 আপনার <b>{method}</b> নম্বর লিখুন\n(১১ ডিজিট, যেমন 01XXXXXXXXX)\n\nবাতিল করতে /cancel")
    await cb.answer()


@router.message(WithdrawState.number)
async def w_number(msg: Message, state: FSMContext):
    number = (msg.text or "").strip()
    if not re.fullmatch(r"01[3-9]\d{8}", number):
        return await msg.answer("❌ নম্বর ঠিক নেই। ১১ ডিজিটের সঠিক নম্বর লিখুন (যেমন 01712345678)।")
    await state.update_data(number=number)
    await state.set_state(WithdrawState.amount)
    user = get_user(msg.from_user.id)
    await msg.answer(
        f"💵 <b>কত টাকা উইথড্র করবেন?</b>\n{LINE}\n"
        f"মিনিমাম: {fmt(min_wd())}{CURRENCY}\n"
        f"আপনার ব্যালেন্স: {user['balance']:.2f}{CURRENCY}")


@router.message(WithdrawState.amount)
async def w_amount(msg: Message, state: FSMContext, bot: Bot):
    try:
        amt = float(msg.text)
    except (TypeError, ValueError):
        return await msg.answer("শুধু সংখ্যা লিখুন।")
    uid = msg.from_user.id
    user = get_user(uid)
    if amt < min_wd():
        return await msg.answer(f"❌ মিনিমাম {fmt(min_wd())}{CURRENCY}। আবার লিখুন।")
    if amt > user["balance"]:
        return await msg.answer(f"❌ ব্যালেন্স কম। আপনার ব্যালেন্স {user['balance']:.2f}{CURRENCY}।")

    data = await state.get_data()
    method_text = f"{data['method']} {data['number']}"
    db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    cur = db.execute("INSERT INTO withdrawals (user_id, amount, method) VALUES (?,?,?)",
                     (uid, amt, method_text))
    db.commit()
    wid = cur.lastrowid
    await state.clear()
    await msg.answer(
        "✅ <b>উইথড্র রিকোয়েস্ট জমা হয়েছে</b>\n"
        f"{LINE}\n"
        f"🧾 আইডি: #{wid}\n"
        f"💵 পরিমাণ: {fmt(amt)}{CURRENCY}\n"
        f"📱 মেথড: {esc(method_text)}\n"
        f"{LINE}\n"
        "এডমিন যাচাই করে পেমেন্ট দেবেন।",
        reply_markup=main_kb(uid))

    kb = Kb(inline_keyboard=[[Btn(text="✅ Approve", callback_data=f"wd_ok_{wid}"),
                              Btn(text="❌ Reject", callback_data=f"wd_no_{wid}")]])
    await notify_admins(
        bot,
        f"💸 <b>নতুন উইথড্র রিকোয়েস্ট #{wid}</b>\n"
        f"{LINE}\n"
        f"👤 {mention(uid, msg.from_user.full_name)} (<code>{uid}</code>)\n"
        f"💵 পরিমাণ: <b>{fmt(amt)}{CURRENCY}</b>\n"
        f"📱 মেথড: <code>{esc(method_text)}</code>\n"
        f"💰 বাকি ব্যালেন্স: {get_user(uid)['balance']:.2f}{CURRENCY}",
        kb)


@router.callback_query(F.data.startswith("wd_"))
async def wd_decide(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("আপনি এডমিন নন", show_alert=True)
    _, action, wid = cb.data.split("_")
    w = db.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not w or w["status"] != "pending":
        return await cb.answer("আগেই প্রসেস হয়েছে", show_alert=True)

    if action == "ok":
        db.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (wid,))
        text = f"✅ <b>উইথড্র অ্যাপ্রুভ</b>\n{LINE}\nআপনার {fmt(w['amount'])}{CURRENCY} উইথড্র অ্যাপ্রুভ হয়েছে।"
    else:
        db.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
        db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (w["amount"], w["user_id"]))
        text = (f"❌ <b>উইথড্র রিজেক্ট</b>\n{LINE}\n"
                f"আপনার {fmt(w['amount'])}{CURRENCY} উইথড্র রিজেক্ট হয়েছে।\nটাকা ব্যালেন্সে ফেরত গেছে।")
    db.commit()
    try:
        await bot.send_message(w["user_id"], text)
    except Exception:
        pass
    await cb.message.edit_text(
        cb.message.html_text + f"\n\n➡️ <b>{'APPROVED' if action == 'ok' else 'REJECTED'}</b> by {cb.from_user.id}")
    await cb.answer("সম্পন্ন")


# ======================= এডমিন প্যানেল =======================
class AdminState(StatesGroup):
    add_channel = State()
    add_admin = State()
    set_bonus = State()
    set_min = State()
    broadcast = State()
    um_id = State()
    um_amount = State()


def panel_kb():
    return Kb(inline_keyboard=[
        [Btn(text="👤 ইউজার ম্যানেজ (ব্যালেন্স)", callback_data="adm:users")],
        [Btn(text="📢 জয়েন চ্যানেল/গ্রুপ", callback_data="adm:channels")],
        [Btn(text="👮 এডমিন ম্যানেজ", callback_data="adm:admins")],
        [Btn(text="🎁 রেফার বোনাস", callback_data="adm:bonus"),
         Btn(text="💵 মিনিমাম উইথড্র", callback_data="adm:minwd")],
        [Btn(text="📊 স্ট্যাটস", callback_data="adm:stats"),
         Btn(text="📣 ব্রডকাস্ট", callback_data="adm:bcast")],
        [Btn(text="⏳ পেন্ডিং উইথড্র", callback_data="adm:wds")],
        [Btn(text="🏠 মেইন মেনু", callback_data="home")],
    ])


def back_row():
    return [Btn(text="⬅️ ব্যাক", callback_data="adm:main")]


@router.message(Command("admin"))
async def admin_cmd(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("🛠 <b>এডমিন প্যানেল</b>", reply_markup=panel_kb())


async def show_channels(cb: CallbackQuery):
    rows = [[Btn(text=f"🗑 {c['title']} ({c['chat_id']})", callback_data=f"adm:delch:{c['id']}")]
            for c in db.execute("SELECT * FROM channels")]
    rows.append([Btn(text="➕ নতুন যোগ করুন", callback_data="adm:addch")])
    rows.append(back_row())
    await cb.message.edit_text(
        f"📢 <b>জয়েন চ্যানেল/গ্রুপ</b>\n{LINE}\nমুছতে নামের উপর চাপ দিন।",
        reply_markup=Kb(inline_keyboard=rows))


async def show_admins(cb: CallbackQuery):
    rows = [[Btn(text=f"👑 {OWNER_ID} (মালিক)", callback_data="adm:noop")]]
    for a in db.execute("SELECT user_id FROM admins"):
        rows.append([Btn(text=f"🗑 {a['user_id']}", callback_data=f"adm:deladm:{a['user_id']}")])
    rows.append([Btn(text="➕ নতুন এডমিন", callback_data="adm:addadm")])
    rows.append(back_row())
    await cb.message.edit_text(
        f"👮 <b>এডমিন লিস্ট</b>\n{LINE}\nবাদ দিতে আইডির উপর চাপ দিন।",
        reply_markup=Kb(inline_keyboard=rows))


@router.callback_query(F.data.startswith("adm:"))
async def admin_cb(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("আপনি এডমিন নন", show_alert=True)
    parts = cb.data.split(":")
    act = parts[1]
    await cb.answer()

    if act == "noop":
        return

    if act == "main":
        await state.clear()
        return await cb.message.edit_text("🛠 <b>এডমিন প্যানেল</b>", reply_markup=panel_kb())

    # ---- ইউজার ম্যানেজ ----
    if act == "users":
        await state.set_state(AdminState.um_id)
        return await cb.message.answer(
            "👤 যে ইউজারের ব্যালেন্স বদলাবেন তার <b>Telegram ID</b> পাঠান।\nবাতিল: /cancel")

    # ---- চ্যানেল ----
    if act == "channels":
        return await show_channels(cb)

    if act == "addch":
        await state.set_state(AdminState.add_channel)
        return await cb.message.answer(
            "নতুন চ্যানেল/গ্রুপের লিংক পাঠান।\n\n"
            "• পাবলিক: <code>https://t.me/name</code> বা <code>@name</code>\n"
            "• প্রাইভেট: <code>-100123456789|https://t.me/+invitelink</code>\n\n"
            "⚠️ বটকে আগে ওই চ্যানেল/গ্রুপে এডমিন বানাতে হবে।\nবাতিল: /cancel")

    if act == "delch":
        db.execute("DELETE FROM channels WHERE id=?", (parts[2],))
        db.commit()
        return await show_channels(cb)

    # ---- এডমিন ----
    if act == "admins":
        return await show_admins(cb)

    if act == "addadm":
        await state.set_state(AdminState.add_admin)
        return await cb.message.answer("নতুন এডমিনের Telegram ID পাঠান (সংখ্যা)।\nবাতিল: /cancel")

    if act == "deladm":
        db.execute("DELETE FROM admins WHERE user_id=?", (parts[2],))
        db.commit()
        return await show_admins(cb)

    # ---- বোনাস / মিনিমাম ----
    if act == "bonus":
        await state.set_state(AdminState.set_bonus)
        return await cb.message.answer(f"🎁 বর্তমান বোনাস: {fmt(bonus())}{CURRENCY}\nনতুন পরিমাণ লিখুন।\nবাতিল: /cancel")

    if act == "minwd":
        await state.set_state(AdminState.set_min)
        return await cb.message.answer(f"💵 বর্তমান মিনিমাম: {fmt(min_wd())}{CURRENCY}\nনতুন পরিমাণ লিখুন।\nবাতিল: /cancel")

    # ---- স্ট্যাটস ----
    if act == "stats":
        total = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        ver = db.execute("SELECT COUNT(*) c FROM users WHERE verified=1").fetchone()["c"]
        pend = db.execute("SELECT COUNT(*) c FROM withdrawals WHERE status='pending'").fetchone()["c"]
        bal = db.execute("SELECT COALESCE(SUM(balance),0) s FROM users").fetchone()["s"]
        return await cb.message.edit_text(
            f"📊 <b>স্ট্যাটস</b>\n{LINE}\n"
            f"👥 মোট ইউজার: {total}\n✅ ভেরিফাইড: {ver}\n"
            f"💰 ইউজারদের মোট ব্যালেন্স: {bal:.2f}{CURRENCY}\n⏳ পেন্ডিং উইথড্র: {pend}",
            reply_markup=Kb(inline_keyboard=[back_row()]))

    # ---- ব্রডকাস্ট ----
    if act == "bcast":
        await state.set_state(AdminState.broadcast)
        return await cb.message.answer("📣 যে মেসেজ সবাইকে পাঠাবেন সেটা লিখুন।\nবাতিল: /cancel")

    # ---- পেন্ডিং উইথড্র ----
    if act == "wds":
        pend = db.execute("SELECT * FROM withdrawals WHERE status='pending'").fetchall()
        if not pend:
            return await cb.message.edit_text("কোনো পেন্ডিং উইথড্র নেই।", reply_markup=Kb(inline_keyboard=[back_row()]))
        await cb.message.edit_text(f"⏳ {len(pend)} টি পেন্ডিং, নিচে পাঠানো হলো।", reply_markup=Kb(inline_keyboard=[back_row()]))
        for w in pend:
            kb = Kb(inline_keyboard=[[Btn(text="✅ Approve", callback_data=f"wd_ok_{w['id']}"),
                                      Btn(text="❌ Reject", callback_data=f"wd_no_{w['id']}")]])
            await cb.message.answer(
                f"💸 <b>#{w['id']}</b>\nইউজার: <code>{w['user_id']}</code>\n"
                f"পরিমাণ: {fmt(w['amount'])}{CURRENCY}\nমেথড: <code>{esc(w['method'])}</code>",
                reply_markup=kb)


# ---- ইউজার ম্যানেজ (ব্যালেন্স কমবেশি) ----
def um_card(u):
    uname = f"@{esc(u['username'])}" if u["username"] else "নেই"
    return (
        "👤 <b>ইউজার তথ্য</b>\n"
        f"{LINE}\n"
        f"🙍 নাম: {mention(u['user_id'], u['full_name'])}\n"
        f"🆔 আইডি: <code>{u['user_id']}</code>\n"
        f"📛 ইউজারনেম: {uname}\n"
        f"💰 ব্যালেন্স: <b>{u['balance']:.2f}{CURRENCY}</b>\n"
        f"👥 সফল রেফার: {u['referrals']}\n"
        f"🔗 রেফারার: {u['referrer_id'] or 'নেই'}\n"
        f"✅ ভেরিফাইড: {'হ্যাঁ' if u['verified'] else 'না'}\n"
        f"🚫 ব্যান: {'হ্যাঁ' if u['banned'] else 'না'}"
    )


def um_kb(u):
    uid = u["user_id"]
    ban_btn = (Btn(text="♻️ আনব্যান", callback_data=f"um:unban:{uid}") if u["banned"]
               else Btn(text="🚫 ব্যান", callback_data=f"um:ban:{uid}"))
    return Kb(inline_keyboard=[
        [Btn(text="➕ ব্যালেন্স যোগ", callback_data=f"um:add:{uid}"),
         Btn(text="➖ ব্যালেন্স কমান", callback_data=f"um:cut:{uid}")],
        [ban_btn],
        [Btn(text="⬅️ প্যানেল", callback_data="adm:main")],
    ])


@router.message(AdminState.um_id)
async def st_um_id(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except (ValueError, AttributeError):
        return await msg.answer("শুধু সংখ্যার আইডি পাঠান।")
    u = get_user(uid)
    if not u:
        return await msg.answer("❌ এই আইডির ইউজার পাওয়া যায়নি। আবার পাঠান বা /cancel দিন।")
    await state.clear()
    await msg.answer(um_card(u), reply_markup=um_kb(u))


@router.callback_query(F.data.startswith("um:"))
async def um_cb(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("আপনি এডমিন নন", show_alert=True)
    _, act, uid = cb.data.split(":")
    uid = int(uid)
    u = get_user(uid)
    if not u:
        return await cb.answer("ইউজার পাওয়া যায়নি", show_alert=True)

    if act in ("add", "cut"):
        await state.set_state(AdminState.um_amount)
        await state.update_data(action=act, target=uid)
        word = "যোগ" if act == "add" else "কমানো"
        await cb.message.answer(f"কত টাকা {word} করবেন? সংখ্যা লিখুন।\nবাতিল: /cancel")
        return await cb.answer()

    if act in ("ban", "unban"):
        db.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if act == "ban" else 0, uid))
        db.commit()
        u = get_user(uid)
        await cb.message.edit_text(um_card(u), reply_markup=um_kb(u))
        return await cb.answer("সম্পন্ন")


@router.message(AdminState.um_amount)
async def st_um_amount(msg: Message, state: FSMContext, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    try:
        amt = float(msg.text)
        if amt <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return await msg.answer("শুধু ধনাত্মক সংখ্যা লিখুন।")
    data = await state.get_data()
    uid, act = data["target"], data["action"]
    u = get_user(uid)
    if not u:
        await state.clear()
        return await msg.answer("ইউজার পাওয়া যায়নি।")

    if act == "add":
        new = u["balance"] + amt
        note = f"➕ আপনার ব্যালেন্সে <b>{fmt(amt)}{CURRENCY}</b> যোগ করা হয়েছে।"
    else:
        new = max(0.0, u["balance"] - amt)
        note = f"➖ আপনার ব্যালেন্স থেকে <b>{fmt(amt)}{CURRENCY}</b> কমানো হয়েছে।"
    db.execute("UPDATE users SET balance=? WHERE user_id=?", (new, uid))
    db.commit()
    await state.clear()

    u = get_user(uid)
    await msg.answer("✅ সম্পন্ন!\n\n" + um_card(u), reply_markup=um_kb(u))
    try:
        await bot.send_message(uid, f"💰 <b>ব্যালেন্স আপডেট</b>\n{LINE}\n{note}\nবর্তমান ব্যালেন্স: {new:.2f}{CURRENCY}")
    except Exception:
        pass


# ---- এডমিন ইনপুট হ্যান্ডলার ----
@router.message(AdminState.add_channel)
async def st_add_channel(msg: Message, state: FSMContext, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    chat_id, url = parse_channel_input(msg.text or "")
    if not chat_id:
        return await msg.answer("ফরম্যাট ঠিক নেই। আবার পাঠান বা /cancel দিন।")
    try:
        chat = await bot.get_chat(chat_ref(chat_id))
        me = await bot.get_chat_member(chat_ref(chat_id), bot.id)
        if me.status not in ("administrator", "creator"):
            return await msg.answer("❌ বট ওই চ্যানেল/গ্রুপে এডমিন নয়। আগে এডমিন বানিয়ে আবার পাঠান।")
        title = chat.title or chat_id
    except Exception as e:
        return await msg.answer(f"❌ চ্যানেল পাওয়া যায়নি বা বট ঢুকতে পারছে না।\n{esc(str(e))}")
    db.execute("INSERT INTO channels (title, chat_id, url) VALUES (?,?,?)", (title, chat_id, url))
    db.commit()
    await state.clear()
    await msg.answer(f"✅ যোগ হয়েছে: {esc(title)}", reply_markup=panel_kb())


@router.message(AdminState.add_admin)
async def st_add_admin(msg: Message, state: FSMContext, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except (ValueError, AttributeError):
        return await msg.answer("শুধু সংখ্যার আইডি পাঠান।")
    db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))
    db.commit()
    await state.clear()
    await msg.answer(f"✅ {uid} এখন এডমিন।", reply_markup=panel_kb())
    try:
        await bot.send_message(uid, "👮 আপনাকে এডমিন বানানো হয়েছে। /start দিন।")
    except Exception:
        pass


@router.message(AdminState.set_bonus)
async def st_bonus(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        v = float(msg.text)
    except (TypeError, ValueError):
        return await msg.answer("শুধু সংখ্যা লিখুন।")
    set_setting("bonus", v)
    await state.clear()
    await msg.answer(f"✅ রেফার বোনাস এখন {fmt(v)}{CURRENCY}", reply_markup=panel_kb())


@router.message(AdminState.set_min)
async def st_min(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        v = float(msg.text)
    except (TypeError, ValueError):
        return await msg.answer("শুধু সংখ্যা লিখুন।")
    set_setting("min_withdraw", v)
    await state.clear()
    await msg.answer(f"✅ মিনিমাম উইথড্র এখন {fmt(v)}{CURRENCY}", reply_markup=panel_kb())


@router.message(AdminState.broadcast)
async def st_broadcast(msg: Message, state: FSMContext, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    ok = fail = 0
    for r in db.execute("SELECT user_id FROM users WHERE banned=0").fetchall():
        try:
            await bot.copy_message(r["user_id"], msg.chat.id, msg.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await msg.answer(f"📣 পাঠানো হয়েছে: {ok}, ব্যর্থ: {fail}")


# ---- এডমিন কমান্ড (শর্টকাট) ----
@router.message(Command("addbal", "cutbal"))
async def change_bal(msg: Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid, amt = command.args.split()
        uid, amt = int(uid), float(amt)
    except Exception:
        return await msg.answer("ব্যবহার: /addbal ID পরিমাণ")
    u = get_user(uid)
    if not u:
        return await msg.answer("ইউজার পাওয়া যায়নি")
    new = u["balance"] + amt if command.command == "addbal" else max(0.0, u["balance"] - amt)
    db.execute("UPDATE users SET balance=? WHERE user_id=?", (new, uid))
    db.commit()
    await msg.answer(f"✅ সম্পন্ন। নতুন ব্যালেন্স: {new:.2f}")


@router.message(Command("ban", "unban"))
async def ban(msg: Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(command.args)
    except Exception:
        return await msg.answer("ব্যবহার: /ban ID")
    db.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if command.command == "ban" else 0, uid))
    db.commit()
    await msg.answer("✅ সম্পন্ন")


@router.message(Command("user"))
async def user_info(msg: Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    try:
        u = get_user(int(command.args))
    except Exception:
        return await msg.answer("ব্যবহার: /user ID")
    if not u:
        return await msg.answer("ইউজার পাওয়া যায়নি")
    await msg.answer(um_card(u), reply_markup=um_kb(u))


# ----------------------------- রান (Render-এর জন্য ওয়েব সার্ভারসহ) -----------------------------
async def health(request):
    return web.Response(text="OK")


async def main():
    global BOT_USERNAME
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    BOT_USERNAME = (await bot.get_me()).username

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
