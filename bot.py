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
TEHRAN_OFFSET = datetime.timezone(datetime.timedelta(hours=3, minutes=30))

submissions = {}
user_submissions = {}
states = {}

# ── String constants (avoid backslash inside f-string expressions) ──
NAMSHAKHAS   = "\u0646\u0627\u0645\u0634\u062e\u0635"
BEDOON_ONVAN = "\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646"
DARYAFT_SHOD = "\u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f"
SEP          = "\u2500" * 30
PAGE_SIZE    = 5

CATEGORY_MAP = {
    "cat_complaint" : "\u0634\u06a9\u0627\u06cc\u062a / \u0645\u0634\u06a9\u0644",
    "cat_suggestion": "\u067e\u06cc\u0634\u0646\u0647\u0627\u062f",
    "cat_idea"      : "\u0627\u06cc\u062f\u0647",
    "cat_opinion"   : "\u0646\u0638\u0631 \u0639\u0645\u0648\u0645\u06cc",
}
CATEGORY_EMOJI = {
    "cat_complaint" : "\u274c",
    "cat_suggestion": "\U0001f4a1",
    "cat_idea"      : "\U0001f680",
    "cat_opinion"   : "\U0001f4ac",
}
CATEGORY_PROMPTS = {
    "cat_complaint": (
        "\u0644\u0637\u0641\u0627 \u0645\u0634\u06a9\u0644 \u06cc\u0627 \u0634\u06a9\u0627\u06cc\u062a \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u062a\u0648\u0636\u06cc\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0686\u0647 \u0645\u0634\u06a9\u0644\u06cc \u0631\u062e \u062f\u0627\u062f\u0647 \u0648 \u0627\u0632 \u0686\u0647 \u0632\u0645\u0627\u0646\u06cc\u061f\n"
        "\u2022 \u062f\u0631 \u06a9\u062c\u0627 \u0627\u062a\u0641\u0627\u0642 \u0627\u0641\u062a\u0627\u062f\u0647\u061f (\u0645\u062d\u0644\u0647\u060c \u062e\u06cc\u0627\u0628\u0627\u0646\u060c \u0645\u0646\u0637\u0642\u0647)\n"
        "\u2022 \u0686\u0647 \u0633\u0627\u0632\u0645\u0627\u0646\u06cc \u0645\u0633\u0626\u0648\u0644 \u0631\u0633\u06cc\u062f\u06af\u06cc \u0627\u0633\u062a\u061f"
    ),
    "cat_suggestion": (
        "\u0644\u0637\u0641\u0627 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0634\u0631\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0634\u0645\u0627 \u062f\u0642\u06cc\u0642\u0627 \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u0686\u0647 \u0645\u0634\u06a9\u0644\u06cc \u0631\u0627 \u062d\u0644 \u0645\u06cc\u200c\u06a9\u0646\u062f\u061f\n"
        "\u2022 \u0686\u0647 \u0645\u0646\u0627\u0628\u0639 \u06cc\u0627 \u0628\u0648\u062f\u062c\u0647\u200c\u0627\u06cc \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f\u061f"
    ),
    "cat_idea": (
        "\u0644\u0637\u0641\u0627 \u0627\u06cc\u062f\u0647 \u062e\u0648\u062f \u0631\u0627 \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0634\u0631\u062d \u062f\u0647\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0627\u06cc\u062f\u0647 \u0634\u0645\u0627 \u0686\u06cc\u0633\u062a \u0648 \u0686\u0647 \u0647\u062f\u0641\u06cc \u062f\u0627\u0631\u062f\u061f\n"
        "\u2022 \u0686\u06af\u0648\u0646\u0647 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646 \u0622\u0646 \u0631\u0627 \u0627\u062c\u0631\u0627\u06cc\u06cc \u06a9\u0631\u062f\u061f\n"
        "\u2022 \u062f\u0631 \u0686\u0647 \u0628\u0627\u0632\u0647 \u0632\u0645\u0627\u0646\u06cc \u0642\u0627\u0628\u0644 \u0627\u062c\u0631\u0627\u0633\u062a\u061f"
    ),
    "cat_opinion": (
        "\u0644\u0637\u0641\u0627 \u0646\u0638\u0631 \u062e\u0648\u062f \u0631\u0627 \u0628\u06cc\u0627\u0646 \u06a9\u0646\u06cc\u062f.\n\n"
        "\u0628\u0631\u0627\u06cc \u0628\u0631\u0631\u0633\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631 \u0645\u0648\u0627\u0631\u062f \u0632\u06cc\u0631 \u0631\u0627 \u0630\u06a9\u0631 \u06a9\u0646\u06cc\u062f:\n"
        "\u2022 \u0645\u0648\u0636\u0648\u0639 \u0645\u0648\u0631\u062f \u0646\u0638\u0631 \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u062f\u06cc\u062f\u06af\u0627\u0647 \u0648 \u0646\u0638\u0631 \u0634\u0645\u0627 \u0686\u06cc\u0633\u062a\u061f\n"
        "\u2022 \u0686\u0647 \u0631\u0627\u0647\u200c\u062d\u0644 \u06cc\u0627 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f\u06cc \u062f\u0627\u0631\u06cc\u062f\u061f"
    ),
}
STATUS_MAP = {
    "received" : "\u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f",
    "analyzing": "\u062f\u0631 \u062d\u0627\u0644 \u062a\u062d\u0644\u06cc\u0644",
    "sent"      : "\u0627\u0631\u0633\u0627\u0644 \u0634\u062f \u0628\u0647 \u0633\u0627\u0632\u0645\u0627\u0646",
    "reviewing" : "\u062f\u0631 \u062d\u0627\u0644 \u0628\u0631\u0631\u0633\u06cc",
    "resolved"  : "\u062d\u0644 \u0634\u062f\u0647",
    "rejected"  : "\u0631\u062f \u0634\u062f\u0647",
}
EMOTION_LABELS = {
    10: "\U0001f621 \u062e\u0634\u0645 \u0634\u062f\u06cc\u062f",
    9 : "\U0001f620 \u062e\u0634\u0645 \u0632\u06cc\u0627\u062f",
    8 : "\U0001f624 \u0646\u0627\u0631\u0636\u0627\u06cc\u062a\u06cc \u0634\u062f\u06cc\u062f",
    7 : "\U0001f615 \u0646\u0627\u0631\u0636\u0627\u06cc\u062a",
    6 : "\U0001f610 \u062e\u0646\u062b\u06cc \u0628\u0627 \u0627\u0646\u062f\u06a9\u06cc \u0646\u06af\u0631\u0627\u0646\u06cc",
    5 : "\U0001f610 \u062e\u0646\u062b\u06cc",
    4 : "\U0001f642 \u0646\u0633\u0628\u062a\u0627\u064b \u0631\u0627\u0636\u06cc",
    3 : "\U0001f60a \u0631\u0627\u0636\u06cc",
    2 : "\U0001f604 \u062e\u0648\u0634\u062d\u0627\u0644",
    1 : "\U0001f60d \u062e\u06cc\u0644\u06cc \u062e\u0648\u0634\u062d\u0627\u0644",
}
WELCOME = (
    "\u0628\u0647 \u0633\u0627\u0645\u0627\u0646\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 \u0645\u0631\u062f\u0645\u06cc \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f \U0001f3db\n\n"
    "\u0627\u0632 \u0637\u0631\u06cc\u0642 \u0627\u06cc\u0646 \u0633\u0627\u0645\u0627\u0646\u0647 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u06cc\u062f:\n"
    "\u2022 \u0645\u0634\u06a9\u0644\u0627\u062a \u0648 \u0634\u06a9\u0627\u06cc\u0627\u062a \u0631\u0627 \u06af\u0632\u0627\u0631\u0634 \u062f\u0647\u06cc\u062f\n"
    "\u2022 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f\u0627\u062a \u0648 \u0627\u06cc\u062f\u0647\u200c\u0647\u0627\u06cc \u062e\u0648\u062f \u0631\u0627 \u062b\u0628\u062a \u06a9\u0646\u06cc\u062f\n"
    "\u2022 \u0648\u0636\u0639\u06cc\u062a \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627\u06cc \u0642\u0628\u0644\u06cc \u0631\u0627 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u06a9\u0646\u06cc\u062f\n\n"
    "\u0644\u0637\u0641\u0627 \u06cc\u06a9 \u06af\u0632\u06cc\u0646\u0647 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:"
)
JALALI_MONTHS = {
    "\u0641\u0631\u0648\u0631\u062f\u06cc\u0646":1,"\u0627\u0631\u062f\u06cc\u0628\u0647\u0634\u062a":2,"\u062e\u0631\u062f\u0627\u062f":3,
    "\u062a\u06cc\u0631":4,"\u0645\u0631\u062f\u0627\u062f":5,"\u0634\u0647\u0631\u06cc\u0648\u0631":6,
    "\u0645\u0647\u0631":7,"\u0622\u0628\u0627\u0646":8,"\u0622\u0630\u0631":9,
    "\u062f\u06cc":10,"\u0628\u0647\u0645\u0646":11,"\u0627\u0633\u0641\u0646\u062f":12,
}


