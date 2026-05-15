import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a PDF Knowledge Assistant. Answer only from the supplied context.
If the context does not contain the answer, say you could not find the answer in the uploaded documents.
Be concise, accurate, and include page references when useful."""


class LLMClient(ABC):
    @abstractmethod
    async def answer(self, question: str, context: str) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def answer(self, question: str, context: str) -> str:
        return (
            "LLM_PROVIDER is set to mock, so this is a retrieval-only response. "
            "Set Gemini or OpenAI credentials in .env for generated answers.\n\n"
            f"Question: {question}\n\nMost relevant context:\n{context[:1600]}"
        )


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def answer(self, question: str, context: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\n"
                                f"Question: {question}\n\nAnswer:"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        headers = {"x-goog-api-key": self.api_key}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def answer(self, question: str, context: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:",
                },
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        return OpenAIClient(settings.openai_api_key, settings.openai_model)
    return MockLLMClient()
