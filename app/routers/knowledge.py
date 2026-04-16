from fastapi import APIRouter, Cookie, Query
from fastapi.responses import JSONResponse

from app.config import SESSION_COOKIE_NAME
from app.models.note import AskRequest, GraphResponse, SearchRequest
from app.services import auth_service, knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search")
async def search_knowledge(
    body: SearchRequest,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        results = knowledge_service.search(student_id, body.query, body.limit)
        return [r.model_dump() for r in results]
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.post("/ask")
async def ask_knowledge(
    body: AskRequest,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        answer, sources = knowledge_service.ask(student_id, body.question)
        return {
            "answer": answer,
            "sources": [s.model_dump() for s in sources],
        }
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(
    course_id: str | None = Query(default=None),
    top_k: int = Query(default=3, ge=1, le=10),
    min_score: float = Query(default=0.5, ge=0.0, le=1.0),
    max_nodes: int = Query(default=120, ge=1, le=300),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    try:
        student_id = auth_service.get_student_id(session_token)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        graph = knowledge_service.build_graph(
            student_id=student_id,
            course_id=course_id,
            top_k=top_k,
            min_score=min_score,
            max_nodes=max_nodes,
        )
        return graph
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
