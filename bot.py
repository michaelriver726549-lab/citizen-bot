import os, json, logging, requests, datetime, random, string, re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
KEY = os.environ["GEMINI_API_KEY"].strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + KEY

submissions = {}
user_submissions = {}
states = {}

NAMSHAKHAS = "نامشخص"
BEDOON_ONVAN = "بدون عنوان"
DARYAFT_SHOD = "دریافت شد"
SEP = "─" * 30

CATEGORY_MAP = {
    "cat_complaint": "شکایت / مشکل",
    "cat_suggestion": "پیشنهاد",
    "cat_idea": "ایده",
    "cat_opinion": "نظر عمومی"
}
CATEGORY_EMOJI = {
    "cat_complaint": "❌",
    "cat_suggestion": "💡",
    "cat_idea": "🚀",
    "cat_opinion": "💬"
}
CATEGORY_PROMPTS = {
    "cat_complaint": (
        "لطفا مشکل یا شکایت خود را با جزئیات توضیح دهید.\n\n"
        "برای بررسی دقیق‌تر موارد زیر را ذکر کنید:\n"
        "• چه مشکلی رخ داده و از چه زمانی؟\n"
        "• در کجا اتفاق افتاده؟ (محله، خیابان، منطقه)\n"
        "• چه سازمانی مسئول رسیدگی است؟\n"
        "• چند نفر از این مشکل متضرر شده‌اند؟\n"
        "• آیا قبلا پیگیری شده؟"
    ),
    "cat_suggestion": (
        "لطفا پیشنهاد خود را با جزئیات شرح دهید.\n\n"
        "برای بررسی دقیق‌تر موارد زیر را ذکر کنید:\n"
        "• پیشنهاد شما دقیقا چیست؟\n"
        "• چه مشکلی را حل می‌کند؟\n"
        "• چه کسانی از آن بهره‌مند می‌شوند؟\n"
        "• آیا نمونه مشابهی در جای دیگری اجرا شده؟\n"
        "• چه منابع یا بودجه‌ای نیاز دارد؟"
    ),
    "cat_idea": (
        "لطفا ایده خود را با جزئیات شرح دهید.\n\n"
        "برای بررسی دقیق‌تر موارد زیر را ذکر کنید:\n"
        "• ایده شما چیست و چه هدفی دارد؟\n"
        "• چگونه می‌توان آن را اجرایی کرد؟\n"
        "• چه مزایا و تاثیراتی برای شهر دارد؟\n"
        "• چه چالش‌هایی در اجرا وجود دارد؟\n"
        "• در چه بازه زمانی قابل اجراست؟"
    ),
    "cat_opinion": (
        "لطفا نظر خود را بیان کنید.\n\n"
        "برای بررسی دقیق‌تر موارد زیر را ذکر کنید:\n"
        "• موضوع مورد نظر چیست؟\n"
        "• دیدگاه و نظر شما چیست؟\n"
        "• این موضوع چه تاثیری بر زندگی شما داشته؟\n"
        "• چه راه‌حل یا پیشنهادی دارید؟"
    ),
}
STATUS_MAP = {
    "received": "دریافت شد",
    "analyzing": "در حال تحلیل",
    "sent": "ارسال شد به سازمان",
    "reviewing": "در حال بررسی",
    "resolved": "حل شده",
    "rejected": "رد شده"
}
WELCOME = (
    "به سامانه ارتباط مردمی خوش آمدید 🏛\n\n"
    "از طریق این سامانه می‌توانید:\n"
    "• مشکلات و شکایات را گزارش دهید\n"
    "• پیشنهادات و ایده‌های خود را ثبت کنید\n"
    "• وضعیت درخواست‌های قبلی را پیگیری کنید\n\n"
    "لطفا یک گزینه را انتخاب کنید:"
)

def gen_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_state(uid):
    return states.get(uid, {"step": None, "data": {}})

def set_state(uid, step, data=None):
    states[uid] = {"step": step, "data": data or {}}

def clear_state(uid):
    states.pop(uid, None)

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ثبت مشکل جدید", callback_data="new_issue")],
        [InlineKeyboardButton("📌 پیگیری درخواست‌ها", callback_data="track")]
    ])

