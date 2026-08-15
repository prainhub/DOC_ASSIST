import os
import json
from .models import Document, DocumentChunk
from .chunking import chunk_text
from .embeddings import embed_chunks_for_document

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse 
from .models import Document, DocumentChunk
from .chunking import chunk_text
from django.views.decorators.http import require_POST
from django.conf import settings

def _extract_text_from_file(document):
    ext = document.file_extension

    try:
        document.processing_status = Document.STATUS_PROCESSING
        document.save(update_fields=['processing_status'])

        with document.file.open('rb') as file_obj:
            if ext == 'pdf':
                text = _extract_pdf(file_obj)

            elif ext == 'docx':
                text = _extract_docx(file_obj)

            elif ext == 'txt':
                text = _extract_txt(file_obj)

            else:
                document.processing_status = Document.STATUS_FAILED
                document.save(update_fields=['processing_status'])
                return False, f"Unsupported file type: .{ext}"

        if not text.strip():
            document.processing_status = Document.STATUS_FAILED
            document.save(update_fields=['processing_status'])
            return False, "Could not extract any text from this document."

        document.extracted_text = text
        document.processing_status = Document.STATUS_READY
        document.save(update_fields=['extracted_text', 'processing_status'])

        _create_chunks_for_document(document)

        return True, ""

    except Exception as e:
        document.processing_status = Document.STATUS_FAILED
        document.save(update_fields=['processing_status'])
        return False, str(e)


def _extract_pdf(file_obj):
    from pypdf import PdfReader
    reader = PdfReader(file_obj)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def _extract_docx(file_obj):
    from docx import Document as DocxDocument
    doc = DocxDocument(file_obj)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_txt(file_obj):
    content = file_obj.read()
    if isinstance(content, bytes):
        return content.decode('utf-8', errors='replace')
    return content


def _create_chunks_for_document(document):
    document.chunks.all().delete()

    pieces = chunk_text(document.extracted_text)

    chunk_objects = [
        DocumentChunk(document=document, chunk_index=index, content=piece)
        for index, piece in enumerate(pieces)
    ]

    if chunk_objects:
        DocumentChunk.objects.bulk_create(chunk_objects)
    try:
        embed_chunks_for_document(document)
    except Exception as exc:
        print("Embedding generation failed:", exc)


ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}


def _is_allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS


@login_required
def upload_document(request):
    if request.method == "POST":

        title = request.POST.get("title", "").strip()
        uploaded_file = request.FILES.get("file")

        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.POST.get('ajax') == '1'
        )

        if not uploaded_file:
            msg = "No file provided."
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'No file provided.'}, status=400)
            return render(request, "documents/upload.html", {"error": "No file provided."})

        if not _is_allowed_file(uploaded_file.name):
            msg = "Unsupported file type. Please upload PDF, DOCX, or TXT."
            if is_ajax:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            return render(request, "documents/upload.html", {"error": msg})

        if uploaded_file.size > settings.MAX_UPLOAD_SIZE_BYTES:
            msg = f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
            if is_ajax:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            return render(request, "documents/upload.html", {"error": msg})

        if not title:
            title = os.path.splitext(uploaded_file.name)[0]

        document = Document.objects.create(
            user=request.user,
            title=title,
            file=uploaded_file,
            processing_status=Document.STATUS_PENDING,
        )

        success, error_msg = _extract_text_from_file(document)

        if is_ajax:
            return JsonResponse({
                'success': True,
                'document_id': document.id,
                'document_title': document.title,
                'processing_status': document.processing_status,
                'extraction_ok': success,
                'extraction_error': error_msg if not success else '',
            })

        return redirect("document_list")

    return render(request, "documents/upload.html")


@login_required
def document_list(request):
    documents = Document.objects.filter(
        user=request.user
    ).order_by("-uploaded_at")

    return render(request, "documents/document_list.html", {"documents": documents})


@login_required
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, user=request.user)

    if document.file:
        if os.path.isfile(document.file.path):
            os.remove(document.file.path)

    document.delete()

    return redirect("document_list")


@login_required
def extract_text(request, document_id):
    document = get_object_or_404(Document, id=document_id, user=request.user)

    success, error_msg = _extract_text_from_file(document)

    return render(
        request,
        "documents/extracted_text.html",
        {
            "document": document,
            "text": document.extracted_text,
            "error": error_msg if not success else None,
        }
    )


@login_required
def chat_with_document(request, document_id):
    from ai_chat.models import ChatSession

    document = get_object_or_404(Document, id=document_id, user=request.user)

    if not document.extracted_text:
        _extract_text_from_file(document)

    session = ChatSession.objects.create(
        user=request.user,
        mode='document',
        document=document,
        title=f"Chat about {document.title[:50]}",
    )

    return redirect('chat_session', session_id=session.id)

@login_required
@require_POST
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, user=request.user)

    if document.file:
        document.file.delete(save=False)

    document.delete()

    return redirect("document_list")