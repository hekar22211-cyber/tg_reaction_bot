import asyncio
import logging
import os
import re
import sqlite3

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Message,
)

# ======================= সেটিংস =======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8940347817:AAHSxRX9uJley9PKJ2BMQmcvXWbUHBCtFvc")   # নতুন টোকেন এখানে বসান
OWNER_ID = 8454171811              # মূল এডমিন (একে বাদ দেওয়া যায় না)
DEFAULT_CHANNEL = "https://t.me/Gaming_Rahim_YT"   # প্রথমবার চালালে এটা যোগ হবে
DEFAULT_BONUS = 5.0
DEFAULT_MIN_WITHDRAW = 50.0
CURRENCY = "৳"
# =======================================================

logging.basicConfig(level=logging.INFO)
router = Router()
BOT_USERNAME = ""

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


# ----------------------------- ইউজার কিবোর্ড -----------------------------
def join_kb():
    rows = [[Btn(text=f"📢 {c['title']} জয়েন করুন", url=c["url"])]
            for c in db.execute("SELECT * FROM channels")]
    rows.append([Btn(text="✅ ভেরিফাই", callback_data="verify")])
    return Kb(inline_keyboard=rows)


def main_kb():
    return Kb(inline_keyboard=[
        [Btn(text="💰 ব্যালেন্স", callback_data="balance"),
         Btn(text="🔗 রেফার লিংক", callback_data="refer")],
        [Btn(text="💸 উইথড্র", callback_data="withdraw")],
    ])


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


# ----------------------------- /start -----------------------------
@router.message(CommandStart())
async def start(msg: Message, command: CommandObject, state: FSMContext):
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

    if user["banned"]:
        return await msg.answer("🚫 আপনি ব্যান হয়েছেন।")
    if user["verified"]:
        return await msg.answer("🏠 মেইন মেনু", reply_markup=main_kb())

    await msg.answer(
        "👋 স্বাগতম!\n\nবট ব্যবহার করতে নিচের সব চ্যানেল/গ্রুপে জয়েন করে "
        "<b>✅ ভেরিফাই</b> বাটনে চাপ দিন।",
        reply_markup=join_kb(), parse_mode="HTML")


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("বাতিল করা হয়েছে।")


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
        try:
            await bot.send_message(ref, f"🎉 আপনার রেফারে একজন ভেরিফাই করেছে! +{b}{CURRENCY} বোনাস যোগ হয়েছে।")
        except Exception:
            pass

    await cb.message.edit_text("✅ ভেরিফাই সম্পন্ন! এখন বট ব্যবহার করতে পারবেন।")
    await cb.message.answer("🏠 মেইন মেনু", reply_markup=main_kb())
    await cb.answer()


# ----------------------------- ইউজার মেনু -----------------------------
async def guard(cb: CallbackQuery):
    user = get_user(cb.from_user.id)
    if not user or not user["verified"] or user["banned"]:
        await cb.answer("আগে /start দিয়ে ভেরিফাই করুন", show_alert=True)
        return None
    return user


@router.callback_query(F.data == "balance")
async def balance(cb: CallbackQuery):
    user = await guard(cb)
    if not user:
        return
    await cb.message.answer(
        f"💰 ব্যালেন্স: <b>{user['balance']:.2f}{CURRENCY}</b>\n"
        f"👥 মোট রেফার: <b>{user['referrals']}</b>", parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "refer")
async def refer(cb: CallbackQuery):
    user = await guard(cb)
    if not user:
        return
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{cb.from_user.id}"
    await cb.message.answer(
        f"🔗 আপনার রেফার লিংক:\n{link}\n\nপ্রতি সফল রেফারে পাবেন {bonus()}{CURRENCY}\n"
        "(বন্ধু জয়েন করে ভেরিফাই করলে তবেই বোনাস)")
    await cb.answer()


# ----------------------------- উইথড্র -----------------------------
class WithdrawState(StatesGroup):
    amount = State()
    method = State()


@router.callback_query(F.data == "withdraw")
async def withdraw(cb: CallbackQuery, state: FSMContext):
    user = await guard(cb)
    if not user:
        return
    if user["balance"] < min_wd():
        return await cb.answer(
            f"মিনিমাম উইথড্র {min_wd()}{CURRENCY}। আপনার ব্যালেন্স {user['balance']:.2f}{CURRENCY}",
            show_alert=True)
    await state.set_state(WithdrawState.amount)
    await cb.message.answer(f"কত টাকা উইথড্র করবেন? (মিনিমাম {min_wd()})\nবাতিল করতে /cancel")
    await cb.answer()


@router.message(WithdrawState.amount)
async def w_amount(msg: Message, state: FSMContext):
    try:
        amt = float(msg.text)
    except (TypeError, ValueError):
        return await msg.answer("শুধু সংখ্যা লিখুন।")
    user = get_user(msg.from_user.id)
    if amt < min_wd() or amt > user["balance"]:
        return await msg.answer("অবৈধ পরিমাণ। আবার লিখুন।")
    await state.update_data(amount=amt)
    await state.set_state(WithdrawState.method)
    await msg.answer("পেমেন্ট মেথড ও নম্বর লিখুন (যেমন: bKash 01XXXXXXXXX)")


