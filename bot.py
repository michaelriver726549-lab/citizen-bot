import os, json, logging, requests, datetime, random, string, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
KEY = os.environ["GEMINI_API_KEY"].strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()  # @channel_username or -100xxxxxxxxxx
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + KEY

submissions = {}
user_submissions = {}
states = {}

CATEGORY_MAP = {
    "cat_complaint": "\u0634\u06a9\u0627\u06cc\u062a / \u0645\u0634\u06a9\u0644",
    "cat_suggestion": "\u067e\u06cc\u0634\u0646\u0647\u0627\u062f",
    "cat_idea": "\u0627\u06cc\u062f\u0647",
    "cat_opinion": "\u0646\u0638\u0631 \u0639\u0645\u0648\u0645\u06cc"
}

CATEGORY_EMOJI = {
    "cat_complaint": "\u274c",
    "cat_suggestion": "\U0001f4a1",
    "cat_idea": "\U0001f680",
    "cat_opinion": "\U0001f4ac"
}

CATEGORY_PROMPTS = {
    "cat_complaint": (
        "\u0644\u0637\u0641\u0627 \u0645\u0634\u06a9\u0644 \u06cc\u0627 \u0634\u06a9\u0627\u06cc\u062a \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u062a\u0648\u0636\u06cc\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0686\u0647 \u0645\u0634\u06a9\u0644\u06cc \u0631\u062e \u062f\u0627\u062f\u0647 \u0648 \u0627\u0632 \u0686\u0647 \u0632\u0645\u0627\u0646\u06cc\u061f\n"
        "\u2022 \u062f\u0631 \u06a9\u062c\u0627 \u0627\u062a\u0641\u0627\u0642 \u0627\u0641\u062a\u0627\u062f\u0647\u061f (\u0645\u062d\u0644\u0647\u060c \u062e\u06cc\u0627\u0628\u0627\u0646\u060c \u0645\u0646\u0637\u0642\u0647)\n"
        "\u2022 \u0686\u0647 \u0633\u0627\u0632\u0645\u0627\u0646\u06cc \u0645\u0633\u0626\u0648\u0644 \u0631\u0633\u06cc\u062f\u06af\u06cc \u0627\u0633\u062a\u061f\n"
        "\u2022 \u0686\u0646\u062f \u0646\u0641\u0631 \u0627\u0632 \u0627\u06cc\u0646 \u0645\u0634\u06a9\u0644 \u0645\u062a\u0636\u0631\u0631 \u0634\u062f\u0647\u200c\u0627\u0646\u062f\u061f\n"
        "\u2022 \u0622\u06cc\u0627 \u0642\u0628\u0644\u0627\u064b \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0634\u062f\u0647\u061f"
    ),
    "cat_suggestion": (
        "\u0644\u0637\u0641\u0627 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0634\u0631\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0634\u0645\u0627 \u062f\u0642\u06cc\u0642\u0627\u064b \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u0686\u0647 \u0645\u0634\u06a9\u0644\u06cc \u0631\u0627 \u062d\u0644 \u0645\u06cc\u200c\u06a9\u0646\u062f\u061f\n"
        "\u2022 \u0686\u0647 \u06a9\u0633\u0627\u0646\u06cc \u0627\u0632 \u0622\u0646 \u0628\u0647\u0631\u0647\u200c\u0645\u0646\u062f \u0645\u06cc\u200c\u0634\u0648\u0646\u062f\u061f\n"
        "\u2022 \u0622\u06cc\u0627 \u0646\u0645\u0648\u0646\u0647 \u0645\u0634\u0627\u0628\u0647\u06cc \u062f\u0631 \u062c\u0627\u06cc \u062f\u06cc\u06af\u0631\u06cc \u0627\u062c\u0631\u0627 \u0634\u062f\u0647\u061f\n"
        "\u2022 \u0686\u0647 \u0645\u0646\u0627\u0628\u0639 \u06cc\u0627 \u0628\u0648\u062f\u062c\u0647\u06cc \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f\u061f"
    ),
    "cat_idea": (
        "\u0644\u0637\u0641\u0627 \u0627\u06cc\u062f\u0647 \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0634\u0631\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0627\u06cc\u062f\u0647 \u0634\u0645\u0627 \u0686\u06cc\u0633\u062a \u0648 \u0686\u0647 \u0647\u062f\u0641\u06cc \u062f\u0627\u0631\u062f\u061f\n"
        "\u2022 \u0686\u06af\u0648\u0646\u0647 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646 \u0622\u0646 \u0631\u0627 \u0627\u062c\u0631\u0627\u06cc\u06cc \u06a9\u0631\u062f\u061f\n"
        "\u2022 \u0686\u0647 \u0645\u0632\u0627\u06cc\u0627 \u0648 \u062a\u0627\u062b\u06cc\u0631\u0627\u062a\u06cc \u0628\u0631\u0627\u06cc \u0634\u0647\u0631 \u062f\u0627\u0631\u062f\u061f\n"
        "\u2022 \u0686\u0647 \u0686\u0627\u0644\u0634\u200c\u0647\u0627\u06cc\u06cc \u062f\u0631 \u0627\u062c\u0631\u0627 \u0648\u062c\u0648\u062f \u062f\u0627\u0631\u062f\u061f\n"
        "\u2022 \u062f\u0631 \u0686\u0647 \u0628\u0627\u0632\u0647 \u0632\u0645\u0627\u0646\u06cc \u0642\u0627\u0628\u0644 \u0627\u062c\u0631\u0627\u0633\u062a\u061f"
    ),
    "cat_opinion": (
        "\u0644\u0637\u0641\u0627 \u0646\u0638\u0631 \u062e\u0648\u062f \u0631\u0627 \u0628\u06cc\u0627\u0646 \u06a9\u0646\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0645\u0648\u0636\u0648\u0639 \u0645\u0648\u0631\u062f \u0646\u0638\u0631 \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u062f\u06cc\u062f\u06af\u0627\u0647 \u0648 \u0646\u0638\u0631 \u0634\u0645\u0627 \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u0627\u06cc\u0646 \u0645\u0648\u0636\u0648\u0639 \u0686\u0647 \u062a\u0627\u062b\u06cc\u0631\u06cc \u0628\u0631 \u0632\u0646\u062f\u06af\u06cc \u0634\u0645\u0627 \u062f\u0627\u0634\u062a\u0647\u061f\n"
        "\u2022 \u0686\u0647 \u0631\u0627\u0647\u200c\u062d\u0644 \u06cc\u0627 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f\u06cc \u062f\u0627\u0631\u06cc\u062f\u061f"
    ),
}

