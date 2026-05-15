import hashlib
import logging
import math
import re

import httpx
import numpy as np

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.provider = settings.embedding_provider.lower()
        self.model_name = settings.embedding_model
        self.gemini_api_key = settings.gemini_api_key
        self.batch_size = settings.embedding_batch_size
        self._dimension = settings.embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype="float32")
        if self.provider == "gemini":
            return await self._embed_with_gemini(texts, task_type="RETRIEVAL_DOCUMENT")
        return self._embed_with_hashing(texts)

    async def embed_query(self, question: str) -> np.ndarray:
        if self.provider == "gemini":
            return await self._embed_with_gemini([question], task_type="RETRIEVAL_QUERY")
        return self._embed_with_hashing([question])

    async def _embed_with_gemini(self, texts: list[str], task_type: str) -> np.ndarray:
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini.")

        model = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents"
        vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60) as client:
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                payload = {
                    "requests": [
                        {
                            "model": model,
                            "content": {"parts": [{"text": text}]},
                            "taskType": task_type,
                            "outputDimensionality": self.dimension,
                        }
                        for text in batch
                    ]
                }
                response = await client.post(url, params={"key": self.gemini_api_key}, json=payload)
                response.raise_for_status()
                data = response.json()
                vectors.extend(item["values"] for item in data.get("embeddings", []))

        embeddings = np.asarray(vectors, dtype="float32")
        return self._normalize(embeddings)

    def _embed_with_hashing(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            tokens = re.findall(r"\b\w+\b", text.lower())
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vectors[row, index] += sign
        return self._normalize(vectors)

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        if vectors.size == 0:
            return vectors.astype("float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = math.sqrt(self.dimension)
        return (vectors / norms).astype("float32")
