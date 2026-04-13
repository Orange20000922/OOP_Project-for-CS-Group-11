from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCHEDULES_DIR = DATA_DIR / "schedules"
USERS_FILE = DATA_DIR / "users.json"
LOGS_DIR = DATA_DIR / "logs"
APP_LOG_FILE = LOGS_DIR / "app.log"
STATIC_DIR = BASE_DIR / "static"
LOG_LEVEL = "INFO"

SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRE_SECONDS = 7 * 24 * 3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "lax"
SESSION_COOKIE_SECURE = False

# 节次时间表（需根据华南师范大学实际作息核实）
# 格式: period -> (开始时间, 结束时间)
PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1:  ("08:00", "08:45"),
    2:  ("08:50", "09:35"),
    3:  ("09:45", "10:30"),
    4:  ("10:35", "11:20"),
    5:  ("11:25", "12:10"),
    6:  ("12:15", "13:00"),
    7:  ("14:00", "14:45"),
    8:  ("14:50", "15:35"),
    9:  ("15:45", "16:30"),
    10: ("16:35", "17:20"),
    11: ("18:30", "19:15"),
    12: ("19:20", "20:05"),
}

# 强智教务系统
SCNU_JWXT_BASE = "https://jwxt.scnu.edu.cn"
SCNU_LOGIN_PATH = "/xtgl/login_slogin.html"
SCNU_PUBLIC_KEY_PATH = "/xtgl/login_getPublicKey.html"
SCNU_SCHEDULE_QUERY_PATH = "/kbcx/xskbcx_cxXsgrkb.html"

# SCNU 统一身份认证（SSO）— Playwright 回退路径使用
SCNU_SSO_AUTH_URL = (
    "https://sso.scnu.edu.cn/AccountService/openapi/auth.html"
    "?client_id=9347e8e342e93da94c8ecf27a9de2599"
    "&response_type=code"
    "&redirect_url=https://jwxt.scnu.edu.cn/sso/oauthLogin"
)
