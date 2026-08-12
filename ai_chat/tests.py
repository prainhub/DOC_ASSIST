"""Tests for the ai_chat app."""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from documents.models import Document
from .models import ChatMessage, ChatSession


def _fake_gemini_response(text):
    mock_response = MagicMock()
    mock_response.text = text
    return mock_response


class ChatAccessTests(TestCase):
    """Tests that chat sessions are properly scoped to their owner."""

    def setUp(self):
        self.user_a = User.objects.create_user(username="alice", password="testpass123")
        self.user_b = User.objects.create_user(username="bob", password="testpass123")
        self.session = ChatSession.objects.create(
            user=self.user_a,
            mode="general",
            title="Test chat",
        )
        ChatMessage.objects.create(session=self.session, role="user", content="hi")

    def test_chat_home_requires_login(self):
        response = self.client.get(reverse("chat_home"))
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_view_other_users_session(self):
        self.client.login(username="bob", password="testpass123")
        response = self.client.get(reverse("chat_session", args=[self.session.id]))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_own_session(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("chat_session", args=[self.session.id]))
        self.assertEqual(response.status_code, 200)

    def test_delete_session_rejects_get(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("delete_session", args=[self.session.id]))
        self.assertEqual(response.status_code, 405)

    def test_owner_can_delete_own_session(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(reverse("delete_session", args=[self.session.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ChatSession.objects.filter(id=self.session.id).exists())


class GeneralAiChatTests(TestCase):
    """Tests for General AI mode."""

    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="testpass123")
        self.client.login(username="carol", password="testpass123")

    def test_empty_question_shows_error(self):
        response = self.client.post(reverse("chat_home"), {"mode": "general", "question": ""})
        self.assertContains(response, "Please enter a question")

    @patch("ai_chat.views.genai.Client")
    def test_general_question_creates_session_and_messages(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_gemini_response("Hi there!")
        mock_client_cls.return_value = mock_client

        response = self.client.post(
            reverse("chat_home"),
            {"mode": "general", "question": "hello"},
        )
        self.assertEqual(response.status_code, 302)

        session = ChatSession.objects.filter(user=self.user).latest("created_at")
        self.assertEqual(session.mode, "general")

        messages = list(session.messages.all())
        self.assertEqual(messages[0].content, "hello")
        self.assertEqual(messages[1].content, "Hi there!")

    @patch("ai_chat.views.genai.Client")
    def test_gemini_failure_shows_friendly_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("RESOURCE_EXHAUSTED 429")
        mock_client_cls.return_value = mock_client

        response = self.client.post(
            reverse("chat_home"),
            {"mode": "general", "question": "hello"},
        )
        self.assertEqual(response.status_code, 302)

        session = ChatSession.objects.filter(user=self.user).latest("created_at")
        last_message = session.messages.last()
        self.assertIn("temporarily unavailable", last_message.content)


class DocumentAiChatTests(TestCase):
    """Tests for Document AI mode."""

    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="testpass123")
        self.client.login(username="dave", password="testpass123")
        self.document = Document.objects.create(
            user=self.user,
            title="Notes",
            extracted_text="The sky is blue.",
            processing_status=Document.STATUS_READY,
        )

    def test_document_mode_without_document_shows_error(self):
        response = self.client.post(
            reverse("chat_home"),
            {"mode": "document", "question": "what color is the sky?"},
        )
        self.assertContains(response, "select or upload a document")

    @patch("ai_chat.views.genai.Client")
    def test_document_question_uses_document_context(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_gemini_response("The sky is blue.")
        mock_client_cls.return_value = mock_client

        response = self.client.post(
            reverse("chat_home"),
            {
                "mode": "document",
                "document": self.document.id,
                "question": "what color is the sky?",
            },
        )
        self.assertEqual(response.status_code, 302)

        session = ChatSession.objects.filter(user=self.user).latest("created_at")
        self.assertEqual(session.document_id, self.document.id)