def jalali_to_gregorian(jy, jm, jd):
    jy -= 979
    jm -= 1
    jd -= 1
    j_day_no = 365 * jy + (jy // 33) * 8 + (jy % 33 + 3) // 4
    for i in range(jm):
        j_day_no += [31,31,31,31,31,31,30,30,30,30,30,29][i]
    j_day_no += jd
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no = g_day_no % 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no = g_day_no % 36524
        leap = False if g_day_no % 365 == 0 else True
        if g_day_no >= 365:
            g_day_no += 1
    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no = g_day_no % 365
    g_days = [31, 29 if leap else 28,31,30,31,30,31,31,30,31,30,31]
    gm = 0
    for i, days in enumerate(g_days):
        if g_day_no < days:
            gm = i + 1
            break
        g_day_no -= days
    gd = g_day_no + 1
    return gy, gm, gd


def parse_jalali_date(text):
    """Parse Persian date string like '16 شهریور 1405'. Returns datetime.date or None."""
    text = text.strip()
    parts = text.split()
    if len(parts) == 3:
        try:
            jd = int(parts[0])
            jm = JALALI_MONTHS.get(parts[1])
            jy = int(parts[2])
            if jm and 1 <= jd <= 31 and 1300 <= jy <= 1500:
                gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
                return datetime.date(gy, gm, gd)
        except Exception:
            pass
    # Also try YYYY-MM-DD Gregorian fallback
    try:
        return datetime.date.fromisoformat(text)
    except Exception:
        return None


def parse_jalali_month(text):
    """Parse like 'فروردین 1404'. Returns (start_date, end_date) or None."""
    parts = text.strip().split()
    if len(parts) == 2:
        jm = JALALI_MONTHS.get(parts[0])
        try:
            jy = int(parts[1])
        except Exception:
            return None
        if jm and 1300 <= jy <= 1500:
            gy_s, gm_s, gd_s = jalali_to_gregorian(jy, jm, 1)
            last_day = 29 if jm == 12 else (30 if jm >= 7 else 31)
            gy_e, gm_e, gd_e = jalali_to_gregorian(jy, jm, last_day)
            return datetime.date(gy_s, gm_s, gd_s), datetime.date(gy_e, gm_e, gd_e)
    return None


# ── Helpers ──────────────────────────────────────────────────────────

def gen_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_state(uid):
    return states.get(uid, {"step": None, "data": {}})

def set_state(uid, step, data=None):
    states[uid] = {"step": step, "data": data or {}}

def clear_state(uid):
    states.pop(uid, None)

def emotion_label(score):
    s = max(1, min(10, int(score)))
    return EMOTION_LABELS.get(s, str(s))

def get_submissions_in_range(start_dt, end_dt):
    """Returns submissions where date falls in [start_dt, end_dt] (datetime objects)."""
    result = []
    for sub in submissions.values():
        try:
            dt = datetime.datetime.strptime(sub["date"], "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=TEHRAN_OFFSET)
            if start_dt <= dt <= end_dt:
                result.append(sub)
        except Exception:
            pass
    return result

def get_recent_submissions(hours=24):
    now = datetime.datetime.now(TEHRAN_OFFSET)
    return get_submissions_in_range(now - datetime.timedelta(hours=hours), now)


# ── Keyboards ─────────────────────────────────────────────────────────

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4dd \u062b\u0628\u062a \u0645\u0634\u06a9\u0644 \u062c\u062f\u06cc\u062f", callback_data="new_issue")],
        [InlineKeyboardButton("\U0001f4cc \u067e\u06cc\u06af\u06cc\u0631\u06cc \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627", callback_data="track")],
    ])

