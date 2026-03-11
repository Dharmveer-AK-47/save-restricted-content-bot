import os
from dotenv import load_dotenv
load_dotenv()

# ════════════════════════════════════════════════════════════════════════════════
# ░ CONFIGURATION SETTINGS
# ════════════════════════════════════════════════════════════════════════════════

# VPS --- FILL COOKIES 🍪 in """ ... """ 
INST_COOKIES = """
# write up here insta cookies
"""

YTUB_COOKIES = """
# write here yt cookies
"""

# ─── BOT / DATABASE CONFIG ──────────────────────────────────────────────────────
API_ID       = os.getenv("API_ID", " 33991640")
API_HASH     = os.getenv("API_HASH", "85d4788bb11ac47f74d8e0754c410d91")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "8642896434:AAFUmn3w3yzz1JEQoWKnSYhUd5HMVAX1eCE")
MONGO_DB     = os.getenv("MONGO_DB", "mongodb+srv://dveer77143_db_user:YourPassword@cluster0.sjql5pn.mongodb.net/bot_db?retryWrites=true&w=majority")
DB_NAME      = os.getenv("DB_NAME", "save-restricted-content-bot")

# ─── OWNER / CONTROL SETTINGS ───────────────────────────────────────────────────
OWNER_ID     = list(map(int, os.getenv("OWNER_ID", "8208350805").split()))  # space-separated list
STRING       = os.getenv("STRING", None)  # optional session string
LOG_GROUP    = int(os.getenv("LOG_GROUP", "-1001234456"))
FORCE_SUB    = int(os.getenv("FORCE_SUB", "0"))

# ─── SECURITY KEYS ──────────────────────────────────────────────────────────────
MASTER_KEY   = os.getenv("MASTER_KEY", "gK8HzLfT9QpViJcYeB5wRa3DmNq")  # session encryption
IV_KEY       = os.getenv("IV_KEY", "s7Yx5CE3F")  # decryption key

# ─── COOKIES HANDLING ───────────────────────────────────────────────────────────
YT_COOKIES   = os.getenv("YT_COOKIES", YTUB_COOKIES)
INSTA_COOKIES = os.getenv("INSTA_COOKIES", INST_COOKIES)

# ─── USAGE LIMITS ───────────────────────────────────────────────────────────────
FREEMIUM_LIMIT = int(os.getenv("FREEMIUM_LIMIT", "50"))
PREMIUM_LIMIT  = int(os.getenv("PREMIUM_LIMIT", "500"))

# ─── UI / LINKS ───────────────────────────────────────────────────────────────── 
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "https://t.me/dharuva_007")
FORCE_SUB     = os.getenv("FORCE_SUB", "RSK_free_content")  # channel ID for force subscription

# ════════════════════════════════════════════════════════════════════════════════
# ░ PREMIUM PLANS CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

P0 = {
    "d": {
        "s": int(os.getenv("PLAN_D_S", 1)),
        "du": int(os.getenv("PLAN_D_DU", 1)),
        "u": os.getenv("PLAN_D_U", "days"),
        "l": os.getenv("PLAN_D_L", "Daily"),
    },
    "w": {
        "s": int(os.getenv("PLAN_W_S", 3)),
        "du": int(os.getenv("PLAN_W_DU", 1)),
        "u": os.getenv("PLAN_W_U", "weeks"),
        "l": os.getenv("PLAN_W_L", "Weekly"),
    },
    "m": {
        "s": int(os.getenv("PLAN_M_S", 5)),
        "du": int(os.getenv("PLAN_M_DU", 1)),
        "u": os.getenv("PLAN_M_U", "month"),
        "l": os.getenv("PLAN_M_L", "Monthly"),
    },
}

# ════════════════════════════════════════════════════════════════════════════════
# ░ DEVGAGAN
# ════════════════════════════════════════════════════════════════════════════════

# ─── JOIN LINK FOR FORCE SUB ─────────────────────────────────────────────────────
JOIN_LINK = os.getenv("JOIN_LINK", "https://t.me/RSK_free_content")
