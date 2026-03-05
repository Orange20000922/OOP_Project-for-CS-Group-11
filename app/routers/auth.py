from fastapi import APIRouter, Response, Cookie, HTTPException
from app.models.user import UserCreate, UserLogin, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(user: UserCreate):
    """注册新用户（学号 + 姓名 + 密码）"""
    # TODO: 调用 user_store 检查学号是否已存在
    # TODO: 对密码哈希后存储
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/login")
async def login(credentials: UserLogin, response: Response):
    """登录，成功后通过 Set-Cookie 返回 session_token"""
    # TODO: 调用 auth_service.login()
    # TODO: response.set_cookie(key="session_token", value=token, httponly=True)
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/logout")
async def logout(response: Response, session_token: str | None = Cookie(None)):
    """登出，清除 Cookie 并从 Session 哈希表移除"""
    # TODO: 调用 auth_service.logout(session_token)
    response.delete_cookie("session_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
async def me(session_token: str | None = Cookie(None)):
    """获取当前登录用户信息"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: 调用 auth_service.get_current_user(session_token)
    raise HTTPException(status_code=501, detail="Not implemented")
