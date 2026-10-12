import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.auth import create_access_token
from app.config import Settings
from app.database import Base, get_db
from app.db_models import User
from app.main import app
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import MockLLMClient
from app.services.pdf_service import PDFService
from app.services.rag_service import RAGService
from app.services.vector_store import VectorStore


class IngestionLifecycleTests(unittest.TestCase):
    def test_pdf_ingestion_owner_file_access_and_failure_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(_env_file=None, upload_dir=root/'uploads', index_dir=root/'index', embedding_provider='hash')
            engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
            Base.metadata.create_all(engine)
            sessions = sessionmaker(engine)
            with sessions() as db:
                owner = User(google_id='test-owner', email='owner@example.test', name='Owner')
                other = User(google_id='test-other', email='other@example.test', name='Other')
                db.add_all([owner, other]); db.commit()
                owner_headers = {'Authorization': 'Bearer '+create_access_token(owner)}
                other_headers = {'Authorization': 'Bearer '+create_access_token(other)}
            def database():
                with sessions() as db:
                    yield db
            store = VectorStore(root/'index', settings.embedding_dimension)
            service = RAGService(settings, PDFService(), EmbeddingService(settings), store, MockLLMClient())
            pdf = fitz.open(); page = pdf.new_page(); page.insert_text((72,72), 'Deployment requires passing tests and reviewer approval.')
            content = pdf.tobytes(); pdf.close()
            app.dependency_overrides[get_db] = database
            try:
                with patch('app.ingestion.SessionLocal', sessions), patch('app.ingestion.get_settings', return_value=settings), patch('app.ingestion.get_rag_service', return_value=service):
                    client = TestClient(app)
                    response = client.post('/api/ingestions', headers=owner_headers, files={'file': ('guide.pdf', content, 'application/pdf')})
                    self.assertEqual(response.status_code, 202)
                    jobs = client.get('/api/ingestions', headers=owner_headers).json()['jobs']
                    self.assertEqual(jobs[0]['status'], 'ready')
                    id = jobs[0]['document_id']
                    self.assertEqual(client.get(f'/api/documents/{id}/file', headers=owner_headers).content, content)
                    self.assertEqual(client.get(f'/api/documents/{id}/file', headers=other_headers).status_code, 404)
                    self.assertEqual(client.get('/api/ingestions', headers=other_headers).json()['jobs'], [])
                    response = client.post('/api/ingestions', headers=owner_headers, files={'file': ('broken.pdf', b'not a PDF', 'application/pdf')})
                    self.assertEqual(response.status_code, 202)
                    jobs = client.get('/api/ingestions', headers=owner_headers).json()['jobs']
                    self.assertIn('failed', [j['status'] for j in jobs])
                    self.assertEqual(list((root/'uploads'/'_jobs').glob('*')), [])
            finally:
                app.dependency_overrides.clear(); engine.dispose()
