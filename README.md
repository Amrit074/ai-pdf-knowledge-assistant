# PDF Knowledge Assistant

A full-stack Retrieval-Augmented Generation app for uploading PDFs and asking natural-language questions about their content.

## Features

- Plain HTML, CSS, and JavaScript frontend served by FastAPI
- Async FastAPI REST API
- PDF text extraction with PyMuPDF
- Text cleaning and overlapping chunking
- Sentence Transformers embeddings using `sentence-transformers/all-MiniLM-L6-v2`
- FAISS semantic vector search
- Gemini, OpenAI, or mock LLM provider
- Document upload, list, question answering, and delete APIs
- Persistent local storage for uploads, FAISS index, metadata, and embeddings
- Docker and Render deployment support

## Project Structure

```text
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── logging_config.py
│   ├── models.py
│   ├── services/
│   │   ├── embedding_service.py
│   │   ├── llm_service.py
│   │   ├── pdf_service.py
│   │   ├── rag_service.py
│   │   └── vector_store.py
│   └── utils/
│       └── text.py
├── static/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── Dockerfile
├── Procfile
├── render.yaml
├── requirements.txt
└── .env.example
```

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

The first upload may take a little longer because the embedding model downloads on first use.

## Environment Variables

Copy `.env.example` to `.env`.

Use mock mode for retrieval-only demos:

```env
LLM_PROVIDER=mock
```

Use Gemini:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Use OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

## API Endpoints

### Health

```http
GET /api/health
```

### Upload PDF

```http
POST /api/documents
Content-Type: multipart/form-data
```

Form field:

- `file`: PDF file

### List Documents

```http
GET /api/documents
```

### Ask Question

```http
POST /api/ask
Content-Type: application/json
```

```json
{
  "question": "What is this document about?",
  "document_id": null,
  "top_k": 5
}
```

### Delete Document

```http
DELETE /api/documents/{document_id}
```

## Docker

```bash
docker build -t pdf-knowledge-assistant .
docker run --env-file .env -p 8000:8000 -v "%cd%/storage:/app/storage" pdf-knowledge-assistant
```

Open `http://localhost:8000`.

## Render Deployment

1. Push this project to GitHub.
2. In Render, create a new Blueprint or Web Service from the repo.
3. If using `render.yaml`, Render will use Docker and mount `/app/storage` as persistent disk.
4. Set `LLM_PROVIDER` to `gemini` or `openai`.
5. Add the matching secret key, `GEMINI_API_KEY` or `OPENAI_API_KEY`.
6. Deploy.

For free or small instances, model download and cold start can be slow. A persistent disk is recommended so uploads and the FAISS index survive restarts.

## Notes for Aiven or Similar Cloud Platforms

This app stores vector data in local FAISS files. Aiven is commonly used for managed PostgreSQL, Kafka, Redis, and other backing services. You can deploy the FastAPI service on a container host and keep FAISS on persistent disk, or later replace `VectorStore` with a managed vector database such as PostgreSQL plus pgvector if your platform provides it.
