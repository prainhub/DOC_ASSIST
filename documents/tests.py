"""Tests for the documents app."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .chunking import chunk_text
from .models import Document
from .retrieval import cosine_similarity


class ChunkTextTests(TestCase):
    """Tests for the chunk_text helper."""

    def test_empty_text_returns_no_chunks(self):
        self.assertEqual(chunk_text(""), [])

    def test_short_text_returns_single_chunk(self):
        chunks = chunk_text("hello world", chunk_size=1000, overlap=150)
        self.assertEqual(chunks, ["hello world"])

    def test_long_text_is_split_with_overlap(self):
        text = "".join(chr(65 + (i % 26)) for i in range(2500))
        chunks = chunk_text(text, chunk_size=1000, overlap=150)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0][-150:], chunks[1][:150])

    def test_invalid_chunk_size_raises(self):
        with self.assertRaises(ValueError):
            chunk_text("hello", chunk_size=0)

    def test_overlap_too_large_raises(self):
        with self.assertRaises(ValueError):
            chunk_text("hello", chunk_size=10, overlap=10)


class CosineSimilarityTests(TestCase):
    """Tests for the cosine_similarity helper."""

    def test_identical_vectors_have_similarity_one(self):
        vec = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(vec, vec), 1.0, places=5)

    def test_orthogonal_vectors_have_similarity_zero(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, places=5)

    def test_empty_vector_returns_zero(self):
        self.assertEqual(cosine_similarity([], [1.0, 2.0]), 0.0)


class DocumentAccessTests(TestCase):
    """Tests that documents are properly scoped to their owner."""

    def setUp(self):
        self.user_a = User.objects.create_user(username="alice", password="testpass123")
        self.user_b = User.objects.create_user(username="bob", password="testpass123")
        self.document = Document.objects.create(
            user=self.user_a,
            title="Alice's Resume",
            extracted_text="Alice worked at Acme Corp.",
            processing_status=Document.STATUS_READY,
        )

    def test_upload_requires_login(self):
        response = self.client.get(reverse("upload_document"))
        self.assertEqual(response.status_code, 302)

    def test_document_list_requires_login(self):
        response = self.client.get(reverse("document_list"))
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_delete_other_users_document(self):
        self.client.login(username="bob", password="testpass123")
        response = self.client.post(reverse("delete_document", args=[self.document.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(id=self.document.id).exists())

    def test_owner_can_delete_own_document(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(reverse("delete_document", args=[self.document.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(id=self.document.id).exists())

    def test_delete_document_rejects_get(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("delete_document", args=[self.document.id]))
        self.assertEqual(response.status_code, 405)

    def test_document_list_only_shows_own_documents(self):
        self.client.login(username="bob", password="testpass123")
        response = self.client.get(reverse("document_list"))
        self.assertNotContains(response, "Alice's Resume")


class UploadValidationTests(TestCase):
    """Tests for upload validation and chunk creation on upload."""

    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="testpass123")
        self.client.login(username="carol", password="testpass123")

    def test_rejects_disallowed_file_type(self):
        bad_file = SimpleUploadedFile("virus.exe", b"not a real document")
        response = self.client.post(
            reverse("upload_document"),
            {"file": bad_file, "ajax": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertFalse(data["success"])

    def test_rejects_oversized_file(self):
        big_content = b"a" * (settings.MAX_UPLOAD_SIZE_BYTES + 1)
        big_file = SimpleUploadedFile("big.txt", big_content)
        response = self.client.post(
            reverse("upload_document"),
            {"file": big_file, "ajax": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("too large", data["error"].lower())

    @patch("documents.views.embed_chunks_for_document")
    def test_accepts_valid_txt_file_and_creates_chunks(self, mock_embed):
        content = ("This is a test document. " * 100).encode("utf-8")
        good_file = SimpleUploadedFile("notes.txt", content)
        response = self.client.post(
            reverse("upload_document"),
            {"file": good_file, "ajax": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["extraction_ok"])

        document = Document.objects.get(id=data["document_id"])
        self.assertEqual(document.processing_status, Document.STATUS_READY)
        self.assertTrue(document.chunks.exists())
        mock_embed.assert_called_once()

    def test_empty_file_field_shows_error(self):
        response = self.client.post(
            reverse("upload_document"),
            {"ajax": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertFalse(data["success"])