def category_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u274c \u0634\u06a9\u0627\u06cc\u062a / \u0645\u0634\u06a9\u0644", callback_data="cat_complaint")],
        [InlineKeyboardButton("\U0001f4a1 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f",           callback_data="cat_suggestion")],
        [InlineKeyboardButton("\U0001f680 \u0627\u06cc\u062f\u0647",                            callback_data="cat_idea")],
        [InlineKeyboardButton("\U0001f4ac \u0646\u0638\u0631 \u0639\u0645\u0648\u0645\u06cc",    callback_data="cat_opinion")],
        [InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc",          callback_data="main_menu")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc", callback_data="main_menu")]])

def daily_report_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001f534 \u0634\u06a9\u0627\u06cc\u0627\u062a \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc", callback_data="lst|cat_complaint|hi|0"),
            InlineKeyboardButton("\U0001f7e2 \u0634\u06a9\u0627\u06cc\u0627\u062a \u0639\u0627\u062f\u06cc",       callback_data="lst|cat_complaint|lo|0"),
        ],
        [
            InlineKeyboardButton("\U0001f534 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc", callback_data="lst|cat_suggestion|hi|0"),
            InlineKeyboardButton("\U0001f7e2 \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0639\u0627\u062f\u06cc",   callback_data="lst|cat_suggestion|lo|0"),
        ],
        [
            InlineKeyboardButton("\U0001f534 \u0627\u06cc\u062f\u0647 \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc", callback_data="lst|cat_idea|hi|0"),
            InlineKeyboardButton("\U0001f7e2 \u0627\u06cc\u062f\u0647 \u0639\u0627\u062f\u06cc",                  callback_data="lst|cat_idea|lo|0"),
        ],
        [
            InlineKeyboardButton("\U0001f534 \u0646\u0638\u0631 \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc", callback_data="lst|cat_opinion|hi|0"),
            InlineKeyboardButton("\U0001f7e2 \u0646\u0638\u0631 \u0639\u0627\u062f\u06cc",                     callback_data="lst|cat_opinion|lo|0"),
        ],
        [InlineKeyboardButton("\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647", callback_data="cmp_menu")],
    ])

def list_nav_kb(cat, urg, page, total):
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("\u25c0\ufe0f \u0642\u0628\u0644\u06cc", callback_data=f"lst|{cat}|{urg}|{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("\u0628\u0639\u062f\u06cc \u25b6\ufe0f", callback_data=f"lst|{cat}|{urg}|{page+1}"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("\U0001f4ca \u06af\u0632\u0627\u0631\u0634 \u0631\u0648\u0632\u0627\u0646\u0647", callback_data="show_report_kb")])
    return InlineKeyboardMarkup(rows)

def compare_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001f4c5 \u0631\u0648\u0632\u0627\u0646\u0647",  callback_data="cmp_daily"),
            InlineKeyboardButton("\U0001f4c5 \u0647\u0641\u062a\u06af\u06cc",    callback_data="cmp_weekly"),
        ],
        [
            InlineKeyboardButton("\U0001f4c5 \u0645\u0627\u0647\u0627\u0646\u0647",  callback_data="cmp_monthly"),
            InlineKeyboardButton("\U0001f4c5 \u0627\u0646\u062a\u062e\u0627\u0628\u06cc", callback_data="cmp_custom"),
        ],
        [InlineKeyboardButton("\U0001f4ca \u06af\u0632\u0627\u0631\u0634 \u0631\u0648\u0632\u0627\u0646\u0647", callback_data="show_report_kb")],
    ])


# ── Gemini ────────────────────────────────────────────────────────────

