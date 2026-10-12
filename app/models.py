from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    document_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_id: str
    score: float
    text: str


class AskResponse(BaseModel):
    success: bool = True
    answer: str
    sources: list[SourceChunk]
    evidence_status: str = "retrieved"
    retrieval_mode: str = "hash"
    elapsed_ms: int = 0


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    pages: int
    chunks: int
    uploaded_at: str


class UploadResponse(BaseModel):
    success: bool = True
    message: str
    document: DocumentInfo


class DocumentListResponse(BaseModel):
    success: bool = True
    documents: list[DocumentInfo]


class DeleteResponse(BaseModel):
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    detail: str


class UserProfile(BaseModel):
    id: int
    email: str
    name: str
    profile_picture: str | None = None


class ChatHistoryItem(BaseModel):
    id: int
    document_id: str | None
    question: str
    answer: str
    created_at: str


class ChatHistoryResponse(BaseModel):
    success: bool = True
    conversations: list[ChatHistoryItem]