STATUS_MAP = {
    "received": "\u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f",
    "analyzing": "\u062f\u0631 \u062d\u0627\u0644 \u062a\u062d\u0644\u06cc\u0644",
    "sent": "\u0627\u0631\u0633\u0627\u0644 \u0634\u062f \u0628\u0647 \u0633\u0627\u0632\u0645\u0627\u0646",
    "reviewing": "\u062f\u0631 \u062d\u0627\u0644 \u0628\u0631\u0631\u0633\u06cc",
    "resolved": "\u062d\u0644 \u0634\u062f\u0647",
    "rejected": "\u0631\u062f \u0634\u062f\u0647"
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
        [InlineKeyboardButton("\U0001f4dd \u062b\u0628\u062a \u0645\u0634\u06a9\u0644 \u062c\u062f\u06cc\u062f", callback_data="new_issue")],
        [InlineKeyboardButton("\U0001f4cc \u067e\u06cc\u06af\u06cc\u0631\u06cc \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627", callback_data="track")]
    ])

def category_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u274c \u0634\u06a9\u0627\u06cc\u062a / \u0645\u0634\u06a9\u0644", callback_data="cat_complaint")],
        [InlineKeyboardButton("\U0001f4a1 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f", callback_data="cat_suggestion")],
        [InlineKeyboardButton("\U0001f680 \u0627\u06cc\u062f\u0647", callback_data="cat_idea")],
        [InlineKeyboardButton("\U0001f4ac \u0646\u0638\u0631 \u0639\u0645\u0648\u0645\u06cc", callback_data="cat_opinion")],
        [InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc", callback_data="main_menu")]
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc", callback_data="main_menu")]])

WELCOME = (
    "\u0628\u0647 \u0633\u0627\u0645\u0627\u0646\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 \u0645\u0631\u062f\u0645\u06cc \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f \U0001f3db\n\n"
    "\u0627\u0632 \u0637\u0631\u06cc\u0642 \u0627\u06cc\u0646 \u0633\u0627\u0645\u0627\u0646\u0647 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u06cc\u062f:\n"
    "\u2022 \u0645\u0634\u06a9\u0644\u0627\u062a \u0648 \u0634\u06a9\u0627\u06cc\u0627\u062a \u0631\u0627 \u06af\u0632\u0627\u0631\u0634 \u062f\u0647\u06cc\u062f\n"
    "\u2022 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f\u0627\u062a \u0648 \u0627\u06cc\u062f\u0647\u200c\u0647\u0627\u06cc \u062e\u0648\u062f \u0631\u0627 \u062b\u0628\u062a \u06a9\u0646\u06cc\u062f\n"
    "\u2022 \u0648\u0636\u0639\u06cc\u062a \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627\u06cc \u0642\u0628\u0644\u06cc \u0631\u0627 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u06a9\u0646\u06cc\u062f\n\n"
    "\u0644\u0637\u0641\u0627 \u06cc\u06a9 \u06af\u0632\u06cc\u0646\u0647 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:"
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
        await q.message.reply_text("\u0646\u0648\u0639 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062e\u0648\u062f \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:", reply_markup=category_kb())
        return

    if data in CATEGORY_MAP:
        set_state(uid, "typing_issue", {"category_key": data, "category": CATEGORY_MAP[data]})
        prompt_text = CATEGORY_PROMPTS[data]
        await q.message.reply_text(
            f"\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc: {CATEGORY_EMOJI[data]} {CATEGORY_MAP[data]}\n\n{prompt_text}",
            reply_markup=back_kb()
        )
        return

    if data == "track":
        user_codes = user_submissions.get(uid, [])
        if not user_codes:
            await q.message.reply_text("\u0634\u0645\u0627 \u0647\u0646\u0648\u0632 \u0647\u06cc\u0686 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u062b\u0628\u062a \u0646\u06a9\u0631\u062f\u0647\u200c\u0627\u06cc\u062f.", reply_markup=main_kb())
            return
        buttons = []
        for code in reversed(user_codes[-10:]):
            sub = submissions.get(code, {})
            title = sub.get("title", "\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646")[:25]
            status = STATUS_MAP.get(sub.get("status", "received"), "\u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f")
            buttons.append([InlineKeyboardButton(f"{title} - {status}", callback_data=f"view_{code}")])
        buttons.append([InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc", callback_data="main_menu")])
        await q.message.reply_text("\u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627\u06cc \u0634\u0645\u0627:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("view_"):
        code = data[5:]
        sub = submissions.get(code)
        if not sub:
            await q.message.reply_text("\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.", reply_markup=main_kb())
            return
        urgency = sub.get("urgency", 5)
        urgency_emoji = "\U0001f534" if urgency >= 8 else "\U0001f7e1" if urgency >= 5 else "\U0001f7e2"
        status = STATUS_MAP.get(sub.get("status", "received"), "\u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f")
        text = (
            f"\U0001f516 \u06a9\u062f \u067e\u06cc\u06af\u06cc\u0631\u06cc: {code}\n"
            f"\U0001f4cc \u0639\u0646\u0648\u0627\u0646: {sub.get('title', '-')}\n"
            f"\U0001f5c2 \u062f\u0633\u062a\u0647: {sub.get('category', '-')}\n"
            f"\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a: {sub.get('location', '\u0646\u0627\u0645\u0634\u062e\u0635')}\n"
            f"\U0001f4c5 \u062a\u0627\u0631\u06cc\u062e \u062b\u0628\u062a: {sub.get('date', '-')}\n"
            f"\U0001f4cb \u0648\u0636\u0639\u06cc\u062a: {status}\n\n"
            f"\U0001f4dd \u062e\u0644\u0627\u0635\u0647:\n{sub.get('summary', '-')}"
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
            "\u0644\u0637\u0641\u0627 \u062a\u0648\u0636\u06cc\u062d \u06a9\u0627\u0645\u0644\u200c\u062a\u0631\u06cc \u0627\u0631\u0627\u0626\u0647 \u062f\u0647\u06cc\u062f (\u062d\u062f\u0627\u0642\u0644 15 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631).",
            reply_markup=back_kb()
        )
        return

    category = s["data"].get("category", "\u0639\u0645\u0648\u0645\u06cc")
    category_key = s["data"].get("category_key", "cat_opinion")

    msg = await u.message.reply_text("\u0644\u0637\u0641\u0627 \u0635\u0628\u0631 \u06a9\u0646\u06cc\u062f\u060c \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u062f\u0631 \u062d\u0627\u0644 \u062b\u0628\u062a \u0648 \u062a\u062d\u0644\u06cc\u0644 \u0627\u0633\u062a...")

    try:
        analysis = analyze_with_gemini(text, category)

        if not analysis.get("is_valid", True):
            await msg.edit_text(
                f"\u067e\u06cc\u0627\u0645 \u0634\u0645\u0627 \u0642\u0627\u0628\u0644 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0646\u06cc\u0633\u062a.\n\n\u062f\u0644\u06cc\u0644: {analysis.get('invalid_reason', '\u0646\u0627\u0645\u0634\u062e\u0635')}\n\n\u0644\u0637\u0641\u0627 \u0645\u062a\u0646 \u0648\u0627\u0642\u0639\u06cc\u200c\u062a\u0631\u06cc \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0628\u06cc\u0634\u062a\u0631 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.",
                reply_markup=back_kb()
            )
            return

        code = gen_code()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        sub = {
            "code": code,
            "user_id": uid,
            "username": u.effective_user.username or "\u0646\u0627\u0634\u0646\u0627\u0633",
            "category": category,
            "category_key": category_key,
            "original_text": text,
            "title": analysis.get("title", "\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646"),
            "issue_type": analysis.get("issue_type", "-"),
            "subcategory": analysis.get("subcategory", "-"),
            "urgency": analysis.get("urgency", 5),
            "impact": analysis.get("impact", 5),
            "priority_score": analysis.get("priority_score", 50),
            "location": analysis.get("location", "\u0646\u0627\u0645\u0634\u062e\u0635"),
            "responsible_department": analysis.get("responsible_department", "\u0646\u0627\u0645\u0634\u062e\u0635"),
            "summary": analysis.get("summary", "-"),
            "status": "received",
            "date": now
        }

        submissions[code] = sub
        if uid not in user_submissions:
            user_submissions[uid] = []
        user_submissions[uid].append(code)
        clear_state(uid)

        # Simple clean response to user
        response = (
            "\u2705 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u0628\u0627 \u0645\u0648\u0641\u0642\u06cc\u062a \u062b\u0628\u062a \u0634\u062f.\n\n"
            f"\U0001f516 \u06a9\u062f \u067e\u06cc\u06af\u06cc\u0631\u06cc: {code}\n\n"
            f"\U0001f4cb \u062e\u0644\u0627\u0635\u0647:\n{sub['summary']}\n\n"
            "\U0001f4e8 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u0628\u0647 \u0633\u0627\u0632\u0645\u0627\u0646 \u0645\u0631\u0628\u0648\u0637\u0647 \u0627\u0631\u0633\u0627\u0644 \u062e\u0648\u0627\u0647\u062f \u0634\u062f."
        )
        await msg.edit_text(response, reply_markup=main_kb())

        # Send detailed report to channel/admin
        await send_to_channel(c, sub)

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("\u062e\u0637\u0627\u06cc\u06cc \u0631\u062e \u062f\u0627\u062f. \u0644\u0637\u0641\u0627 \u062f\u0648\u0628\u0627\u0631\u0647 \u062a\u0644\u0627\u0634 \u06a9\u0646\u06cc\u062f.", reply_markup=back_kb())

def analyze_with_gemini(text, category):
    prompt = f"""\u062a\u0648 \u0633\u06cc\u0633\u062a\u0645 \u0647\u0648\u0634 \u0645\u0635\u0646\u0648\u0639\u06cc \u062a\u062d\u0644\u06cc\u0644 \u0628\u0627\u0632\u062e\u0648\u0631\u062f \u0634\u0647\u0631\u0648\u0646\u062f\u06cc \u0647\u0633\u062a\u06cc.\n\u067e\u06cc\u0627\u0645 \u0634\u0647\u0631\u0648\u0646\u062f \u0631\u0627 \u062a\u062d\u0644\u06cc\u0644 \u06a9\u0646. \u0641\u0642\u0637 JSON \u062e\u0631\u0648\u062c\u06cc \u0628\u062f\u0647:\n\n{{\n  \"title\": \"\u0639\u0646\u0648\u0627\u0646 \u06a9\u0648\u062a\u0627\u0647 \u062d\u062f\u0627\u06a9\u062b\u0631 8 \u06a9\u0644\u0645\u0647\",\n  \"issue_type\": \"\u06cc\u06a9\u06cc \u0627\u0632: \u0632\u06cc\u0631\u0633\u0627\u062e\u062a | \u062d\u0645\u0644\u200c\u0648\u0646\u0642\u0644 | \u0628\u0647\u062f\u0627\u0634\u062a | \u0622\u0645\u0648\u0632\u0634 | \u0645\u062d\u06cc\u0637 \u0632\u06cc\u0633\u062a | \u0627\u0642\u062a\u0635\u0627\u062f | \u062e\u062f\u0645\u0627\u062a \u062f\u0648\u0644\u062a\u06cc | \u0633\u0627\u06cc\u0631\",\n  \"subcategory\": \"\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u062b\u0644 \u0622\u0628\u060c \u0628\u0631\u0642\u060c \u062c\u0627\u062f\u0647\u060c \u0627\u06cc\u0646\u062a\u0631\u0646\u062a\",\n  \"urgency\": \u0639\u062f\u062f 1 \u062a\u0627 10,\n  \"impact\": \u0639\u062f\u062f 1 \u062a\u0627 10,\n  \"priority_score\": \u0639\u062f\u062f 1 \u062a\u0627 100,\n  \"location\": \"\u0634\u0647\u0631 \u06cc\u0627 \u0645\u0646\u0637\u0642\u0647 \u0627\u06af\u0631 \u0630\u06a9\u0631 \u0634\u062f\u0647 \u0648\u06af\u0631\u0646\u0647 \u0646\u0627\u0645\u0634\u062e\u0635\",\n  \"responsible_department\": \"\u0646\u0627\u0645 \u06a9\u0627\u0645\u0644 \u0633\u0627\u0632\u0645\u0627\u0646 \u06cc\u0627 \u0648\u0632\u0627\u0631\u062a\u062e\u0627\u0646\u0647 \u0645\u0633\u0626\u0648\u0644 \u0628\u0647 \u0641\u0627\u0631\u0633\u06cc\",\n  \"summary\": \"\u062e\u0644\u0627\u0635\u0647 2 \u062c\u0645\u0644\u0647\u200c\u0627\u06cc \u0627\u0632 \u0645\u0634\u06a9\u0644\",\n  \"is_valid\": true \u06cc\u0627 false,\n  \"invalid_reason\": \"\u0627\u06af\u0631 is_valid=false \u062f\u0644\u06cc\u0644 \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633 \u0648\u06af\u0631\u0646\u0647 \u062e\u0627\u0644\u06cc\"\n}}\n\n\u062f\u0633\u062a\u0647: {category}\n\u067e\u06cc\u0627\u0645 \u0634\u0647\u0631\u0648\u0646\u062f: {text}"""

    r = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    match = re.search(r'{[^}]*}|{[\s\S]*}', raw)
    if match:
        return json.loads(match.group())
    return json.loads(raw)

async def send_to_channel(c, sub):
    target = CHANNEL_ID if CHANNEL_ID else ADMIN_CHAT_ID
    if not target:
        return
    try:
        urgency = sub["urgency"]
        urgency_emoji = "\U0001f534" if urgency >= 8 else "\U0001f7e1" if urgency >= 5 else "\U0001f7e2"
        text = (
            f"\U0001f4e8 \u06af\u0632\u0627\u0631\u0634 \u062c\u062f\u06cc\u062f \u0634\u0647\u0631\u0648\u0646\u062f\u06cc\n"
            f"{'\u2500'*30}\n"
            f"\U0001f516 \u06a9\u062f: {sub['code']}\n"
            f"\U0001f5c2 \u062f\u0633\u062a\u0647: {sub['category']}\n"
            f"\U0001f4cc \u0639\u0646\u0648\u0627\u0646: {sub['title']}\n"
            f"\U0001f539 \u0646\u0648\u0639: {sub['issue_type']} \u2190 {sub['subcategory']}\n"
            f"\U0001f3db \u0633\u0627\u0632\u0645\u0627\u0646: {sub['responsible_department']}\n"
            f"\u26a1 \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a: {urgency_emoji} {urgency}/10\n"
            f"\U0001f3af \u0627\u0645\u062a\u06cc\u0627\u0632: {sub.get('priority_score', 0)}/100\n"
            f"\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a: {sub['location']}\n"
            f"\U0001f4c5 \u062a\u0627\u0631\u06cc\u062e: {sub['date']}\n"
            f"{'\u2500'*30}\n"
            f"\U0001f4dd \u062e\u0644\u0627\u0635\u0647:\n{sub['summary']}\n\n"
            f"\U0001f4ac \u0645\u062a\u0646 \u0627\u0635\u0644\u06cc:\n{sub['original_text'][:600]}"
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
