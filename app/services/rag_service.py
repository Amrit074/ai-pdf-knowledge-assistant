from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import Settings
from app.models import SourceChunk
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMClient
from app.services.pdf_service import PDFService
from app.services.vector_store import DocumentMetadata, VectorStore
from app.utils.text import split_text


class RAGService:
    def __init__(
        self,
        settings: Settings,
        pdf_service: PDFService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        llm_client: LLMClient,
    ) -> None:
        self.settings = settings
        self.pdf_service = pdf_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.upload_dir = settings.resolve_path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_pdf(self, file: UploadFile, progress=None) -> DocumentMetadata:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

        temp_dir = self.upload_dir / "_incoming"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{uuid4().hex}-{Path(file.filename).name}"
        content = await file.read(self.settings.max_upload_mb * 1024 * 1024 + 1)
        if len(content) > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"PDF exceeds {self.settings.max_upload_mb} MB limit.")
        if not content:
            raise ValueError("Uploaded PDF is empty.")
        temp_path.write_bytes(content)

        if progress: progress("extracting")
        try:
            pages = self.pdf_service.extract_pages(temp_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        page_chunks: list[tuple[int, str]] = []
        for page in pages:
            chunks = split_text(page.text, self.settings.chunk_size, self.settings.chunk_overlap)
            page_chunks.extend((page.page, chunk) for chunk in chunks)

        if not page_chunks:
            temp_path.unlink(missing_ok=True)
            raise ValueError("No extractable text found. Scanned PDFs need OCR before upload.")

        try:
            if progress: progress("embedding")
            embeddings = await self.embedding_service.embed_texts([text for _, text in page_chunks])
            if progress: progress("indexing")
            document = self.vector_store.add_document(Path(file.filename).name, page_chunks, embeddings)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        document_dir = self.upload_dir / document.document_id
        try:
            document_dir.mkdir(parents=True, exist_ok=True)
            final_path = document_dir / Path(file.filename).name
            temp_path.replace(final_path)
        except Exception:
            self.vector_store.delete_document(document.document_id, self.upload_dir)
            temp_path.unlink(missing_ok=True)
            raise
        return document

    async def ask(self, question: str, top_k: int, document_id: str | None = None, allowed_document_ids: set[str] | None = None) -> tuple[str, list[SourceChunk]]:
        query_embedding = await self.embedding_service.embed_query(question)
        results = self.vector_store.search(query_embedding, top_k=top_k, document_id=document_id, allowed_document_ids=allowed_document_ids)
        results = [result for result in results if result.score >= self.settings.min_retrieval_score]
        if not results:
            return "I don't have enough supporting evidence in your documents to answer this. Try a more specific question or upload a relevant PDF.", []

        sources = [
            SourceChunk(
                document_id=result.metadata.document_id,
                filename=result.metadata.filename,
                page=result.metadata.page,
                chunk_id=result.metadata.chunk_id,
                score=result.score,
                text=result.metadata.text,
            )
            for result in results
        ]
        context = "\n\n".join(
            f"[S{number}] {source.filename}, page {source.page}\n{source.text}"
            for number, source in enumerate(sources, start=1)
        )
        answer = await self.llm_client.answer(question, context)
        return answer, sources