def analyze_with_gemini(text, category):
    prompt = (
        "\u062a\u0648 \u0633\u06cc\u0633\u062a\u0645 \u0647\u0648\u0634 \u0645\u0635\u0646\u0648\u0639\u06cc \u062a\u062d\u0644\u06cc\u0644 \u0628\u0627\u0632\u062e\u0648\u0631\u062f \u0634\u0647\u0631\u0648\u0646\u062f\u06cc \u0647\u0633\u062a\u06cc.\n"
        "\u067e\u06cc\u0627\u0645 \u0634\u0647\u0631\u0648\u0646\u062f \u0631\u0627 \u062a\u062d\u0644\u06cc\u0644 \u06a9\u0646. \u0641\u0642\u0637 JSON \u062e\u0631\u0648\u062c\u06cc \u0628\u062f\u0647:\n\n"
        "{\n"
        '  "title": "\u0639\u0646\u0648\u0627\u0646 \u06a9\u0648\u062a\u0627\u0647 \u062d\u062f\u0627\u06a9\u062b\u0631 8 \u06a9\u0644\u0645\u0647",\n'
        '  "issue_type": "\u0632\u06cc\u0631\u0633\u0627\u062e\u062a | \u062d\u0645\u0644\u200c\u0648\u0646\u0642\u0644 | \u0628\u0647\u062f\u0627\u0634\u062a | \u0622\u0645\u0648\u0632\u0634 | \u0645\u062d\u06cc\u0637 | \u0627\u0642\u062a\u0635\u0627\u062f | \u062e\u062f\u0645\u0627\u062a | \u0633\u0627\u06cc\u0631",\n'
        '  "subcategory": "\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc \u062f\u0642\u06cc\u0642\u200c\u062a\u0631",\n'
        '  "urgency": \u0639\u062f\u062f 1-10,\n'
        '  "impact": \u0639\u062f\u062f 1-10,\n'
        '  "priority_score": \u0639\u062f\u062f 1-100,\n'
        '  "location": "\u0634\u0647\u0631 \u06cc\u0627 \u0645\u0646\u0637\u0642\u0647 \u06cc\u0627 \u0646\u0627\u0645\u0634\u062e\u0635",\n'
        '  "responsible_department": "\u0646\u0627\u0645 \u0633\u0627\u0632\u0645\u0627\u0646 \u0645\u0633\u0626\u0648\u0644",\n'
        '  "summary": "\u062e\u0644\u0627\u0635\u0647 2 \u062c\u0645\u0644\u0647\u200c\u0627\u06cc",\n'
        '  "emotion_score": \u0639\u062f\u062f 1-10 (10=\u062e\u0634\u0645 \u0634\u062f\u06cc\u062f, 1=\u062e\u0648\u0634\u062d\u0627\u0644),\n'
        '  "emotion_label": "\u062a\u0648\u0635\u06cc\u0641 \u06a9\u0648\u062a\u0627\u0647 \u0627\u062d\u0633\u0627\u0633\u0627\u062a",\n'
        '  "is_valid": true \u06cc\u0627 false,\n'
        '  "invalid_reason": "\u0627\u06af\u0631 false \u062f\u0644\u06cc\u0644 \u0648\u06af\u0631\u0646\u0647 \u062e\u0627\u0644\u06cc"\n'
        "}\n\n"
        f"\u062f\u0633\u062a\u0647: {category}\n"
        f"\u067e\u06cc\u0627\u0645: {text}"
    )
    r = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    m = re.search(r"{[\s\S]*?}", raw)
    return json.loads(m.group() if m else raw)


def gemini_text(prompt, timeout=90):
    r = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=timeout)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def build_daily_ai_summary(subs):
    lines = [
        f"- {s.get('title','-')} | {s.get('category','-')} | {s.get('issue_type','-')} "
        f"| \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a:{s.get('urgency',5)} | \u0627\u062d\u0633\u0627\u0633: {s.get('emotion_score',5)}/10"
        for s in subs
    ]
    prompt = (
        "\u0644\u06cc\u0633\u062a \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627 \u0631\u0627 \u062a\u062d\u0644\u06cc\u0644 \u06a9\u0646 \u0648 \u06af\u0632\u0627\u0631\u0634 \u062c\u0627\u0645\u0639 \u0628\u0647 \u0641\u0627\u0631\u0633\u06cc \u0628\u0646\u0648\u06cc\u0633:\n\n"
        + "\n".join(lines)
        + "\n\n\u06af\u0632\u0627\u0631\u0634 \u0634\u0627\u0645\u0644:\n"
        "1. \u062e\u0644\u0627\u0635\u0647 \u06a9\u0644\u06cc\n"
        "2. \u067e\u0631\u062a\u06a9\u0631\u0627\u0631\u062a\u0631\u06cc\u0646 \u0645\u0634\u06a9\u0644\u0627\u062a (3 \u0645\u0648\u0631\u062f \u0627\u0648\u0644)\n"
        "3. \u0627\u0648\u0631\u0698\u0627\u0646\u06cc\u200c\u062a\u0631\u06cc\u0646 \u0645\u0648\u0627\u0631\u062f\n"
        "4. \u0633\u0627\u0632\u0645\u0627\u0646\u200c\u0647\u0627\u06cc \u067e\u0631\u0628\u0627\u0631\u062a\u0631\n"
        "5. \u062f\u0645\u06cc\u0646\u0647 \u0627\u062d\u0633\u0627\u0633\u0627\u062a \u0639\u0645\u0648\u0645\u06cc \u0645\u0631\u062f\u0645\n"
        "6. \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0627\u0642\u062f\u0627\u0645\u0627\u062a \u0641\u0648\u0631\u06cc"
    )
    try:
        return gemini_text(prompt)
    except Exception as e:
        logger.error(f"Daily AI: {e}")
        return "\u062a\u062d\u0644\u06cc\u0644 \u0647\u0648\u0634 \u0645\u0635\u0646\u0648\u0639\u06cc \u062f\u0631 \u062f\u0633\u062a\u0631\u0633 \u0646\u06cc\u0633\u062a."


def build_compare_report(subs_a, label_a, subs_b, label_b):
    def fmt(subs):
        if not subs:
            return "\u0647\u06cc\u0686 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u062b\u0628\u062a \u0646\u0634\u062f"
        return "\n".join(
            f"- {s.get('title','-')} | \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a:{s.get('urgency',5)} | \u0627\u062d\u0633\u0627\u0633: {s.get('emotion_score',5)}/10 | {s.get('category','-')}"
            for s in subs
        )
    prompt = (
        "\u062f\u0648 \u0628\u0627\u0632\u0647 \u0632\u0645\u0627\u0646\u06cc \u0631\u0627 \u0628\u0627 \u0647\u0645 \u0645\u0642\u0627\u06cc\u0633\u0647 \u06a9\u0646 \u0648 \u06af\u0632\u0627\u0631\u0634 \u062c\u0627\u0645\u0639 \u0628\u0647 \u0641\u0627\u0631\u0633\u06cc \u0628\u0646\u0648\u06cc\u0633:\n\n"
        f"== {label_a} ({len(subs_a)} \u062f\u0631\u062e\u0648\u0627\u0633\u062a) ==\n{fmt(subs_a)}\n\n"
        f"== {label_b} ({len(subs_b)} \u062f\u0631\u062e\u0648\u0627\u0633\u062a) ==\n{fmt(subs_b)}\n\n"
        "\u06af\u0632\u0627\u0631\u0634 \u0634\u0627\u0645\u0644:\n"
        "1. \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a \u06a9\u0645\u06cc (\u062a\u0639\u062f\u0627\u062f\u060c \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a)\n"
        "2. \u062a\u063a\u06cc\u06cc\u0631 \u0637\u0631\u0632 \u0641\u06a9\u0631 \u0648 \u062f\u063a\u062f\u063a\u0647\u0647\u0627\u06cc \u0645\u0631\u062f\u0645\n"
        "3. \u062a\u063a\u06cc\u06cc\u0631 \u0627\u062d\u0633\u0627\u0633\u0627\u062a \u0639\u0645\u0648\u0645\u06cc\n"
        "4. \u0645\u0648\u0636\u0648\u0639\u0627\u062a \u062c\u062f\u06cc\u062f \u06cc\u0627 \u0645\u062d\u0648 \u0634\u062f\u0647\n"
        "5. \u062c\u0645\u0639\u200c\u0628\u0646\u062f\u06cc \u06a9\u0644\u06cc"
    )
    try:
        return gemini_text(prompt)
    except Exception as e:
        logger.error(f"Compare AI: {e}")
        return "\u062e\u0637\u0627 \u062f\u0631 \u062a\u0648\u0644\u06cc\u062f \u06af\u0632\u0627\u0631\u0634."


