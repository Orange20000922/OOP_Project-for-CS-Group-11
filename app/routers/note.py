from fastapi import APIRouter, Cookie, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import SESSION_COOKIE_NAME
from app.services import auth_service, knowledge_service, note_service

router = APIRouter(prefix="/note", tags=["note"])


@router.post("/upload")
async def upload_note(
    file: UploadFile = File(...),
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        content = await file.read()
        detail = note_service.upload(student_id, file.filename or "unknown", content, course_id)

        # 异步建立向量索引（best-effort）
        try:
            knowledge_service.index_chunks(student_id, detail.chunks)
        except Exception:
            pass  # 向量索引失败不阻塞上传

        # 异步生成摘要（best-effort）
        try:
            summary_data = knowledge_service.generate_summary(detail.chunks)
            if summary_data["title"] or summary_data["summary"]:
                detail.note.title = summary_data["title"]
                detail.note.summary = summary_data["summary"]
                note_service._store.update_note(detail.note)
        except Exception:
            pass

        return detail.model_dump()
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/list")
async def list_notes(
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    notes = note_service.list_notes(student_id, course_id)
    return [n.model_dump() for n in notes]


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    detail = note_service.get_detail(note_id)
    if detail is None:
        return JSONResponse({"error": "笔记不存在"}, status_code=404)
    return detail.model_dump()


@router.get("/{note_id}/file")
async def get_note_file(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    file_path = note_service.get_file_path(note_id)
    if file_path is None:
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    return FileResponse(str(file_path))


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        # 删除向量索引（best-effort）
        try:
            knowledge_service.delete_note_vectors(student_id, note_id)
        except Exception:
            pass

        note_service.delete(student_id, note_id)
        return {"message": "已删除"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
