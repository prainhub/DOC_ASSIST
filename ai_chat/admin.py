"""Admin configuration for ai_chat app."""
from django.contrib import admin
from .models import ChatMessage, ChatSession


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Admin view for chat sessions, useful for seeing user activity."""

    list_display = ("title", "user", "mode", "document", "created_at", "updated_at")
    list_filter = ("mode", "created_at")
    search_fields = ("title", "user__username")
    date_hierarchy = "created_at"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin view for individual chat messages."""

    list_display = ("session", "role", "content_preview", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "session__title", "session__user__username")
    date_hierarchy = "created_at"

    def content_preview(self, obj):
        """Show a short preview of the message content in the list view."""
        preview_length = 80
        if len(obj.content) > preview_length:
            return obj.content[:preview_length] + "..."
        return obj.content

    content_preview.short_description = "Content preview"