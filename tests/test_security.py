import os
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['APP_ENV'] = 'development'

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.auth import create_access_token
from app.config import Settings
from app.database import Base, get_db
from app.db_models import User, Document, ChatHistory
from app.dependencies import get_rag_service, get_vector_store
from app.main import app
import app.main as main_module
from app.services.vector_store import VectorStore


class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        owner = User(google_id='owner', email='owner@example.test', name='Owner')
        other = User(google_id='other', email='other@example.test', name='Other')
        self.db.add_all([owner, other]); self.db.commit()
        self.db.add(Document(document_id='private', user_id=owner.id, filename='private.pdf', pages=1, chunks=1))
        self.db.add(ChatHistory(user_id=owner.id, document_id='private', question='secret', answer='secret'))
        self.db.commit()
        self.owner = {'Authorization': 'Bearer ' + create_access_token(owner)}
        self.other = {'Authorization': 'Bearer ' + create_access_token(other)}
        self.rag = Mock(); self.rag.ask = AsyncMock(return_value=('No documents', []))
        self.store = Mock()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_rag_service] = lambda: self.rag
        app.dependency_overrides[get_vector_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.db.close(); self.engine.dispose()

    def test_missing_and_tampered_tokens_are_rejected(self):
        for headers in ({}, {'Authorization': 'Bearer invalid.token.value'}):
            for method, path, kwargs in [('get', '/api/documents', {}), ('get', '/api/chat-history', {}),
                    ('delete', '/api/documents/private', {}),
                    ('post', '/api/ask', {'json': {'question': 'What is inside?'}}),
                    ('post', '/api/documents', {'files': {'file': ('test.pdf', b'%PDF-test', 'application/pdf')}})]:
                with self.subTest(path=path, headers=headers):
                    self.assertEqual(getattr(self.client, method)(path, headers=headers, **kwargs).status_code, 401)

    def test_other_user_cannot_list_read_or_delete_owned_data(self):
        self.assertEqual(self.client.get('/api/documents', headers=self.other).json()['documents'], [])
        self.assertEqual(self.client.get('/api/chat-history', headers=self.other).json()['conversations'], [])
        self.assertEqual(self.client.delete('/api/documents/private', headers=self.other).status_code, 404)
        self.assertEqual(self.client.post('/api/ask', headers=self.other, json={
            'question': 'What is inside?', 'document_id': 'private'}).status_code, 404)
        self.rag.ask.assert_not_called(); self.store.delete_document.assert_not_called()

    def test_unscoped_query_passes_only_owned_ids_to_retriever(self):
        for headers, ids in ((self.other, set()), (self.owner, {'private'})):
            self.assertEqual(self.client.post('/api/ask', headers=headers, json={'question': 'What is inside?'}).status_code, 200)
            self.assertEqual(self.rag.ask.call_args.kwargs['allowed_document_ids'], ids)

    def test_owner_can_list_and_delete(self):
        self.assertEqual(len(self.client.get('/api/documents', headers=self.owner).json()['documents']), 1)
        self.store.delete_document.return_value = True
        self.assertEqual(self.client.delete('/api/documents/private', headers=self.owner).status_code, 200)
        self.assertIsNone(self.db.get(Document, 'private'))

    def test_google_callback_rejects_missing_or_false_verified_email(self):
        google = Mock()
        for verified in (None, False, 'true'):
            profile = {'sub': 'new-google-user', 'email': 'new@example.test'}
            if verified is not None:
                profile['email_verified'] = verified
            google.authorize_access_token = AsyncMock(return_value={'userinfo': profile})
            with patch.object(main_module.settings, 'google_client_id', 'test-id'), \
                 patch.object(main_module.settings, 'google_client_secret', 'test-secret'), \
                 patch.object(main_module, 'oauth', Mock(google=google)):
                self.assertEqual(self.client.get('/api/auth/google/callback').status_code, 400)


class VectorIntegrityTests(unittest.TestCase):
    def test_retrieval_filters_owners_and_recovers_corrupt_faiss(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VectorStore(Path(directory), 2)
            first = store.add_document('a.pdf', [(1, 'owner text')], np.array([[1, 0]], dtype='float32'))
            second = store.add_document('b.pdf', [(2, 'other text')], np.array([[0, 1]], dtype='float32'))
            query = np.array([[0, 1]], dtype='float32')
            self.assertEqual(store.search(query, 5, allowed_document_ids=set()), [])
            results = store.search(query, 5, allowed_document_ids={first.document_id})
            self.assertEqual([r.metadata.document_id for r in results], [first.document_id])
            store.index_path.write_bytes(b'corrupt')
            recovered = VectorStore(Path(directory), 2)
            self.assertEqual(recovered.index.ntotal, 2)
            self.assertEqual(recovered.search(query, 1)[0].metadata.document_id, second.document_id)

    def test_wrong_dimension_does_not_mutate_index(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VectorStore(Path(directory), 2)
            with self.assertRaises(ValueError):
                store.add_document('bad.pdf', [(1, 'text')], np.ones((1, 3), dtype='float32'))
            self.assertEqual(store.index.ntotal, 0)
            self.assertEqual(store.documents, {})

    def test_production_rejects_default_secrets(self):
        with self.assertRaises(ValueError):
            Settings(_env_file=None, app_env='production', jwt_secret_key='change-this-in-production')


if __name__ == '__main__':
    unittest.main()
