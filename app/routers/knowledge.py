from fastapi import APIRouter, Cookie, HTTPException, Query

from app.config import SESSION_COOKIE_NAME
from app.models.knowledge import KnowledgeTopicAssign, KnowledgeTopicCreate, KnowledgeTopicUpdate, KnowledgeTree
from app.models.note import AskRequest, AskResponse, GraphResponse, SearchRequest, SearchResult
from app.services import auth_service, knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _require_student_id(session_token: str | None) -> str:
    try:
        return auth_service.get_student_id(session_token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/search", response_model=list[SearchResult])
async def search_knowledge(
    body: SearchRequest,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

    try:
        return knowledge_service.search(student_id, body.query, body.limit, course_id=body.course_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ask", response_model=AskResponse)
async def ask_knowledge(
    body: AskRequest,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

    try:
        answer, sources = knowledge_service.ask(student_id, body.question, course_id=body.course_id)
        return {
            "answer": answer,
            "sources": sources,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tree", response_model=KnowledgeTree)
async def get_knowledge_tree(
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    return knowledge_service.get_tree(student_id, course_id)


@router.post("/tree/topic", response_model=KnowledgeTree)
async def create_knowledge_topic(
    body: KnowledgeTopicCreate,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    try:
        return knowledge_service.create_topic(student_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/tree/topic/{topic_id}", response_model=KnowledgeTree)
async def update_knowledge_topic(
    topic_id: str,
    body: KnowledgeTopicUpdate,
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    try:
        return knowledge_service.update_topic(student_id, course_id, topic_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/tree/topic/{topic_id}", response_model=KnowledgeTree)
async def delete_knowledge_topic(
    topic_id: str,
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    try:
        return knowledge_service.delete_topic(student_id, course_id, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tree/topic/{topic_id}/assign", response_model=KnowledgeTree)
async def assign_note_to_knowledge_topic(
    topic_id: str,
    body: KnowledgeTopicAssign,
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    try:
        return knowledge_service.assign_note_to_topic(
            student_id=student_id,
            course_id=body.course_id,
            topic_id=topic_id,
            note_id=body.note_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete("/tree/topic/{topic_id}/assign/{note_id}", response_model=KnowledgeTree)
async def unassign_note_from_knowledge_topic(
    topic_id: str,
    note_id: str,
    course_id: str | None = Query(default=None),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)
    try:
        return knowledge_service.unassign_note_from_topic(student_id, course_id, topic_id, note_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(
    course_id: str | None = Query(default=None),
    top_k: int = Query(default=3, ge=1, le=10),
    min_score: float = Query(default=0.5, ge=0.0, le=1.0),
    max_nodes: int = Query(default=120, ge=1, le=300),
    query: str = Query(default=""),
    topic_id: str | None = Query(default=None),
    topic_limit: int = Query(default=3, ge=1, le=10),
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    student_id = _require_student_id(session_token)

    try:
        return knowledge_service.build_graph(
            student_id=student_id,
            course_id=course_id,
            top_k=top_k,
            min_score=min_score,
            max_nodes=max_nodes,
            query=query,
            topic_id=topic_id,
            topic_limit=topic_limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
