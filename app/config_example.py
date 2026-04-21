import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCHEDULES_DIR = DATA_DIR / "schedules"
USERS_FILE = DATA_DIR / "users.json"
LOGS_DIR = DATA_DIR / "logs"
# Base log file name; logging_config.py expands this into combined/http/errors/failures sinks.
APP_LOG_FILE = LOGS_DIR / "app.log"
STATIC_DIR = BASE_DIR / "static"
NOTES_DB_PATH = DATA_DIR / "notes.db"
NOTE_FILES_DIR = DATA_DIR / "note_files"
QDRANT_DB_DIR = DATA_DIR / "qdrant_db"
HF_CACHE_DIR = BASE_DIR / ".hf_cache"
HF_HUB_CACHE_DIR = HF_CACHE_DIR / "hub"
TRANSFORMERS_CACHE_DIR = HF_CACHE_DIR / "transformers"
SENTENCE_TRANSFORMERS_CACHE_DIR = HF_CACHE_DIR / "sentence_transformers"
LOG_LEVEL = "INFO"

HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
HF_HUB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TRANSFORMERS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
SENTENCE_TRANSFORMERS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))
os.environ.setdefault("HF_HUB_CACHE", str(HF_HUB_CACHE_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_HUB_CACHE_DIR))
os.environ.setdefault("TRANSFORMERS_CACHE", str(TRANSFORMERS_CACHE_DIR))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(SENTENCE_TRANSFORMERS_CACHE_DIR))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# DeepSeek LLM
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# Text chunking
CHUNK_MAX_LENGTH = 500
CHUNK_OVERLAP = 50

SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRE_SECONDS = 7 * 24 * 3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "lax"
SESSION_COOKIE_SECURE = False

# Class period time ranges: period -> (start_time, end_time)
PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1: ("08:00", "08:45"),
    2: ("08:50", "09:35"),
    3: ("09:45", "10:30"),
    4: ("10:35", "11:20"),
    5: ("11:25", "12:10"),
    6: ("12:15", "13:00"),
    7: ("14:00", "14:45"),
    8: ("14:50", "15:35"),
    9: ("15:45", "16:30"),
    10: ("16:35", "17:20"),
    11: ("18:30", "19:15"),
    12: ("19:20", "20:05"),
}

# SCNU academic system
SCNU_JWXT_BASE = "https://jwxt.scnu.edu.cn"
SCNU_LOGIN_PATH = "/xtgl/login_slogin.html"
SCNU_PUBLIC_KEY_PATH = "/xtgl/login_getPublicKey.html"
SCNU_SCHEDULE_QUERY_PATH = "/kbcx/xskbcx_cxXsgrkb.html"

# SCNU SSO auth URL used by the Playwright fallback path
SCNU_SSO_AUTH_URL = (
    "https://sso.scnu.edu.cn/AccountService/openapi/auth.html"
    "?client_id=9347e8e342e93da94c8ecf27a9de2599"
    "&response_type=code"
    "&redirect_url=https://jwxt.scnu.edu.cn/sso/oauthLogin"
)
