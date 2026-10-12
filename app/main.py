import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user
from app.config import get_settings
from app.database import Base, engine, get_db
from app.db_models import ChatHistory, Document, User, IngestionJob
from app.dependencies import get_rag_service, get_vector_store
from app.logging_config import configure_logging
from app.models import (
    AskRequest,
    AskResponse,
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    ErrorResponse,
    UploadResponse,
    ChatHistoryItem,
    ChatHistoryResponse,
    UserProfile,
)
from app.services.rag_service import RAGService
from app.services.vector_store import VectorStore

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


def to_document_info(document) -> DocumentInfo:
    return DocumentInfo(
        document_id=document.document_id,
        filename=document.filename,
        pages=document.pages,
        chunks=document.chunks,
        uploaded_at=document.uploaded_at,
    )

oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.resolve_path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.execute(update(IngestionJob).where(IngestionJob.status.in_(["queued", "extracting", "embedding", "indexing"])).values(status="failed", error="Processing interrupted by restart. Please upload again."))
        db.commit()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="RAG-based AI assistant for asking questions about uploaded PDFs.",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.oauth_state_secret, https_only=settings.app_env == "production", same_site="lax")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content=ErrorResponse(detail="Internal server error.").model_dump())


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    return {"success": True, "status": "ok"}


@app.get("/api/auth/google/login")
async def google_login(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    token = await oauth.google.authorize_access_token(request)
    profile = token.get("userinfo") or await oauth.google.userinfo(token=token)
    google_id, email = profile.get("sub"), profile.get("email")
    if not google_id or not email or profile.get("email_verified") is not True:
        raise HTTPException(status_code=400, detail="Google did not return a verified email address.")
    user = db.scalar(select(User).where(User.google_id == google_id))
    if user is None:
        user = User(google_id=google_id, email=email, name=profile.get("name") or email, profile_picture=profile.get("picture"))
        db.add(user)
    else:
        user.email, user.name, user.profile_picture = email, profile.get("name") or email, profile.get("picture")
    db.commit()
    db.refresh(user)
    return RedirectResponse(url=f"{settings.frontend_url.rstrip('/')}#token={create_access_token(user)}", status_code=303)


@app.get("/api/auth/me", response_model=UserProfile)
async def current_profile(user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile(id=user.id, email=user.email, name=user.name, profile_picture=user.profile_picture)


@app.post("/api/documents", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    try:
        document = await rag_service.upload_pdf(file)
        db.add(Document(document_id=document.document_id, user_id=user.id, filename=document.filename, pages=document.pages, chunks=document.chunks))
        db.commit()
        return UploadResponse(message="PDF uploaded and indexed successfully.", document=to_document_info(document))
    except HTTPError as exc:
        logger.exception("Embedding API error")
        raise HTTPException(status_code=502, detail=f"Embedding provider request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DocumentListResponse:
    documents = db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.uploaded_at.desc())).all()
    return DocumentListResponse(documents=[DocumentInfo(document_id=item.document_id, filename=item.filename, pages=item.pages, chunks=item.chunks, uploaded_at=item.uploaded_at.isoformat()) for item in documents])


@app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    document = db.scalar(select(Document).where(Document.document_id == document_id, Document.user_id == user.id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        deleted = vector_store.delete_document(document_id, settings.resolve_path(settings.upload_dir))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.execute(update(ChatHistory).where(ChatHistory.document_id == document_id).values(document_id=None))
    db.delete(document)
    db.commit()
    return DeleteResponse(message="Document deleted successfully.")


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(
    payload: AskRequest,
    rag_service: RAGService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    started = perf_counter()
    try:
        top_k = payload.top_k or settings.top_k
        owned_ids = set(db.scalars(select(Document.document_id).where(Document.user_id == user.id)).all())
        if payload.document_id and payload.document_id not in owned_ids:
            raise HTTPException(status_code=404, detail="Document not found.")
        answer, sources = await rag_service.ask(payload.question, top_k=top_k, document_id=payload.document_id, allowed_document_ids=owned_ids)
        db.add(ChatHistory(user_id=user.id, document_id=payload.document_id, question=payload.question, answer=answer))
        db.commit()
        return AskResponse(answer=answer, sources=sources,
            evidence_status="insufficient" if not sources else ("retrieval_only" if settings.llm_provider == "mock" else "retrieved"),
            retrieval_mode=settings.embedding_provider, elapsed_ms=round((perf_counter()-started)*1000))
    except HTTPError as exc:
        logger.exception("AI provider API error")
        raise HTTPException(status_code=502, detail=f"AI provider request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/chat-history", response_model=ChatHistoryResponse)
async def chat_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatHistoryResponse:
    entries = db.scalars(select(ChatHistory).where(ChatHistory.user_id == user.id).order_by(ChatHistory.created_at.desc())).all()
    return ChatHistoryResponse(conversations=[ChatHistoryItem(id=item.id, document_id=item.document_id, question=item.question, answer=item.answer, created_at=item.created_at.isoformat()) for item in entries])


from app.ingestion import router as ingestion_router
app.include_router(ingestion_router)
from app.demo import router as demo_router
app.include_router(demo_router)

@app.get("/api/capabilities")
async def capabilities():
    return {"google_login": bool(settings.google_client_id and settings.google_client_secret),
            "retrieval_mode": settings.embedding_provider, "answer_mode": settings.llm_provider,
            "max_upload_mb": settings.max_upload_mb, "min_retrieval_score": settings.min_retrieval_score}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
