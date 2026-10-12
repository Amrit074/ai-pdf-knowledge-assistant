# Folio — Answers with evidence

A responsive PDF research workspace with a paper-and-sage interface, authenticated personal libraries, observable ingestion, and inspectable source excerpts.

## New workspace

- A **read-only sample** works immediately without OAuth or paid provider keys. Its three documents are fictional and its answers are retrieved excerpts, not generated model answers.
- Signed-in users can upload PDFs, watch queued/extracting/embedding/indexing/ready or failed stages, choose a document scope, inspect citations, and open the original PDF page.
- Retrieval below `MIN_RETRIEVAL_SCORE` is discarded; no supporting chunks means an insufficient-evidence response before any LLM call. Similarity is not confidence.
- File access, jobs, documents, history, and query scope are restricted to their owner. Source text is rendered as text rather than injected HTML.

## Quick start

```sh
python -m venv .venv
# Activate the environment for your shell.
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit `http://localhost:8000` for the sample. To use private uploads, configure Google OAuth and matching callback/frontend URLs using `.env.example`. Hash/mock defaults require no provider key. Gemini/OpenAI modes require your own credentials. Use HTTPS and strong distinct JWT/OAuth-state secrets in production.

```sh
python -m unittest discover -s tests -v
```

## Deployment boundaries

Run **one application worker** with persistent storage for SQLite, PDFs, vectors, and metadata. Upload processing uses in-process BackgroundTasks, not a durable queue; restart marks interrupted jobs failed. The 10 MB default upload limit is configurable with `MAX_UPLOAD_MB`; it is not a complete bound on extracted text or provider cost. Scanned PDFs require OCR outside this app. Prompt instructions and displayed citations do not guarantee factual correctness or prompt-injection immunity.

The sample regression questions are not a held-out retrieval benchmark. Cloud OAuth and paid providers need a separate deployment smoke test.

Read [the engineering handbook](docs/PROJECT_HANDBOOK.md) for beginner explanations, diagrams, tables, code maps, exercises, and interview walkthroughs for all three projects.

[Download the illustrated PDF handbook](docs/Project_Engineering_Handbook.pdf).

---

## Existing configuration reference

# AI PDF Knowledge Assistant

AI PDF Knowledge Assistant is a full-stack Retrieval-Augmented Generation application that allows users to upload PDF documents and ask natural-language questions based on the uploaded content.

The system extracts text from PDFs, converts the content into configurable hash or Gemini embeddings, stores those embeddings in a FAISS vector index, retrieves the most relevant document chunks for a user query, and generates a contextual answer using an LLM provider such as Gemini or OpenAI.

## Key Features

- PDF upload and document management through a simple web interface
- FastAPI backend with clean, modular service architecture
- Text extraction from PDFs using PyMuPDF
- Text cleaning, chunking, and overlap-based document splitting
- Lightweight hashing embeddings for free cloud deployment
- Optional Gemini `gemini-embedding-001` embeddings for higher-quality retrieval
- FAISS vector search for fast semantic retrieval
- Retrieval-Augmented Generation with Gemini, OpenAI, or mock mode
- REST APIs for uploading, listing, deleting, and querying documents
- Structured JSON responses for frontend and API clients
- Centralized configuration through environment variables
- Logging and exception handling for production readiness
- Docker and Render deployment support

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| PDF Processing | PyMuPDF |
| Embeddings | Hashing Embeddings, Optional Gemini Embeddings |
| Vector Search | FAISS |
| LLM Providers | Gemini, OpenAI, Mock |
| Deployment | Docker, Render |

## Architecture

```text
User uploads PDF
        |
        v
FastAPI upload endpoint
        |
        v
PyMuPDF extracts text
        |
        v
Text is cleaned and split into chunks
        |
        v
The app creates document embeddings
        |
        v
FAISS stores vectors and metadata
        |
        v
User asks a question
        |
        v
Relevant chunks are retrieved from FAISS
        |
        v
Gemini/OpenAI generates a contextual answer
```

