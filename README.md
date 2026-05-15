# AI PDF Knowledge Assistant

AI PDF Knowledge Assistant is a full-stack Retrieval-Augmented Generation application that allows users to upload PDF documents and ask natural-language questions based on the uploaded content.

The system extracts text from PDFs, converts the content into semantic embeddings, stores those embeddings in a FAISS vector index, retrieves the most relevant document chunks for a user query, and generates a contextual answer using an LLM provider such as Gemini or OpenAI.

## Key Features

- PDF upload and document management through a simple web interface
- FastAPI backend with clean, modular service architecture
- Text extraction from PDFs using PyMuPDF
- Text cleaning, chunking, and overlap-based document splitting
- Sentence Transformer embeddings with `all-MiniLM-L6-v2`
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
| Embeddings | Sentence Transformers |
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
Sentence Transformer creates embeddings
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
| `EMBEDDING_MODEL` | Sentence Transformer model name |
| `CHUNK_SIZE` | Maximum text chunk size |
| `CHUNK_OVERLAP` | Overlap between adjacent chunks |
| `TOP_K` | Default number of retrieved chunks |
| `LLM_PROVIDER` | `gemini`, `openai`, or `mock` |
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Gemini model name |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI model name |

### Gemini Configuration

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
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

## Docker

The included `Dockerfile` runs the FastAPI app with Uvicorn and exposes the service on the port provided by the deployment platform.

```bash
docker build -t ai-pdf-knowledge-assistant .
docker run --env-file .env -p 8000:8000 ai-pdf-knowledge-assistant
```

## Production Notes

- Use persistent disk storage for uploaded PDFs and FAISS index files.
- Keep API keys in the deployment platform's secret manager.
- For scanned PDFs, add OCR processing before text chunking.
- For larger production workloads, consider replacing file-based FAISS storage with a managed vector database.
- Cold starts can take longer on small instances because the embedding model loads into memory.

## License

This project is intended for educational, portfolio, and deployment demonstration use.