# ── Channel sender ────────────────────────────────────────────────────

async def send_to_channel(c, sub):
    target = CHANNEL_ID if CHANNEL_ID else ADMIN_CHAT_ID
    if not target:
        return
    try:
        urgency  = sub["urgency"]
        ue       = "\U0001f534" if urgency >= 8 else "\U0001f7e1" if urgency >= 5 else "\U0001f7e2"
        priority = sub.get("priority_score", 0)
        emo_score = sub.get("emotion_score", 5)
        emo_lbl   = emotion_label(emo_score)
        code  = sub["code"]
        cat   = sub["category"]
        title = sub["title"]
        itype = sub["issue_type"]
        subcat= sub["subcategory"]
        dept  = sub["responsible_department"]
        loc   = sub["location"]
        dt    = sub["date"]
        summ  = sub["summary"]
        orig  = sub["original_text"][:600]
        text = (
            f"\U0001f4e8 \u06af\u0632\u0627\u0631\u0634 \u062c\u062f\u06cc\u062f \u0634\u0647\u0631\u0648\u0646\u062f\u06cc\n"
            f"{SEP}\n"
            f"\U0001f516 \u06a9\u062f: {code}\n"
            f"\U0001f5c2 \u062f\u0633\u062a\u0647: {cat}\n"
            f"\U0001f4cc \u0639\u0646\u0648\u0627\u0646: {title}\n"
            f"\U0001f539 \u0646\u0648\u0639: {itype} \u2190 {subcat}\n"
            f"\U0001f3db \u0633\u0627\u0632\u0645\u0627\u0646: {dept}\n"
            f"\u26a1 \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a: {ue} {urgency}/10\n"
            f"\U0001f3af \u0627\u0645\u062a\u06cc\u0627\u0632: {priority}/100\n"
            f"\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a: {loc}\n"
            f"\U0001f4c5 \u062a\u0627\u0631\u06cc\u062e: {dt}\n"
            f"\U0001f9e0 \u0627\u062d\u0633\u0627\u0633: {emo_lbl} ({emo_score}/10)\n"
            f"{SEP}\n"
            f"\U0001f4dd \u062e\u0644\u0627\u0635\u0647:\n{summ}\n\n"
            f"\U0001f4ac \u0645\u062a\u0646 \u0627\u0635\u0644\u06cc:\n{orig}"
        )
        await c.bot.send_message(chat_id=target, text=text)
    except Exception as e:
        logger.error(f"Channel send error: {e}")


# ── Daily report ──────────────────────────────────────────────────────

async def send_daily_report(context):
    target = CHANNEL_ID if CHANNEL_ID else ADMIN_CHAT_ID
    if not target:
        return
    now_str = datetime.datetime.now(TEHRAN_OFFSET).strftime("%Y-%m-%d")
    recent  = get_recent_submissions(24)
    total   = len(recent)
    if total == 0:
        msg = (
            f"\U0001f4ca \u06af\u0632\u0627\u0631\u0634 \u0631\u0648\u0632\u0627\u0646\u0647 \u2014 {now_str}\n"
            f"{SEP}\n"
            "\u062f\u0631 24 \u0633\u0627\u0639\u062a \u06af\u0630\u0634\u062a\u0647 \u0647\u06cc\u0686 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u062b\u0628\u062a \u0646\u0634\u062f\u0647 \u0627\u0633\u062a."
        )
        await context.bot.send_message(chat_id=target, text=msg, reply_markup=daily_report_kb())
        return
    cat_count  = {}
    dept_count = {}
    urgencies  = []
    emotions   = []
    for s in recent:
        cat_count[s.get("category","-")] = cat_count.get(s.get("category","-"), 0) + 1
        dept = s.get("responsible_department", NAMSHAKHAS)
        dept_count[dept] = dept_count.get(dept, 0) + 1
        urgencies.append(s.get("urgency", 5))
        emotions.append(s.get("emotion_score", 5))
    avg_urg = sum(urgencies) / len(urgencies)
    avg_emo = sum(emotions)  / len(emotions)
    hi_urg  = sum(1 for u in urgencies if u >= 8)
    cat_lines  = "\n".join(f"  \u2022 {c}: {n}" for c, n in sorted(cat_count.items(),  key=lambda x: x[1], reverse=True))
    dept_lines = "\n".join(f"  \u2022 {d}: {n}" for d, n in sorted(dept_count.items(), key=lambda x: x[1], reverse=True)[:3])
    ai_text = build_daily_ai_summary(recent)
    report = (
        f"\U0001f4ca \u06af\u0632\u0627\u0631\u0634 \u0631\u0648\u0632\u0627\u0646\u0647 \u2014 {now_str}\n"
        f"{SEP}\n"
        f"\U0001f4ac \u062c\u0645\u0639 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627: {total}\n"
        f"\U0001f534 \u0627\u0648\u0631\u0698\u0627\u0646\u06cc (8+): {hi_urg}\n"
        f"\u26a1 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 \u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc\u062a: {avg_urg:.1f}/10\n"
        f"\U0001f9e0 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 \u0627\u062d\u0633\u0627\u0633: {avg_emo:.1f}/10\n\n"
        f"\U0001f5c2 \u062a\u0648\u0632\u06cc\u0639 \u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc:\n{cat_lines}\n\n"
        f"\U0001f3db \u067e\u0631\u0628\u0627\u0631\u062a\u0631\u06cc\u0646 \u0633\u0627\u0632\u0645\u0627\u0646\u200c\u0647\u0627:\n{dept_lines}\n\n"
        f"{SEP}\n"
        f"\U0001f916 \u062a\u062d\u0644\u06cc\u0644 \u0647\u0648\u0634 \u0645\u0635\u0646\u0648\u0639\u06cc:\n{ai_text}"
    )
    if len(report) > 4000:
        report = report[:4000] + "\n..."
    await context.bot.send_message(chat_id=target, text=report, reply_markup=daily_report_kb())
    logger.info(f"Daily report sent: {total} subs")


