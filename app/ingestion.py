"""Small, single-worker ingestion pipeline with persistent, owner-scoped status."""
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.db_models import Document, IngestionJob, User
from app.dependencies import get_rag_service

router = APIRouter()

async def process_job(job_id: str, path: Path):
    with SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        document = None
        def progress(state):
            job.status = state
            db.commit()
        try:
            service = get_rag_service()
            with path.open('rb') as stream:
                document = await service.upload_pdf(UploadFile(filename=job.filename, file=stream), progress=progress)
            db.add(Document(document_id=document.document_id, user_id=job.user_id, filename=document.filename, pages=document.pages, chunks=document.chunks))
            job.document_id = document.document_id
            job.status = 'ready'
            db.commit()
        except Exception:
            db.rollback()
            if document:
                service.vector_store.delete_document(document.document_id, service.upload_dir)
            job.status = 'failed'
            job.error = 'Unable to process this PDF. Check that it contains selectable text and try again.'
            db.commit()
        finally:
            path.unlink(missing_ok=True)

@router.post('/api/ingestions', status_code=202)
async def submit_job(background: BackgroundTasks, file: UploadFile = File(...),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, 'Choose a PDF file.')
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content or len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Upload a nonempty PDF no larger than {settings.max_upload_mb} MB.')
    active = db.scalar(select(IngestionJob.id).where(IngestionJob.user_id == user.id, IngestionJob.status.in_(['queued','extracting','embedding','indexing'])))
    if active:
        raise HTTPException(409, 'Wait for your current upload to finish.')
    job = IngestionJob(id=uuid4().hex, user_id=user.id, filename=Path(file.filename.replace('\\','/')).name[:250], status='queued')
    directory = settings.resolve_path(settings.upload_dir) / '_jobs'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job.id + '.pdf')
    path.write_bytes(content)
    try:
        db.add(job); db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    background.add_task(process_job, job.id, path)
    return {'id': job.id, 'status': job.status, 'filename': job.filename}

@router.get('/api/ingestions')
async def jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionJob).where(IngestionJob.user_id == user.id).order_by(IngestionJob.created_at.desc()).limit(20)).all()
    return {'jobs': [{'id': j.id, 'filename': j.filename, 'status': j.status, 'error': j.error, 'document_id': j.document_id} for j in rows]}

@router.get('/api/documents/{document_id}/file')
async def source_file(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.scalar(select(Document).where(Document.document_id == document_id, Document.user_id == user.id))
    if doc is None: raise HTTPException(404, 'Document not found.')
    root = get_settings().resolve_path(get_settings().upload_dir).resolve()
    path = (root / doc.document_id / Path(doc.filename).name).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404, 'Original PDF is unavailable.')
    return FileResponse(path, media_type='application/pdf', filename=Path(doc.filename).name, content_disposition_type='inline')
