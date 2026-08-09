"""Models for AI Chat sessions and messages."""
from django.conf import settings
from django.db import models
from documents.models import Document


class ChatSession(models.Model):
    """Represents a chat conversation session between a user and the AI."""

    MODE_CHOICES = [
        ("general", "General AI"),
        ("document", "Document AI"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions"
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default="general",
    )

    title = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        """Meta options for ChatSession model."""
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Chat {self.id}"


class ChatMessage(models.Model):
    """Represents an individual message within a ChatSession."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        """Meta options for ChatMessage model."""
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
