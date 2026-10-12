import unittest
from fastapi.testclient import TestClient
from app.main import app

class EvidenceWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_suggested_questions_retrieve_expected_sources(self):
        cases = [('What is the deployment process?', 'engineering-handbook'),
                 ('What are the API rate limits?', 'api-design'),
                 ('How should API keys be stored?', 'security-guide')]
        for question, expected in cases:
            with self.subTest(question=question):
                result = self.client.post('/api/demo/ask', json={'question': question}).json()
                self.assertEqual(result['sources'][0]['document_id'], expected)
                self.assertIn('[S1]', result['answer'])
                self.assertEqual(result['evidence_status'], 'retrieval_only')

    def test_unrelated_question_abstains(self):
        result = self.client.post('/api/demo/ask', json={'question': 'quantum banana telescope'}).json()
        self.assertEqual(result['sources'], [])
        self.assertEqual(result['evidence_status'], 'insufficient')

    def test_scope_does_not_leak_other_sample_documents(self):
        result = self.client.post('/api/demo/ask', json={'question': 'What is the deployment process?', 'document_id': 'security-guide'}).json()
        self.assertEqual(result['sources'], [])

    def test_upload_jobs_and_original_files_require_authentication(self):
        for path in ['/api/ingestions', '/api/documents/example/file']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post('/api/ingestions', files={'file': ('a.pdf', b'fake', 'application/pdf')}).status_code, 401)

    def test_question_size_is_bounded(self):
        self.assertEqual(self.client.post('/api/demo/ask', json={'question': 'x'*2001}).status_code, 422)