@router.message(WithdrawState.method)
async def w_method(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amt = data["amount"]
    uid = msg.from_user.id
    user = get_user(uid)
    if amt > user["balance"]:
        await state.clear()
        return await msg.answer("ব্যালেন্স যথেষ্ট নয়।")

    db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    cur = db.execute("INSERT INTO withdrawals (user_id, amount, method) VALUES (?,?,?)", (uid, amt, msg.text))
    db.commit()
    wid = cur.lastrowid
    await state.clear()
    await msg.answer("✅ উইথড্র রিকোয়েস্ট জমা হয়েছে। এডমিন যাচাই করবেন।")

    kb = Kb(inline_keyboard=[[Btn(text="✅ Approve", callback_data=f"wd_ok_{wid}"),
                              Btn(text="❌ Reject", callback_data=f"wd_no_{wid}")]])
    for a in all_admin_ids():
        try:
            await bot.send_message(
                a, f"💸 নতুন উইথড্র #{wid}\nইউজার: {uid} (@{msg.from_user.username})\n"
                   f"পরিমাণ: {amt}{CURRENCY}\nমেথড: {msg.text}", reply_markup=kb)
        except Exception:
            pass


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
        text = f"✅ আপনার {w['amount']}{CURRENCY} উইথড্র অ্যাপ্রুভ হয়েছে।"
    else:
        db.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
        db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (w["amount"], w["user_id"]))
        text = f"❌ আপনার {w['amount']}{CURRENCY} উইথড্র রিজেক্ট হয়েছে। টাকা ব্যালেন্সে ফেরত গেছে।"
    db.commit()
    try:
        await bot.send_message(w["user_id"], text)
    except Exception:
        pass
    await cb.message.edit_text(cb.message.text + f"\n\n➡️ {action.upper()} by {cb.from_user.id}")
    await cb.answer("সম্পন্ন")


# ======================= এডমিন প্যানেল =======================
class AdminState(StatesGroup):
    add_channel = State()
    add_admin = State()
    set_bonus = State()
    set_min = State()
    broadcast = State()


def panel_kb():
    return Kb(inline_keyboard=[
        [Btn(text="📢 জয়েন চ্যানেল/গ্রুপ", callback_data="adm:channels")],
        [Btn(text="👮 এডমিন ম্যানেজ", callback_data="adm:admins")],
        [Btn(text="🎁 রেফার বোনাস", callback_data="adm:bonus"),
         Btn(text="💵 মিনিমাম উইথড্র", callback_data="adm:minwd")],
        [Btn(text="📊 স্ট্যাটস", callback_data="adm:stats"),
         Btn(text="📣 ব্রডকাস্ট", callback_data="adm:bcast")],
        [Btn(text="⏳ পেন্ডিং উইথড্র", callback_data="adm:wds")],
    ])


def back_row():
    return [Btn(text="⬅️ ব্যাক", callback_data="adm:main")]


