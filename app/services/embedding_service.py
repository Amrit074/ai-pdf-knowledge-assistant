import logging
from functools import cached_property

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def model(self) -> SentenceTransformer:
        logger.info("Loading embedding model: %s", self.model_name)
        return SentenceTransformer(self.model_name)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype="float32")
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype="float32")

    def embed_query(self, question: str) -> np.ndarray:
        vector = self.model.encode([question], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vector, dtype="float32")

    @cached_property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())
