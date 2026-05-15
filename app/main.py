import logging

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError

from app.config import get_settings
from app.dependencies import get_rag_service, get_vector_store
from app.logging_config import configure_logging
from app.models import AskRequest, AskResponse, DeleteResponse, DocumentListResponse, ErrorResponse, UploadResponse
from app.services.rag_service import RAGService
from app.services.vector_store import VectorStore

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="RAG-based AI assistant for asking questions about uploaded PDFs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


@app.post("/api/documents", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service),
) -> UploadResponse:
    try:
        document = await rag_service.upload_pdf(file)
        return UploadResponse(message="PDF uploaded and indexed successfully.", document=document)
    except HTTPError as exc:
        logger.exception("Embedding API error")
        raise HTTPException(status_code=502, detail=f"Embedding provider request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(vector_store: VectorStore = Depends(get_vector_store)) -> DocumentListResponse:
    return DocumentListResponse(documents=vector_store.list_documents())


@app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> DeleteResponse:
    try:
        deleted = vector_store.delete_document(document_id, settings.resolve_path(settings.upload_dir))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DeleteResponse(message="Document deleted successfully.")


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(
    payload: AskRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> AskResponse:
    try:
        top_k = payload.top_k or settings.top_k
        answer, sources = await rag_service.ask(payload.question, top_k=top_k, document_id=payload.document_id)
        return AskResponse(answer=answer, sources=sources)
    except HTTPError as exc:
        logger.exception("AI provider API error")
        raise HTTPException(status_code=502, detail=f"AI provider request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.mount("/", StaticFiles(directory="static", html=True), name="static")
