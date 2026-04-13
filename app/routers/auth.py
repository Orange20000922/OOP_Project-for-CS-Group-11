from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.config import (
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_EXPIRE_SECONDS,
)
from app.logging_config import logger
from app.models.user import UserCreate, UserInfo, UserLogin
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    try:
        return auth_service.register(user)
    except ValueError as exc:
        logger.warning("Register request failed for {}: {}", user.student_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=UserInfo)
async def login(credentials: UserLogin, response: Response):
    try:
        token, user = auth_service.login(credentials)
    except PermissionError as exc:
        logger.warning("Login request failed for {}: {}", credentials.student_id, exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRE_SECONDS,
        httponly=SESSION_COOKIE_HTTPONLY,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=SESSION_COOKIE_SECURE,
    )
    logger.info("Login request succeeded for {}", user.student_id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session_token: str | None = Cookie(None)):
    auth_service.logout(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.status_code = status.HTTP_204_NO_CONTENT
    logger.info("Logout request completed")
    return response


@router.get("/me", response_model=UserInfo)
async def me(session_token: str | None = Cookie(None)):
    try:
        return auth_service.get_current_user(session_token)
    except PermissionError as exc:
        logger.warning("Current user request failed: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