def category_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ شکایت / مشکل", callback_data="cat_complaint")],
        [InlineKeyboardButton("💡 پیشنهاد", callback_data="cat_suggestion")],
        [InlineKeyboardButton("🚀 ایده", callback_data="cat_idea")],
        [InlineKeyboardButton("💬 نظر عمومی", callback_data="cat_opinion")],
        [InlineKeyboardButton("🏠 منو اصلی", callback_data="main_menu")]
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منو اصلی", callback_data="main_menu")]])

async def start(u, c):
    clear_state(u.effective_user.id)
    await u.message.reply_text(WELCOME, reply_markup=main_kb())

async def handle_callback(u, c):
    q = u.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "main_menu":
        clear_state(uid)
        await q.message.reply_text(WELCOME, reply_markup=main_kb())
        return

    if data == "new_issue":
        set_state(uid, "choose_category")
        await q.message.reply_text("نوع درخواست خود را انتخاب کنید:", reply_markup=category_kb())
        return

    if data in CATEGORY_MAP:
        set_state(uid, "typing_issue", {"category_key": data, "category": CATEGORY_MAP[data]})
        emoji = CATEGORY_EMOJI[data]
        name = CATEGORY_MAP[data]
        prompt = CATEGORY_PROMPTS[data]
        await q.message.reply_text(f"دسته‌بندی: {emoji} {name}\n\n{prompt}", reply_markup=back_kb())
        return

    if data == "track":
        user_codes = user_submissions.get(uid, [])
        if not user_codes:
            await q.message.reply_text("شما هنوز هیچ درخواستی ثبت نکرده‌اید.", reply_markup=main_kb())
            return
        buttons = []
        for code in reversed(user_codes[-10:]):
            sub = submissions.get(code, {})
            title = sub.get("title", BEDOON_ONVAN)[:25]
            status = STATUS_MAP.get(sub.get("status", "received"), DARYAFT_SHOD)
            buttons.append([InlineKeyboardButton(f"{title} - {status}", callback_data=f"view_{code}")])
        buttons.append([InlineKeyboardButton("🏠 منو اصلی", callback_data="main_menu")])
        await q.message.reply_text("درخواست‌های شما:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("view_"):
        code = data[5:]
        sub = submissions.get(code)
        if not sub:
            await q.message.reply_text("درخواست پیدا نشد.", reply_markup=main_kb())
            return
        urgency = sub.get("urgency", 5)
        ue = "🔴" if urgency >= 8 else "🟡" if urgency >= 5 else "🟢"
        status = STATUS_MAP.get(sub.get("status", "received"), DARYAFT_SHOD)
        title = sub.get("title", "-")
        cat = sub.get("category", "-")
        loc = sub.get("location", NAMSHAKHAS)
        dt = sub.get("date", "-")
        summ = sub.get("summary", "-")
        text = (
            f"🔖 کد پیگیری: {code}\n"
            f"📌 عنوان: {title}\n"
            f"🗂 دسته: {cat}\n"
            f"📍 موقعیت: {loc}\n"
            f"📅 تاریخ ثبت: {dt}\n"
            f"📋 وضعیت: {status}\n\n"
            f"📝 خلاصه:\n{summ}"
        )
        await q.message.reply_text(text, reply_markup=back_kb())
        return

async def handle_text(u, c):
    uid = u.effective_user.id
    text = u.message.text
    s = get_state(uid)

    if s["step"] != "typing_issue":
        await u.message.reply_text(WELCOME, reply_markup=main_kb())
        return

    if len(text.strip()) < 15:
        await u.message.reply_text("لطفا توضیح کامل‌تری ارائه دهید (حداقل 15 کاراکتر).", reply_markup=back_kb())
        return

    category = s["data"].get("category", "عمومی")
    category_key = s["data"].get("category_key", "cat_opinion")
    msg = await u.message.reply_text("لطفا صبر کنید، درخواست شما در حال ثبت و تحلیل است...")

    try:
        analysis = analyze_with_gemini(text, category)

        if not analysis.get("is_valid", True):
            reason = analysis.get("invalid_reason", NAMSHAKHAS)
            await msg.edit_text(
                f"پیام شما قابل پیگیری نیست.\n\nدلیل: {reason}\n\nلطفا متن واقعی‌تری با جزئیات بیشتر ارسال کنید.",
                reply_markup=back_kb()
            )
            return

        code = gen_code()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        username = u.effective_user.username or NAMSHAKHAS
        sub = {
            "code": code, "user_id": uid, "username": username,
            "category": category, "category_key": category_key,
            "original_text": text,
            "title": analysis.get("title", BEDOON_ONVAN),
            "issue_type": analysis.get("issue_type", "-"),
            "subcategory": analysis.get("subcategory", "-"),
            "urgency": analysis.get("urgency", 5),
            "impact": analysis.get("impact", 5),
            "priority_score": analysis.get("priority_score", 50),
            "location": analysis.get("location", NAMSHAKHAS),
            "responsible_department": analysis.get("responsible_department", NAMSHAKHAS),
            "summary": analysis.get("summary", "-"),
            "status": "received", "date": now
        }
        submissions[code] = sub
        user_submissions.setdefault(uid, []).append(code)
        clear_state(uid)

        summ = sub["summary"]
        response = (
            "✅ درخواست شما با موفقیت ثبت شد.\n\n"
            f"🔖 کد پیگیری: {code}\n\n"
            f"📋 خلاصه:\n{summ}\n\n"
            "📨 درخواست شما به سازمان مربوطه ارسال خواهد شد."
        )
        await msg.edit_text(response, reply_markup=main_kb())
        await send_to_channel(c, sub)

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("خطایی رخ داد. لطفا دوباره تلاش کنید.", reply_markup=back_kb())

def analyze_with_gemini(text, category):
    prompt = (
        "تو سیستم هوش مصنوعی تحلیل بازخورد شهروندی هستی.\n"
        "پیام شهروند را تحلیل کن. فقط JSON خروجی بده:\n\n"
        "{\n"
        '  "title": "عنوان کوتاه حداکثر 8 کلمه",\n'
        '  "issue_type": "یکی از: زیرساخت | حمل‌ونقل | بهداشت | آموزش | محیط زیست | اقتصاد | خدمات دولتی | سایر",\n'
        '  "subcategory": "دسته‌بندی دقیق‌تر مثل آب، برق، جاده",\n'
        '  "urgency": عدد 1 تا 10,\n'
        '  "impact": عدد 1 تا 10,\n'
        '  "priority_score": عدد 1 تا 100,\n'
        '  "location": "شهر یا منطقه اگر ذکر شده وگرنه نامشخص",\n'
        '  "responsible_department": "نام کامل سازمان مسئول به فارسی",\n'
        '  "summary": "خلاصه 2 جمله‌ای از مشکل",\n'
        '  "is_valid": true یا false,\n'
        '  "invalid_reason": "اگر is_valid=false دلیل را بنویس وگرنه خالی"\n'
        "}\n\n"
        f"دسته: {category}\n"
        f"پیام شهروند: {text}"
    )
    r = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    match = re.search(r"{[\s\S]*?}", raw)
    if match:
        return json.loads(match.group())
    return json.loads(raw)

async def send_to_channel(c, sub):
    target = CHANNEL_ID if CHANNEL_ID else ADMIN_CHAT_ID
    if not target:
        return
    try:
        urgency = sub["urgency"]
        ue = "🔴" if urgency >= 8 else "🟡" if urgency >= 5 else "🟢"
        priority = sub.get("priority_score", 0)
        code = sub["code"]
        cat = sub["category"]
        title = sub["title"]
        itype = sub["issue_type"]
        subcat = sub["subcategory"]
        dept = sub["responsible_department"]
        loc = sub["location"]
        dt = sub["date"]
        summ = sub["summary"]
        orig = sub["original_text"][:600]
        text = (
            f"📨 گزارش جدید شهروندی\n"
            f"{SEP}\n"
            f"🔖 کد: {code}\n"
            f"🗂 دسته: {cat}\n"
            f"📌 عنوان: {title}\n"
            f"🔹 نوع: {itype} ← {subcat}\n"
            f"🏛 سازمان: {dept}\n"
            f"⚡ اورژانسیت: {ue} {urgency}/10\n"
            f"🎯 امتیاز: {priority}/100\n"
            f"📍 موقعیت: {loc}\n"
            f"📅 تاریخ: {dt}\n"
            f"{SEP}\n"
            f"📝 خلاصه:\n{summ}\n\n"
            f"💬 متن اصلی:\n{orig}"
        )
        await c.bot.send_message(chat_id=target, text=text)
    except Exception as e:
        logger.error(f"Channel send error: {e}")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
logger.info("Citizen bot v2 started!")
app.run_polling()