## Project Structure

```text
.
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- dependencies.py
|   |-- logging_config.py
|   |-- models.py
|   |-- services/
|   |   |-- embedding_service.py
|   |   |-- llm_service.py
|   |   |-- pdf_service.py
|   |   |-- rag_service.py
|   |   `-- vector_store.py
|   `-- utils/
|       `-- text.py
|-- static/
|   |-- index.html
|   |-- styles.css
|   `-- app.js
|-- Dockerfile
|-- Procfile
|-- render.yaml
|-- requirements.txt
`-- .env.example
```

## Environment Variables

The application is configured through environment variables. Use `.env.example` as the reference for required and optional settings.

| Variable | Description |
| --- | --- |
| `APP_NAME` | Application name |
| `APP_ENV` | Runtime environment |
| `LOG_LEVEL` | Logging level |
| `UPLOAD_DIR` | PDF upload storage path |
| `INDEX_DIR` | FAISS index and metadata storage path |
| `EMBEDDING_PROVIDER` | `gemini` or `hash` |
| `EMBEDDING_MODEL` | Embedding model name |
| `EMBEDDING_DIMENSION` | Embedding vector dimension |
| `EMBEDDING_BATCH_SIZE` | Number of chunks embedded per API request |
| `CHUNK_SIZE` | Maximum text chunk size |
| `CHUNK_OVERLAP` | Overlap between adjacent chunks |
| `TOP_K` | Default number of retrieved chunks. Higher values provide more context but use more LLM tokens. |
| `LLM_PROVIDER` | `gemini`, `openai`, or `mock` |
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Gemini model name |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI model name |

### Gemini Configuration

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_PROVIDER=hash
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSION=768
```

### OpenAI Configuration

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

### Mock Configuration

```env
LLM_PROVIDER=mock
```

Mock mode returns retrieval-focused responses without calling an external LLM API. It is useful for demos, testing, and deployments where an API key is not yet configured.

For free Render deployments, hash embeddings are recommended because they avoid PyTorch memory usage and do not require access to Gemini's embedding endpoint.

## API Reference

### Health Check

```http
GET /api/health
```

Returns the application health status.

### Upload PDF

```http
POST /api/documents
Content-Type: multipart/form-data
```

Form field:

```text
file: PDF document
```

Uploads a PDF, extracts text, creates chunks, generates embeddings, and stores vectors in FAISS.

### List Documents

```http
GET /api/documents
```

Returns all indexed PDF documents.

### Ask a Question

```http
POST /api/ask
Content-Type: application/json
```

Request body:

```json
{
  "question": "What are the main points in this document?",
  "document_id": null,
  "top_k": 5
}
```

Returns a generated answer and the retrieved source chunks used as context.

### Delete Document

```http
DELETE /api/documents/{document_id}
```

Deletes a document and rebuilds the FAISS index without that document.

## Deployment

The project includes Docker and Render configuration files for cloud deployment.

### Render

1. Connect the GitHub repository to Render.
2. Create a new Blueprint or Web Service.
3. Use the included `render.yaml` configuration.
4. Add the required environment variables in the Render dashboard.
5. Set `LLM_PROVIDER` to `gemini`, `openai`, or `mock`.
6. Add the matching API key if using Gemini or OpenAI.
7. Deploy the service.

The included Render configuration mounts persistent storage at `/app/storage` so uploaded PDFs, metadata, and FAISS index files can survive service restarts.

### Google OAuth and JWT setup

1. In Google Cloud Console, create an OAuth 2.0 **Web application** client.
2. Add `http://localhost:8000/api/auth/google/callback` locally, and
   `https://YOUR-RENDER-URL/api/auth/google/callback` in production, to its
   authorized redirect URIs.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
   `FRONTEND_URL`, `JWT_SECRET_KEY`, and `OAUTH_STATE_SECRET` as deployment
   secrets. Generate different long random values for the two secrets.
