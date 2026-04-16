from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from app.config import SESSION_EXPIRE_SECONDS
from app.core import HashTable
from app.logging_config import logger
from app.models.user import User, UserCreate, UserInfo, UserLogin
from app.storage.user_store import UserStore

try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover
    CryptContext = None


@dataclass
class SessionRecord:
    student_id: str
    expires_at: datetime


class AuthService:
    def __init__(self, user_store: UserStore) -> None:
        self._user_store = user_store
        self._sessions = HashTable[str, SessionRecord](bucket_count=32)
        self._lock = Lock()
        self._pwd_context = self._build_password_context()
        logger.debug("AuthService initialized")
    # ── 用户认证与会话管理 ──
    def register(self, payload: UserCreate) -> UserInfo:
        user = User(
            student_id=payload.student_id.strip(),
            name=payload.name.strip(),
            password_hash=self._hash_password(payload.password),
            scnu_account=(payload.scnu_account or payload.student_id).strip(),
        )
        created = self._user_store.create(user)
        logger.info("Registered user {}", created.student_id)
        return self._to_user_info(created)

    def login(self, payload: UserLogin) -> tuple[str, UserInfo]:
        user = self._user_store.get(payload.student_id.strip())
        if user is None or not self._verify_password(payload.password, user.password_hash):
            logger.warning("Failed login attempt for {}", payload.student_id.strip())
            raise PermissionError("学号或密码错误")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = SessionRecord(
                student_id=user.student_id,
                expires_at=datetime.now() + timedelta(seconds=SESSION_EXPIRE_SECONDS),
            )
        logger.info("User {} logged in", user.student_id)
        return token, self._to_user_info(user)

    def logout(self, session_token: str | None) -> None:
        if not session_token:
            logger.debug("Logout called without session token")
            return
        with self._lock:
            self._sessions.pop(session_token, None)
        logger.info("Session logged out")

    def get_current_user(self, session_token: str | None) -> UserInfo:
        student_id = self.get_student_id(session_token)
        user = self._user_store.get(student_id)
        if user is None:
            self.logout(session_token)
            logger.warning("Session for {} lost backing user record", student_id)
            raise PermissionError("登录状态已失效")
        return self._to_user_info(user)

    def get_student_id(self, session_token: str | None) -> str:
        if not session_token:
            logger.warning("Attempted to access protected resource without login")
            raise PermissionError("未登录")
        with self._lock:
            session = self._sessions.get(session_token)
            if session is None:
                logger.warning("Attempted to use missing session token")
                raise PermissionError("登录状态已失效")
            if session.expires_at <= datetime.now():
                self._sessions.pop(session_token, None)
                logger.warning("Session expired for {}", session.student_id)
                raise PermissionError("登录已过期")
            return session.student_id

    def _to_user_info(self, user: User) -> UserInfo:
        return UserInfo(
            student_id=user.student_id,
            name=user.name,
            scnu_account=user.scnu_account,
        )

    def _hash_password(self, password: str) -> str:
        if self._pwd_context is not None:
            try:
                return self._pwd_context.hash(password)
            except Exception:
                logger.exception("Passlib hashing failed; falling back to PBKDF2")
                self._pwd_context = None

        iterations = 390000
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return (
            "pbkdf2_sha256"
            f"${iterations}"
            f"${base64.b64encode(salt).decode('ascii')}"
            f"${base64.b64encode(digest).decode('ascii')}"
        )

    def _verify_password(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith("pbkdf2_sha256$"):
            _, raw_iterations, salt_b64, digest_b64 = password_hash.split("$", maxsplit=3)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                base64.b64decode(salt_b64.encode("ascii")),
                int(raw_iterations),
            )
            expected = base64.b64decode(digest_b64.encode("ascii"))
            return hmac.compare_digest(actual, expected)

        if self._pwd_context is None:
            return False
        try:
            return self._pwd_context.verify(password, password_hash)
        except Exception:
            logger.exception("Passlib password verification failed")
            return False

    def _build_password_context(self) -> CryptContext | None:
        if CryptContext is None:
            logger.warning("passlib is unavailable; PBKDF2 password hashing will be used")
            return None

        try:
            bcrypt_module = importlib.import_module("bcrypt")
        except ImportError:
            logger.warning("bcrypt is unavailable; PBKDF2 password hashing will be used")
            return None

        if not hasattr(bcrypt_module, "__about__"):
            logger.warning("bcrypt compatibility check failed; PBKDF2 password hashing will be used")
            return None

        candidate = CryptContext(schemes=["bcrypt"], deprecated="auto")
        try:
            candidate.hash("compatibility-check")
        except Exception:
            logger.exception("Failed to initialize passlib bcrypt context; PBKDF2 password hashing will be used")
            return None
        return candidate
