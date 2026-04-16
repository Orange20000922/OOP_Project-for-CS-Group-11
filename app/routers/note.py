from fastapi import APIRouter, Cookie, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.config import SESSION_COOKIE_NAME
from app.models.note import Note, NoteDetail, NoteUpdate
from app.services import auth_service, knowledge_service, note_service

router = APIRouter(prefix="/note", tags=["note"])


def _require_student_id(session_token: str | None) -> str:
    try:
        return auth_service.get_student_id(session_token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/upload", response_model=NoteDetail, status_code=status.HTTP_201_CREATED)
async def upload_note(
    file: UploadFile = File(...),
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

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

        try:
            knowledge_service.auto_assign_note(student_id, detail.note, detail.chunks)
        except Exception:
            pass

        return detail
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/list", response_model=list[Note])
async def list_notes(
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    return note_service.list_notes(student_id, course_id)


@router.get("/{note_id}", response_model=NoteDetail)
async def get_note(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    _require_student_id(session_token)

    detail = note_service.get_detail(note_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return detail


@router.put("/{note_id}", response_model=Note)
async def update_note(
    note_id: str,
    body: NoteUpdate,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

    try:
        original = note_service.get_detail(note_id)
        updated = note_service.update_metadata(student_id, note_id, body)

        try:
            if original is not None and original.note.course_id != updated.course_id:
                if original.note.course_id is not None:
                    knowledge_service.remove_note_from_topics(student_id, note_id, original.note.course_id)
                detail = note_service.get_detail(note_id)
                if detail is not None:
                    knowledge_service.auto_assign_note(student_id, updated, detail.chunks)
            else:
                knowledge_service.refresh_topics_for_note(student_id, updated)
        except Exception:
            pass

        return updated
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{note_id}/file")
async def get_note_file(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    _require_student_id(session_token)

    file_path = note_service.get_file_path(note_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

    try:
        detail = note_service.get_detail(note_id)

        # 删除向量索引（best-effort）
        try:
            knowledge_service.delete_note_vectors(student_id, note_id)
        except Exception:
            pass

        if detail is not None and detail.note.course_id is not None:
            try:
                knowledge_service.remove_note_from_topics(student_id, note_id, detail.note.course_id)
            except Exception:
                pass

        note_service.delete(student_id, note_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