# ── Handlers ──────────────────────────────────────────────────────────

async def start(u, c):
    clear_state(u.effective_user.id)
    await u.message.reply_text(WELCOME, reply_markup=main_kb())


async def handle_callback(u, c):
    q   = u.callback_query
    await q.answer()
    uid  = q.from_user.id
    data = q.data

    # ── Main menu ──
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
        emoji  = CATEGORY_EMOJI[data]
        name   = CATEGORY_MAP[data]
        prompt = CATEGORY_PROMPTS[data]
        await q.message.reply_text(f"\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc: {emoji} {name}\n\n{prompt}", reply_markup=back_kb())
        return

    if data == "track":
        user_codes = user_submissions.get(uid, [])
        if not user_codes:
            await q.message.reply_text("\u0634\u0645\u0627 \u0647\u0646\u0648\u0632 \u0647\u06cc\u0686 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u062b\u0628\u062a \u0646\u06a9\u0631\u062f\u0647\u200c\u0627\u06cc\u062f.", reply_markup=main_kb())
            return
        buttons = []
        for code in reversed(user_codes[-10:]):
            sub    = submissions.get(code, {})
            title  = sub.get("title", BEDOON_ONVAN)[:25]
            status = STATUS_MAP.get(sub.get("status", "received"), DARYAFT_SHOD)
            buttons.append([InlineKeyboardButton(f"{title} - {status}", callback_data=f"view_{code}")])
        buttons.append([InlineKeyboardButton("\U0001f3e0 \u0645\u0646\u0648 \u0627\u0635\u0644\u06cc", callback_data="main_menu")])
        await q.message.reply_text("\u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627\u06cc \u0634\u0645\u0627:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("view_"):
        code = data[5:]
        sub  = submissions.get(code)
        if not sub:
            await q.message.reply_text("\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.", reply_markup=main_kb())
            return
        urgency   = sub.get("urgency", 5)
        ue        = "\U0001f534" if urgency >= 8 else "\U0001f7e1" if urgency >= 5 else "\U0001f7e2"
        status    = STATUS_MAP.get(sub.get("status", "received"), DARYAFT_SHOD)
        emo_score = sub.get("emotion_score", 5)
        emo_lbl   = emotion_label(emo_score)
        title  = sub.get("title", "-")
        cat    = sub.get("category", "-")
        loc    = sub.get("location", NAMSHAKHAS)
        dt     = sub.get("date", "-")
        summ   = sub.get("summary", "-")
        text = (
            f"\U0001f516 \u06a9\u062f: {code}\n"
            f"\U0001f4cc \u0639\u0646\u0648\u0627\u0646: {title}\n"
            f"\U0001f5c2 \u062f\u0633\u062a\u0647: {cat}\n"
            f"\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a: {loc}\n"
            f"\U0001f4c5 \u062a\u0627\u0631\u06cc\u062e: {dt}\n"
            f"\U0001f4cb \u0648\u0636\u0639\u06cc\u062a: {status}\n"
            f"\U0001f9e0 \u0627\u062d\u0633\u0627\u0633: {emo_lbl}\n\n"
            f"\U0001f4dd \u062e\u0644\u0627\u0635\u0647:\n{summ}"
        )
        await q.message.reply_text(text, reply_markup=back_kb())
        return

    # ── List with pagination ──
    if data.startswith("lst|"):
        parts = data.split("|")
        cat, urg, page = parts[1], parts[2], int(parts[3])
        hi = urg == "hi"
        cat_name  = CATEGORY_MAP.get(cat, cat)
        urg_label = "\u0627\u0648\u0631\u0698\u0627\u0646\u0633\u06cc (8+)" if hi else "\u0639\u0627\u062f\u06cc (<8)"
        recent = get_recent_submissions(24)
        filtered = [
            s for s in recent
            if s.get("category_key") == cat and (s.get("urgency", 5) >= 8) == hi
        ]
        filtered.sort(key=lambda x: x.get("urgency", 0), reverse=True)
        total = len(filtered)
        if total == 0:
            await q.message.reply_text(
                f"\U0001f4ed \u0647\u06cc\u0686 \u0645\u0648\u0631\u062f\u06cc \u062f\u0631 \u062f\u0633\u062a\u0647 {cat_name} ({urg_label}) \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f.",
                reply_markup=list_nav_kb(cat, urg, 0, 0)
            )
            return
        start_i = page * PAGE_SIZE
        page_items = filtered[start_i: start_i + PAGE_SIZE]
        lines = [f"\U0001f4ca {cat_name} \u2014 {urg_label} ({total} \u0645\u0648\u0631\u062f) \u2014 \u0635\u0641\u062d\u0647 {page+1}\n{SEP}"]
        for i, s in enumerate(page_items, start=start_i+1):
            emo_lbl   = emotion_label(s.get("emotion_score", 5))
            emo_score = s.get("emotion_score", 5)
            ue        = "\U0001f534" if s.get("urgency",5)>=8 else "\U0001f7e1" if s.get("urgency",5)>=5 else "\U0001f7e2"
            urgency   = s.get("urgency", 5)
            code      = s.get("code","-")
            title     = s.get("title", BEDOON_ONVAN)
            summ      = s.get("summary","-")
            loc       = s.get("location", NAMSHAKHAS)
            lines.append(
                f"{i}. \U0001f516 {code} | {ue} {urgency}/10 | {emo_lbl} ({emo_score}/10)\n"
                f"   \U0001f4cc {title}\n"
                f"   \U0001f4cd {loc}\n"
                f"   \U0001f4dd {summ[:100]}"
            )
        await q.message.reply_text("\n\n".join(lines), reply_markup=list_nav_kb(cat, urg, page, total))
        return

    # ── Show report keyboard again ──
    if data == "show_report_kb":
        await q.message.reply_text(
            "\U0001f4ca \u06af\u0632\u0627\u0631\u0634 \u0631\u0648\u0632\u0627\u0646\u0647 \u2014 \u062f\u06a9\u0645\u0647\u200c\u0647\u0627\u06cc \u062f\u0633\u062a\u0631\u0633\u06cc \u0633\u0631\u06cc\u0639:",
            reply_markup=daily_report_kb()
        )
        return

    # ── Compare menu ──
    if data == "cmp_menu":
        await q.message.reply_text("\U0001f4ca \u0646\u0648\u0639 \u0645\u0642\u0627\u06cc\u0633\u0647 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:", reply_markup=compare_kb())
        return

    if data in ("cmp_daily", "cmp_weekly", "cmp_monthly"):
        now = datetime.datetime.now(TEHRAN_OFFSET)
        if data == "cmp_daily":
            a_start = now - datetime.timedelta(hours=24)
            a_end   = now
            b_start = now - datetime.timedelta(hours=48)
            b_end   = now - datetime.timedelta(hours=24)
            label_a = "\u0627\u0645\u0631\u0648\u0632"
            label_b = "\u062f\u06cc\u0631\u0648\u0632"
        elif data == "cmp_weekly":
            a_start = now - datetime.timedelta(days=7)
            a_end   = now
            b_start = now - datetime.timedelta(days=14)
            b_end   = now - datetime.timedelta(days=7)
            label_a = "\u0647\u0641\u062a\u0647 \u062c\u0627\u0631\u06cc"
            label_b = "\u0647\u0641\u062a\u0647 \u06af\u0630\u0634\u062a\u0647"
        else:
            a_start = now - datetime.timedelta(days=30)
            a_end   = now
            b_start = now - datetime.timedelta(days=60)
            b_end   = now - datetime.timedelta(days=30)
            label_a = "\u0645\u0627\u0647 \u062c\u0627\u0631\u06cc"
            label_b = "\u0645\u0627\u0647 \u06af\u0630\u0634\u062a\u0647"
        subs_a = get_submissions_in_range(a_start, a_end)
        subs_b = get_submissions_in_range(b_start, b_end)
        wait_msg = await q.message.reply_text("\u0644\u0637\u0641\u0627 \u0635\u0628\u0631 \u06a9\u0646\u06cc\u062f\u060c \u062f\u0631 \u062d\u0627\u0644 \u062a\u0648\u0644\u06cc\u062f \u06af\u0632\u0627\u0631\u0634 \u0645\u0642\u0627\u06cc\u0633\u0647...")
        report = build_compare_report(subs_a, label_a, subs_b, label_b)
        result = (
            f"\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647 {label_a} \u0628\u0627 {label_b}\n"
            f"{SEP}\n{report}"
        )
        if len(result) > 4000:
            result = result[:4000] + "\n..."
        await wait_msg.edit_text(result, reply_markup=compare_kb())
        return

    if data == "cmp_custom":
        set_state(uid, "compare_custom")
        await q.message.reply_text(
            "\U0001f4c5 \u062a\u0627\u0631\u06cc\u062e \u06cc\u0627 \u0628\u0627\u0632\u0647 \u0645\u0648\u0631\u062f \u0646\u0638\u0631 \u0631\u0627 \u0648\u0627\u0631\u062f \u06a9\u0646\u06cc\u062f:\n\n"
            "\u2022 \u062a\u0627\u0631\u06cc\u062e \u0645\u0634\u062e\u0635: \u0645\u062b\u0644\u0627\u064b  16 \u0634\u0647\u0631\u06cc\u0648\u0631 1405\n"
            "\u2022 \u0645\u0627\u0647 \u06a9\u0627\u0645\u0644: \u0645\u062b\u0644\u0627\u064b  \u0641\u0631\u0648\u0631\u062f\u06cc\u0646 1404",
            reply_markup=back_kb()
        )
        return


async def handle_text(u, c):
    uid  = u.effective_user.id
    text = u.message.text
    s    = get_state(uid)

    # ── Compare custom date input ──
    if s["step"] == "compare_custom":
        clear_state(uid)
        now = datetime.datetime.now(TEHRAN_OFFSET)
        # Try full date
        parsed_date = parse_jalali_date(text)
        if parsed_date:
            target_start = datetime.datetime.combine(parsed_date, datetime.time.min).replace(tzinfo=TEHRAN_OFFSET)
            target_end   = datetime.datetime.combine(parsed_date, datetime.time.max).replace(tzinfo=TEHRAN_OFFSET)
            label_b = text.strip()
        else:
            # Try month
            parsed_month = parse_jalali_month(text)
            if parsed_month:
                d_s, d_e = parsed_month
                target_start = datetime.datetime.combine(d_s, datetime.time.min).replace(tzinfo=TEHRAN_OFFSET)
                target_end   = datetime.datetime.combine(d_e, datetime.time.max).replace(tzinfo=TEHRAN_OFFSET)
                label_b = text.strip()
            else:
                await u.message.reply_text(
                    "\u0641\u0631\u0645\u062a \u062a\u0627\u0631\u06cc\u062e \u0635\u062d\u06cc\u062d \u0646\u06cc\u0633\u062a.\n"
                    "\u0645\u062b\u0627\u0644: 16 \u0634\u0647\u0631\u06cc\u0648\u0631 1405  \u06cc\u0627  \u0641\u0631\u0648\u0631\u062f\u06cc\u0646 1404",
                    reply_markup=compare_kb()
                )
                return
        a_start = now - datetime.timedelta(hours=24)
        a_end   = now
        subs_a  = get_submissions_in_range(a_start, a_end)
        subs_b  = get_submissions_in_range(target_start, target_end)
        wait_msg = await u.message.reply_text("\u0644\u0637\u0641\u0627 \u0635\u0628\u0631 \u06a9\u0646\u06cc\u062f\u060c \u062f\u0631 \u062d\u0627\u0644 \u062a\u0648\u0644\u06cc\u062f \u06af\u0632\u0627\u0631\u0634 \u0645\u0642\u0627\u06cc\u0633\u0647...")
        report = build_compare_report(subs_a, "\u0627\u0645\u0631\u0648\u0632", subs_b, label_b)
        result = (
            f"\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647 \u0627\u0645\u0631\u0648\u0632 \u0628\u0627 {label_b}\n"
            f"{SEP}\n{report}"
        )
        if len(result) > 4000:
            result = result[:4000] + "\n..."
        await wait_msg.edit_text(result, reply_markup=compare_kb())
        return

    # ── Normal issue submission ──
    if s["step"] != "typing_issue":
        await u.message.reply_text(WELCOME, reply_markup=main_kb())
        return

    if len(text.strip()) < 15:
        await u.message.reply_text(
            "\u0644\u0637\u0641\u0627 \u062a\u0648\u0636\u06cc\u062d \u06a9\u0627\u0645\u0644\u200c\u062a\u0631\u06cc \u0627\u0631\u0627\u0626\u0647 \u062f\u0647\u06cc\u062f (\u062d\u062f\u0627\u0642\u0644 15 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631).",
            reply_markup=back_kb()
        )
        return

    category     = s["data"].get("category", "\u0639\u0645\u0648\u0645\u06cc")
    category_key = s["data"].get("category_key", "cat_opinion")
    msg = await u.message.reply_text("\u0644\u0637\u0641\u0627 \u0635\u0628\u0631 \u06a9\u0646\u06cc\u062f\u060c \u062f\u0631 \u062d\u0627\u0644 \u062b\u0628\u062a \u0648 \u062a\u062d\u0644\u06cc\u0644 \u0627\u0633\u062a...")
    try:
        analysis = analyze_with_gemini(text, category)
        if not analysis.get("is_valid", True):
            reason = analysis.get("invalid_reason", NAMSHAKHAS)
            await msg.edit_text(
                f"\u067e\u06cc\u0627\u0645 \u0634\u0645\u0627 \u0642\u0627\u0628\u0644 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0646\u06cc\u0633\u062a.\n\n\u062f\u0644\u06cc\u0644: {reason}\n\n"
                "\u0644\u0637\u0641\u0627 \u0645\u062a\u0646 \u0648\u0627\u0642\u0639\u06cc\u200c\u062a\u0631\u06cc \u0628\u0627 \u062c\u0632\u0626\u06cc\u0627\u062a \u0628\u06cc\u0634\u062a\u0631 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.",
                reply_markup=back_kb()
            )
            return
        code = gen_code()
        now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        username = u.effective_user.username or NAMSHAKHAS
        sub = {
            "code": code, "user_id": uid, "username": username,
            "category": category, "category_key": category_key,
            "original_text": text,
            "title"                : analysis.get("title", BEDOON_ONVAN),
            "issue_type"           : analysis.get("issue_type", "-"),
            "subcategory"          : analysis.get("subcategory", "-"),
            "urgency"              : analysis.get("urgency", 5),
            "impact"               : analysis.get("impact", 5),
            "priority_score"       : analysis.get("priority_score", 50),
            "location"             : analysis.get("location", NAMSHAKHAS),
            "responsible_department": analysis.get("responsible_department", NAMSHAKHAS),
            "summary"              : analysis.get("summary", "-"),
            "emotion_score"        : analysis.get("emotion_score", 5),
            "emotion_label"        : analysis.get("emotion_label", "-"),
            "status": "received", "date": now,
        }
        submissions[code] = sub
        user_submissions.setdefault(uid, []).append(code)
        clear_state(uid)
        summ      = sub["summary"]
        emo_lbl   = emotion_label(sub["emotion_score"])
        emo_score = sub["emotion_score"]
        response = (
            "\u2705 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u0628\u0627 \u0645\u0648\u0641\u0642\u06cc\u062a \u062b\u0628\u062a \u0634\u062f.\n\n"
            f"\U0001f516 \u06a9\u062f \u067e\u06cc\u06af\u06cc\u0631\u06cc: {code}\n\n"
            f"\U0001f4cb \u062e\u0644\u0627\u0635\u0647:\n{summ}\n\n"
            "\U0001f4e8 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u0628\u0647 \u0633\u0627\u0632\u0645\u0627\u0646 \u0645\u0631\u0628\u0648\u0637\u0647 \u0627\u0631\u0633\u0627\u0644 \u062e\u0648\u0627\u0647\u062f \u0634\u062f."
        )
        await msg.edit_text(response, reply_markup=main_kb())
        await send_to_channel(c, sub)
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("\u062e\u0637\u0627\u06cc\u06cc \u0631\u062e \u062f\u0627\u062f. \u0644\u0637\u0641\u0627 \u062f\u0648\u0628\u0627\u0631\u0647 \u062a\u0644\u0627\u0634 \u06a9\u0646\u06cc\u062f.", reply_markup=back_kb())


# ── App setup ─────────────────────────────────────────────────────────

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

report_time = datetime.time(hour=2, minute=30, tzinfo=datetime.timezone.utc)  # 06:00 Tehran
app.job_queue.run_daily(send_daily_report, time=report_time)

logger.info("Citizen bot v4 started!")
app.run_polling()
