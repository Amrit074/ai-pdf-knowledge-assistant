import json
import logging
import pickle
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import faiss
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    chunk_id: str
    document_id: str
    filename: str
    page: int
    text: str


@dataclass
class DocumentMetadata:
    document_id: str
    filename: str
    pages: int
    chunks: int
    uploaded_at: str


@dataclass
class SearchResult:
    metadata: ChunkMetadata
    score: float


class VectorStore:
    def __init__(self, index_dir: Path, dimension: int) -> None:
        self.index_dir = index_dir
        self.dimension = dimension
        self.index_path = index_dir / "documents.faiss"
        self.embeddings_path = index_dir / "embeddings.npy"
        self.chunks_path = index_dir / "chunks.pkl"
        self.documents_path = index_dir / "documents.json"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index = self._load_index()
        self.embeddings = self._load_embeddings()
        self.chunks = self._load_chunks()
        self.documents = self._load_documents()
        self._ensure_index_consistency()

    def _load_index(self) -> faiss.Index:
        if self.index_path.exists():
            index = faiss.read_index(str(self.index_path))
            if index.d != self.dimension:
                logger.warning(
                    "Ignoring FAISS index with dimension %s because configured dimension is %s",
                    index.d,
                    self.dimension,
                )
                return faiss.IndexFlatIP(self.dimension)
            return index
        return faiss.IndexFlatIP(self.dimension)

    def _load_chunks(self) -> list[ChunkMetadata]:
        if not self.chunks_path.exists():
            return []
        with self.chunks_path.open("rb") as file:
            chunks = pickle.load(file)
        if len(chunks) != len(self.embeddings):
            logger.warning("Ignoring chunk metadata because it does not match embedding count")
            return []
        return chunks

    def _load_embeddings(self) -> np.ndarray:
        if self.embeddings_path.exists():
            embeddings = np.load(self.embeddings_path).astype("float32")
            if embeddings.ndim != 2 or embeddings.shape[1] != self.dimension:
                logger.warning(
                    "Ignoring embeddings with shape %s because configured dimension is %s",
                    embeddings.shape,
                    self.dimension,
                )
                return np.empty((0, self.dimension), dtype="float32")
            return embeddings
        return np.empty((0, self.dimension), dtype="float32")

    def _load_documents(self) -> dict[str, DocumentMetadata]:
        if not self.documents_path.exists():
            return {}
        if not self.chunks:
            logger.warning("Ignoring document metadata because no compatible chunks are loaded")
            return {}
        with self.documents_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return {doc_id: DocumentMetadata(**value) for doc_id, value in raw.items()}

    def save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        np.save(self.embeddings_path, self.embeddings)
        with self.chunks_path.open("wb") as file:
            pickle.dump(self.chunks, file)
        with self.documents_path.open("w", encoding="utf-8") as file:
            json.dump({key: asdict(value) for key, value in self.documents.items()}, file, indent=2)

    def _ensure_index_consistency(self) -> None:
        if self.index.ntotal == len(self.embeddings) == len(self.chunks):
            return
        logger.warning(
            "Rebuilding FAISS index because index=%s embeddings=%s chunks=%s",
            self.index.ntotal,
            len(self.embeddings),
            len(self.chunks),
        )
        self.index = faiss.IndexFlatIP(self.dimension)
        if len(self.embeddings) and len(self.embeddings) == len(self.chunks):
            self.index.add(self.embeddings)
        else:
            self.embeddings = np.empty((0, self.dimension), dtype="float32")
            self.chunks = []
            self.documents = {}
        self.save()

    def add_document(
        self,
        filename: str,
        page_chunks: list[tuple[int, str]],
        embeddings: np.ndarray,
    ) -> DocumentMetadata:
        if len(page_chunks) != len(embeddings):
            raise ValueError("Chunk count and embedding count do not match.")

        document_id = uuid4().hex
        metadata = [
            ChunkMetadata(
                chunk_id=uuid4().hex,
                document_id=document_id,
                filename=filename,
                page=page,
                text=text,
            )
            for page, text in page_chunks
        ]

        if len(embeddings):
            self.index.add(embeddings)
            self.embeddings = np.vstack([self.embeddings, embeddings]).astype("float32")
            self.chunks.extend(metadata)

        document = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            pages=len({page for page, _ in page_chunks}),
            chunks=len(page_chunks),
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )
        self.documents[document_id] = document
        self.save()
        logger.info("Indexed document %s with %s chunks", filename, len(page_chunks))
        return document

    def search(self, query_embedding: np.ndarray, top_k: int, document_id: str | None = None) -> list[SearchResult]:
        if self.index.ntotal == 0:
            return []

        top_n = min(max(top_k * 5 if document_id else top_k, top_k), self.index.ntotal)
        scores, indices = self.index.search(query_embedding, top_n)
        results: list[SearchResult] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self.chunks[int(idx)]
            if document_id and chunk.document_id != document_id:
                continue
            results.append(SearchResult(metadata=chunk, score=float(score)))
            if len(results) >= top_k:
                break

        return results

    def list_documents(self) -> list[DocumentMetadata]:
        return sorted(self.documents.values(), key=lambda item: item.uploaded_at, reverse=True)

    def delete_document(self, document_id: str, upload_dir: Path) -> bool:
        if document_id not in self.documents:
            return False

        keep_indices = [index for index, chunk in enumerate(self.chunks) if chunk.document_id != document_id]
        self.chunks = [self.chunks[index] for index in keep_indices]
        del self.documents[document_id]

        self.index = faiss.IndexFlatIP(self.dimension)
        self.embeddings = self.embeddings[keep_indices] if keep_indices else np.empty((0, self.dimension), dtype="float32")
        if len(self.embeddings):
            self.index.add(self.embeddings)

        document_upload_dir = upload_dir / document_id
        if document_upload_dir.exists():
            shutil.rmtree(document_upload_dir)

        self.save()
        return True
