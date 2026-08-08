from django.db import models
from django.contrib.auth.models import User
from documents.models import Document


class ChatSession(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )

    title = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Chat {self.id}"


class ChatMessage(models.Model):

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"