from fastapi import APIRouter, Cookie, HTTPException, UploadFile, File
from app.models.course import Course, CourseCreate, Schedule, ScheduleInit, SCNUFetchRequest

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=Schedule)
async def get_schedule(session_token: str | None = Cookie(None)):
    """获取当前登录用户的完整课表"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: auth_service.get_current_user() -> student_id
    # TODO: schedule_store.get(student_id) -> Schedule
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("", status_code=201)
async def init_schedule(body: ScheduleInit, session_token: str | None = Cookie(None)):
    """初始化课表（设置学期和开学日期，首次使用时调用）"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: schedule_store.init(student_id, body.semester, body.semester_start)
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/upload", status_code=201)
async def upload_schedule(
    file: UploadFile = File(...),
    session_token: str | None = Cookie(None),
):
    """上传 JSON 或 PDF 课表文件"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: 根据 file.content_type 分别处理 JSON / PDF
    # TODO: JSON → 直接反序列化；PDF → scnu_scraper.parse_pdf()
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/fetch", status_code=202)
async def fetch_from_scnu(body: SCNUFetchRequest, session_token: str | None = Cookie(None)):
    """从华南师大强智教务平台抓取课表（异步任务入队）"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: task_queue.enqueue({student_id, scnu_password, semester_id})
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/course", status_code=201, response_model=Course)
async def add_course(course: CourseCreate, session_token: str | None = Cookie(None)):
    """手动新增单门课程"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: schedule_store.add_course(student_id, course) -> Course
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/course/{course_id}", response_model=Course)
async def update_course(
    course_id: str,
    course: CourseCreate,
    session_token: str | None = Cookie(None),
):
    """修改某门课程"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: schedule_store.update_course(student_id, course_id, course)
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/course/{course_id}", status_code=204)
async def delete_course(course_id: str, session_token: str | None = Cookie(None)):
    """删除某门课程"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # TODO: schedule_store.delete_course(student_id, course_id)
    raise HTTPException(status_code=501, detail="Not implemented")
