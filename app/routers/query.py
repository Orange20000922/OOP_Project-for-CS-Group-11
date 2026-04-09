from fastapi import APIRouter, Cookie, HTTPException

from app.models.course import Course
from app.services import auth_service, schedule_service

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/now", response_model=Course | None)
async def query_now(session_token: str | None = Cookie(None)):
    """
    查询当前节次正在上的课。
    - 根据系统时间计算当前周次、星期几、第几节
    - 用 BST 在课表中查找对应课程
    - 若当前没课则返回 null
    """
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.get_current_course(student_id)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/today", response_model=list[Course])
async def query_today(session_token: str | None = Cookie(None)):
    """
    查询今天所有课程（有序列表）。
    - 用双向链表遍历今天的节点
    """
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.get_today_courses(student_id)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/week", response_model=dict[str, list[Course]])
async def query_week(session_token: str | None = Cookie(None)):
    """
    查询本周课表。
    - 返回格式: {"1": [...], "2": [...], ..., "7": [...]}  key 为星期几
    """
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.get_week_courses(student_id, week_offset=0)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/week/{offset}", response_model=dict[str, list[Course]])
async def query_week_offset(offset: int, session_token: str | None = Cookie(None)):
    """
    查询指定周课表（offset: 0=本周, -1=上周, +1=下周）。
    """
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.get_week_courses(student_id, week_offset=offset)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
