import os, json, logging, requests, datetime, random, string, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
KEY = os.environ["GEMINI_API_KEY"].strip()
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + KEY

submissions = {}
user_submissions = {}
states = {}

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

STATUS_MAP = {
    "received": "دریافت شد",
    "analyzing": "در حال تحلیل",
    "sent": "ارسال شد به سازمان",
    "reviewing": "در حال بررسی",
    "resolved": "حل شده",
    "rejected": "رد شده"
}

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

WELCOME = (
    "به سامانه ارتباط مردمی خوش آمدید 🏛\n\n"
    "از طریق این سامانه می‌توانید:\n"
    "مشکلات و شکایات را گزارش دهید\n"
    "پیشنهادات و ایده‌های خود را ثبت کنید\n"
    "وضعیت درخواست‌های قبلی را پیگیری کنید\n\n"
    "لطفا یک گزینه را انتخاب کنید:"
)

async def start(u, c):
    uid = u.effective_user.id
    clear_state(uid)
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
        await q.message.reply_text(
            f"دسته‌بندی: {CATEGORY_EMOJI[data]} {CATEGORY_MAP[data]}\n\n"
            "لطفا مشکل یا درخواست خود را با جزئیات توضیح دهید.\n\n"
            "برای تحلیل بهتر موارد زیر را ذکر کنید:\n"
            "چه اتفاقی افتاده؟\n"
            "از چه زمانی؟\n"
            "در کجا؟\n"
            "چه سازمانی مسئول است؟\n"
            "چند نفر تحت تاثیر است؟",
            reply_markup=back_kb()
        )
        return

    if data == "track":
        user_codes = user_submissions.get(uid, [])
        if not user_codes:
            await q.message.reply_text("شما هنوز هیچ درخواستی ثبت نکرده‌اید.", reply_markup=main_kb())
            return
        buttons = []
        for code in reversed(user_codes[-10:]):
            sub = submissions.get(code, {})
            title = sub.get("title", "بدون عنوان")[:25]
            status = STATUS_MAP.get(sub.get("status", "received"), "دریافت شد")
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
        urgency_emoji = "🔴" if urgency >= 8 else "🟡" if urgency >= 5 else "🟢"
        status = STATUS_MAP.get(sub.get("status", "received"), "دریافت شد")
        text = (
            f"کد پیگیری: {code}\n"
            f"عنوان: {sub.get('title', '-')}\n"
            f"دسته: {sub.get('category', '-')}\n"
            f"نوع مشکل: {sub.get('issue_type', '-')} - {sub.get('subcategory', '-')}\n"
            f"سازمان مسئول: {sub.get('responsible_department', '-')}\n"
            f"اورژانسیت: {urgency_emoji} {urgency}/10\n"
            f"امتیاز اولویت: {sub.get('priority_score', '-')}/100\n"
            f"موقعیت: {sub.get('location', 'نامشخص')}\n"
            f"تاریخ ثبت: {sub.get('date', '-')}\n"
            f"وضعیت: {status}\n\n"
            f"خلاصه هوش مصنوعی:\n{sub.get('summary', '-')}"
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
        await u.message.reply_text(
            "لطفا توضیح کامل‌تری ارائه دهید (حداقل 15 کاراکتر).",
            reply_markup=back_kb()
        )
        return

    category = s["data"].get("category", "عمومی")
    category_key = s["data"].get("category_key", "cat_opinion")

    msg = await u.message.reply_text("در حال تحلیل پیام شما توسط هوش مصنوعی...")

    try:
        analysis = analyze_with_gemini(text, category)

        if not analysis.get("is_valid", True):
            await msg.edit_text(
                f"پیام شما قابل پیگیری نیست.\n\nدلیل: {analysis.get('invalid_reason', 'نامشخص')}\n\nلطفا مشکل واقعی خود را با جزئیات بیشتر توضیح دهید.",
                reply_markup=back_kb()
            )
            return

        code = gen_code()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        sub = {
            "code": code,
            "user_id": uid,
            "username": u.effective_user.username or "ناشناس",
            "category": category,
            "category_key": category_key,
            "original_text": text,
            "title": analysis.get("title", "بدون عنوان"),
            "issue_type": analysis.get("issue_type", "-"),
            "subcategory": analysis.get("subcategory", "-"),
            "urgency": analysis.get("urgency", 5),
            "impact": analysis.get("impact", 5),
            "priority_score": analysis.get("priority_score", 50),
            "location": analysis.get("location", "نامشخص"),
            "responsible_department": analysis.get("responsible_department", "نامشخص"),
            "summary": analysis.get("summary", "-"),
            "status": "received",
            "date": now
        }

        submissions[code] = sub
        if uid not in user_submissions:
            user_submissions[uid] = []
        user_submissions[uid].append(code)
        clear_state(uid)

        urgency = sub["urgency"]
        urgency_emoji = "🔴" if urgency >= 8 else "🟡" if urgency >= 5 else "🟢"

        response = (
            f"درخواست شما با موفقیت ثبت شد.\n\n"
            f"کد پیگیری: {code}\n\n"
            f"نتیجه تحلیل هوش مصنوعی:\n"
            f"عنوان: {sub['title']}\n"
            f"نوع: {sub['issue_type']} - {sub['subcategory']}\n"
            f"سازمان مسئول: {sub['responsible_department']}\n"
            f"اورژانسیت: {urgency_emoji} {urgency}/10\n"
            f"امتیاز اولویت: {sub['priority_score']}/100\n"
            f"موقعیت: {sub['location']}\n\n"
            f"خلاصه:\n{sub['summary']}\n\n"
            f"درخواست شما به سازمان مربوطه ارسال خواهد شد."
        )

        await msg.edit_text(response, reply_markup=main_kb())

        if ADMIN_CHAT_ID:
            await send_to_admin(c, sub)

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("خطایی در تحلیل پیام رخ داد. لطفا دوباره تلاش کنید.", reply_markup=back_kb())

def analyze_with_gemini(text, category):
    prompt = f"""تو سیستم هوش مصنوعی تحلیل بازخورد شهروندی هستی.
پیام شهروند را تحلیل کن. فقط JSON خروجی بده:

{{
  "title": "عنوان کوتاه حداکثر 8 کلمه",
  "issue_type": "یکی از: زیرساخت | حمل‌ونقل | بهداشت | آموزش | محیط زیست | اقتصاد | خدمات دولتی | سایر",
  "subcategory": "دسته‌بندی دقیق‌تر مثل آب، برق، جاده، اینترنت",
  "urgency": عدد 1 تا 10,
  "impact": عدد 1 تا 10,
  "priority_score": عدد 1 تا 100,
  "location": "شهر یا منطقه اگر ذکر شده وگرنه نامشخص",
  "responsible_department": "نام کامل سازمان یا وزارتخانه مسئول به فارسی",
  "summary": "خلاصه 2 جمله‌ای از مشکل",
  "is_valid": true یا false,
  "invalid_reason": "اگر is_valid=false دلیل را بنویس وگرنه خالی"
}}

دسته: {category}
پیام شهروند: {text}"""

    r = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    match = re.search(r'{[^}]*}|{[\s\S]*}', raw)
    if match:
        return json.loads(match.group())
    return json.loads(raw)

async def send_to_admin(c, sub):
    try:
        urgency = sub["urgency"]
        urgency_emoji = "🔴" if urgency >= 8 else "🟡" if urgency >= 5 else "🟢"
        text = (
            f"گزارش جدید شهروندی\n\n"
            f"کد: {sub['code']}\n"
            f"دسته: {sub['category']}\n"
            f"عنوان: {sub['title']}\n"
            f"نوع: {sub['issue_type']} - {sub['subcategory']}\n"
            f"سازمان مسئول: {sub['responsible_department']}\n"
            f"اورژانسیت: {urgency_emoji} {urgency}/10\n"
            f"امتیاز اولویت: {sub['priority_score']}/100\n"
            f"موقعیت: {sub['location']}\n"
            f"تاریخ: {sub['date']}\n\n"
            f"خلاصه:\n{sub['summary']}\n\n"
            f"متن اصلی:\n{sub['original_text'][:400]}"
        )
        await c.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)
    except Exception as e:
        logger.error(f"Admin send error: {e}")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
logger.info("Citizen bot started!")
app.run_polling()
