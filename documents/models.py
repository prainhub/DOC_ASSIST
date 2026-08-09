from django.db import models
from django.contrib.auth.models import User


class Document(models.Model):

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(max_length=255)

    file = models.FileField(upload_to="documents/")

    extracted_text = models.TextField(blank=True)

    processing_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def file_extension(self):
        import os
        _, ext = os.path.splitext(self.file.name)
        return ext.lower().lstrip('.')

    @property
    def is_ready(self):
        return self.processing_status == self.STATUS_READY