@router.message(Command("admin"))
async def admin_cmd(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer(
        "🛠 <b>এডমিন প্যানেল</b>\n\nঅন্যান্য কমান্ড:\n"
        "/addbal ID পরিমাণ\n/cutbal ID পরিমাণ\n/ban ID\n/unban ID\n/user ID",
        reply_markup=panel_kb(), parse_mode="HTML")


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
        return await cb.message.edit_text("🛠 <b>এডমিন প্যানেল</b>", reply_markup=panel_kb(), parse_mode="HTML")

    # ---- চ্যানেল ----
    if act == "channels":
        rows = [[Btn(text=f"🗑 {c['title']} ({c['chat_id']})", callback_data=f"adm:delch:{c['id']}")]
                for c in db.execute("SELECT * FROM channels")]
        rows.append([Btn(text="➕ নতুন যোগ করুন", callback_data="adm:addch")])
        rows.append(back_row())
        return await cb.message.edit_text(
            "📢 <b>জয়েন চ্যানেল/গ্রুপ</b>\nমুছতে নামের উপর চাপ দিন।",
            reply_markup=Kb(inline_keyboard=rows), parse_mode="HTML")

    if act == "addch":
        await state.set_state(AdminState.add_channel)
        return await cb.message.answer(
            "নতুন চ্যানেল/গ্রুপের লিংক পাঠান।\n\n"
            "• পাবলিক: <code>https://t.me/name</code> বা <code>@name</code>\n"
            "• প্রাইভেট: <code>-100123456789|https://t.me/+invitelink</code>\n\n"
            "⚠️ বটকে আগে ওই চ্যানেল/গ্রুপে এডমিন বানাতে হবে।\nবাতিল: /cancel",
            parse_mode="HTML")

    if act == "delch":
        db.execute("DELETE FROM channels WHERE id=?", (parts[2],))
        db.commit()
        cb.data = "adm:channels"
        return await admin_cb(cb, state, bot)

    # ---- এডমিন ----
    if act == "admins":
        rows = [[Btn(text=f"👑 {OWNER_ID} (মালিক)", callback_data="adm:noop")]]
        for a in db.execute("SELECT user_id FROM admins"):
            rows.append([Btn(text=f"🗑 {a['user_id']}", callback_data=f"adm:deladm:{a['user_id']}")])
        rows.append([Btn(text="➕ নতুন এডমিন", callback_data="adm:addadm")])
        rows.append(back_row())
        return await cb.message.edit_text(
            "👮 <b>এডমিন লিস্ট</b>\nবাদ দিতে আইডির উপর চাপ দিন।",
            reply_markup=Kb(inline_keyboard=rows), parse_mode="HTML")

    if act == "addadm":
        await state.set_state(AdminState.add_admin)
        return await cb.message.answer("নতুন এডমিনের Telegram ID পাঠান (সংখ্যা)।\nবাতিল: /cancel")

    if act == "deladm":
        db.execute("DELETE FROM admins WHERE user_id=?", (parts[2],))
        db.commit()
        cb.data = "adm:admins"
        return await admin_cb(cb, state, bot)

    # ---- বোনাস / মিনিমাম ----
    if act == "bonus":
        await state.set_state(AdminState.set_bonus)
        return await cb.message.answer(f"বর্তমান বোনাস: {bonus()}{CURRENCY}\nনতুন পরিমাণ লিখুন।\nবাতিল: /cancel")

    if act == "minwd":
        await state.set_state(AdminState.set_min)
        return await cb.message.answer(f"বর্তমান মিনিমাম: {min_wd()}{CURRENCY}\nনতুন পরিমাণ লিখুন।\nবাতিল: /cancel")

    # ---- স্ট্যাটস ----
    if act == "stats":
        total = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        ver = db.execute("SELECT COUNT(*) c FROM users WHERE verified=1").fetchone()["c"]
        pend = db.execute("SELECT COUNT(*) c FROM withdrawals WHERE status='pending'").fetchone()["c"]
        return await cb.message.edit_text(
            f"📊 মোট ইউজার: {total}\n✅ ভেরিফাইড: {ver}\n⏳ পেন্ডিং উইথড্র: {pend}",
            reply_markup=Kb(inline_keyboard=[back_row()]))

    # ---- ব্রডকাস্ট ----
    if act == "bcast":
        await state.set_state(AdminState.broadcast)
        return await cb.message.answer("যে মেসেজ সবাইকে পাঠাবেন সেটা লিখুন।\nবাতিল: /cancel")

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
                f"💸 #{w['id']}\nইউজার: {w['user_id']}\nপরিমাণ: {w['amount']}{CURRENCY}\nমেথড: {w['method']}",
                reply_markup=kb)


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
        return await msg.answer(f"❌ চ্যানেল পাওয়া যায়নি বা বট ঢুকতে পারছে না।\n{e}")
    db.execute("INSERT INTO channels (title, chat_id, url) VALUES (?,?,?)", (title, chat_id, url))
    db.commit()
    await state.clear()
    await msg.answer(f"✅ যোগ হয়েছে: {title}", reply_markup=panel_kb())


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
        await bot.send_message(uid, "👮 আপনাকে এডমিন বানানো হয়েছে। /admin দিন।")
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
    await msg.answer(f"✅ রেফার বোনাস এখন {v}{CURRENCY}", reply_markup=panel_kb())


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
    await msg.answer(f"✅ মিনিমাম উইথড্র এখন {v}{CURRENCY}", reply_markup=panel_kb())


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


# ---- এডমিন কমান্ড ----
@router.message(Command("addbal", "cutbal"))
async def change_bal(msg: Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid, amt = command.args.split()
        uid, amt = int(uid), float(amt)
    except Exception:
        return await msg.answer("ব্যবহার: /addbal ID পরিমাণ")
    if not get_user(uid):
        return await msg.answer("ইউজার পাওয়া যায়নি")
    if command.command == "cutbal":
        amt = -amt
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    db.commit()
    await msg.answer(f"✅ সম্পন্ন। নতুন ব্যালেন্স: {get_user(uid)['balance']:.2f}")


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
    await msg.answer(
        f"ID: {u['user_id']}\nনাম: {u['full_name']}\nইউজারনেম: @{u['username']}\n"
        f"ভেরিফাইড: {bool(u['verified'])}\nব্যালেন্স: {u['balance']:.2f}\n"
        f"রেফার: {u['referrals']}\nরেফারার: {u['referrer_id']}\nব্যান: {bool(u['banned'])}")


# ----------------------------- রান -----------------------------
async def main():
    global BOT_USERNAME
    bot = Bot(BOT_TOKEN)
    BOT_USERNAME = (await bot.get_me()).username
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
