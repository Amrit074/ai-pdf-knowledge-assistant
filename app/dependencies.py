from functools import lru_cache

from app.config import get_settings
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import build_llm_client
from app.services.pdf_service import PDFService
from app.services.rag_service import RAGService
from app.services.vector_store import VectorStore


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(settings.embedding_model)


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    embedding_service = get_embedding_service()
    return VectorStore(settings.resolve_path(settings.index_dir), embedding_service.dimension)


@lru_cache
def get_rag_service() -> RAGService:
    settings = get_settings()
    return RAGService(
        settings=settings,
        pdf_service=PDFService(),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
        llm_client=build_llm_client(settings),
    )
