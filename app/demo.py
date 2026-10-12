"""Public, read-only example corpus. Never reads account documents or calls paid APIs."""
from time import perf_counter
from fastapi import APIRouter
from app.config import Settings
from app.models import AskRequest, AskResponse, SourceChunk
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix='/api/demo')
CORPUS = [
    ('engineering-handbook', 'Engineering handbook.pdf', 1, 'The deployment process requires a pull request, passing automated tests and one reviewer approval. Deployments run on Tuesday and Thursday. Rollback restores the previous release.'),
    ('engineering-handbook', 'Engineering handbook.pdf', 2, 'Production incidents are triaged by the on-call engineer. Severity one incidents require an update every 30 minutes. A blameless review is written within two working days.'),
    ('api-design', 'API design notes.pdf', 1, 'API rate limits protect the service. The API rate limits are 5 requests per 10 seconds for bursts and 30 requests per minute for sustained traffic. Rejected requests return HTTP 429 with a Retry-After header.'),
    ('security-guide', 'Security checklist.pdf', 1, 'API keys are shown once and stored as SHA-256 hashes. Never commit credentials. Rotate a compromised key immediately. Administrative endpoints require a separate secret.'),
]

@router.get('/documents')
def documents():
    return {'documents': [{'document_id': id, 'filename': name, 'pages': sum(1 for c in CORPUS if c[0] == id), 'chunks': sum(1 for c in CORPUS if c[0] == id)} for id, name in dict((c[0], c[1]) for c in CORPUS).items()]}

@router.post('/ask', response_model=AskResponse)
async def ask(payload: AskRequest):
    started = perf_counter()
    service = EmbeddingService(Settings(_env_file=None, embedding_provider='hash', embedding_dimension=768))
    vectors = await service.embed_texts([c[3] for c in CORPUS])
    query = await service.embed_query(payload.question)
    scores = (vectors @ query[0]).tolist()
    ranked = sorted(range(len(CORPUS)), key=lambda i: scores[i], reverse=True)
    sources = []
    for i in ranked:
        id, name, page, text = CORPUS[i]
        if scores[i] < .20 or (payload.document_id and id != payload.document_id): continue
        sources.append(SourceChunk(document_id=id, filename=name, page=page, chunk_id=str(i), score=scores[i], text=text))
        if len(sources) >= (payload.top_k or 3): break
    answer = '\n\n'.join(f'{s.text} [S{i}]' for i, s in enumerate(sources, 1)) if sources else "There isn't enough evidence in this sample workspace to answer that question."
    return AskResponse(answer=answer, sources=sources, evidence_status='retrieval_only' if sources else 'insufficient', retrieval_mode='hash', elapsed_ms=round((perf_counter()-started)*1000))