4. Deploy. The frontend redirects users to Google, receives the application's
   short-lived JWT in the URL fragment, stores it in browser storage, and sends
   it as `Authorization: Bearer <token>` for protected requests.

All document upload, list, query, delete, and chat-history endpoints require a
valid JWT. SQLite is the default persistent database and records Users,
Documents, and ChatHistory; set `DATABASE_URL` to a managed SQLAlchemy-compatible
database for a multi-instance deployment. The FAISS index remains file-backed,
so it must be on shared persistent storage when running more than one app instance.

## Multi-user security and interview notes

**OAuth vs JWT:** Google OAuth proves a user's identity without this application
handling a password. The application then issues its own signed, expiring JWT.
OAuth is the identity-provider exchange; the JWT is the compact credential used
to authorize this API's later calls.

**Why an application JWT:** The backend validates Google only during the OAuth
callback, maps the Google identity to a local user, and then controls its own
expiry and claims. Each protected request verifies the JWT signature and loads
the user, with no server-side session or refresh-token state.

**User isolation:** Each Document row has a `user_id`. List and delete queries
filter by that ID. For a query across all documents, the service passes only the
current user's document IDs into FAISS filtering; an explicit foreign document ID
returns `404`. Chat history is also queried by `user_id` only. This prevents both
direct-ID and broad semantic-retrieval cross-user access.

**FAISS architecture:** PDFs are still extracted with PyMuPDF, split into chunks,
embedded, and stored in the existing FAISS index. Ownership is kept in the SQL
database, while retrieval applies the authenticated user's allowed document-ID
set before any chunk can become LLM context or a returned source.

### Supported resume bullets

- Built a multi-user FastAPI RAG document assistant with Google OAuth, expiring
  JWT API authentication, and persistent user profiles.
- Implemented user-isolated PDF upload, list, semantic retrieval, and deletion
  by enforcing document ownership in both SQL queries and FAISS result filtering.
- Added persisted, user-scoped chat history while retaining PyMuPDF ingestion,
  chunking, FAISS retrieval, and Gemini/OpenAI source-grounded answer support.
- Rendered assistant Markdown with DOMPurify-sanitized HTML on the existing
  frontend, preserving the JSON answer API contract.

## Docker

The included `Dockerfile` runs the FastAPI app with Uvicorn and exposes the service on the port provided by the deployment platform.

```bash
docker build -t ai-pdf-knowledge-assistant .
docker run --env-file .env -p 8000:8000 ai-pdf-knowledge-assistant
```

## Testing

```bash
python -m unittest discover
```

Tests cover text normalization, chunking, missing/tampered JWTs, owner-only
listing/deletion, cross-user query denial, empty-owner retrieval filtering,
Google callback rejection of unverified email, embedding dimension validation,
and reconstruction of a corrupt FAISS index from intact embeddings/metadata.
They use an isolated in-memory SQL database and mock external AI/OAuth calls.
They do not exercise Google's live consent flow or paid LLM providers.

Production startup rejects default/short JWT and OAuth state secrets and requires
different secrets of at least 32 characters. Generate random secrets, not phrases.
The Google callback requires `email_verified` to be the boolean `true`.

The recovery guarantee covers the FAISS index file when embeddings and metadata
are intact. It does not repair arbitrary metadata corruption. File-based writes
are not transactional across SQL, uploaded files, and the vector index; run one
worker and maintain backups. This testing is not a comprehensive security audit.

## Production Notes

- Use persistent disk storage for uploaded PDFs and FAISS index files.
- Keep API keys in the deployment platform's secret manager.
- For scanned PDFs, add OCR processing before text chunking.
- For larger production workloads, consider replacing file-based FAISS storage with a managed vector database.
- On small instances, use hash embeddings or hosted embeddings instead of local PyTorch models to avoid memory limits.

## License

This project is intended for educational, portfolio, and deployment demonstration use.
