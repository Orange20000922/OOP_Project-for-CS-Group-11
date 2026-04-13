from fastapi import APIRouter, Cookie, File, HTTPException, Response, UploadFile, status

from app.logging_config import logger
from app.models.course import Course, CourseCreate, FetchTaskStatus, SCNUFetchRequest, Schedule, ScheduleInit
from app.services import auth_service, schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=Schedule)
async def get_schedule(session_token: str | None = Cookie(None)):
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.get_schedule(student_id)
    except PermissionError as exc:
        logger.warning("Get schedule request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Get schedule request failed with schedule error: {}", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def init_schedule(body: ScheduleInit, session_token: str | None = Cookie(None)):
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.initialize_schedule(student_id, body)
    except PermissionError as exc:
        logger.warning("Init schedule request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Init schedule request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def upload_schedule(
    file: UploadFile = File(...),
    session_token: str | None = Cookie(None),
):
    try:
        student_id = auth_service.get_student_id(session_token)
        content = await file.read()
        return schedule_service.upload_schedule(
            student_id=student_id,
            filename=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
    except PermissionError as exc:
        logger.warning("Upload schedule request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Upload schedule request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Upload schedule request failed with parser error: {}", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/fetch", response_model=FetchTaskStatus, status_code=status.HTTP_202_ACCEPTED)
async def fetch_from_scnu(body: SCNUFetchRequest, session_token: str | None = Cookie(None)):
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.submit_scnu_fetch(student_id, body)
    except PermissionError as exc:
        logger.warning("Fetch schedule request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Fetch schedule request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/fetch/{task_id}", response_model=FetchTaskStatus)
async def get_fetch_status(task_id: str, session_token: str | None = Cookie(None)):
    try:
        auth_service.get_student_id(session_token)
        return schedule_service.get_fetch_task(task_id)
    except PermissionError as exc:
        logger.warning("Get fetch status request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Get fetch status request failed with task error: {}", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/course", status_code=201, response_model=Course)
async def add_course(course: CourseCreate, session_token: str | None = Cookie(None)):
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.add_course(student_id, course)
    except PermissionError as exc:
        logger.warning("Add course request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Add course request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/course/{course_id}", response_model=Course)
async def update_course(
    course_id: str,
    course: CourseCreate,
    session_token: str | None = Cookie(None),
):
    try:
        student_id = auth_service.get_student_id(session_token)
        return schedule_service.update_course(student_id, course_id, course)
    except PermissionError as exc:
        logger.warning("Update course request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Update course request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/course/{course_id}", status_code=204)
async def delete_course(course_id: str, session_token: str | None = Cookie(None)):
    try:
        student_id = auth_service.get_student_id(session_token)
        schedule_service.delete_course(student_id, course_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except PermissionError as exc:
        logger.warning("Delete course request failed with auth error: {}", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Delete course request failed with validation error: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
