from django.contrib import admin

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "processing_status", "uploaded_at")
    list_filter = ("processing_status",)
    search_fields = ("title", "user__username")


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "content_preview", "created_at")
    list_filter = ("document",)
    search_fields = ("content",)

    def content_preview(self, obj):
        preview_length = 80
        if len(obj.content) > preview_length:
            return obj.content[:preview_length] + "..."
        return obj.content

    content_preview.short_description = "Content preview"