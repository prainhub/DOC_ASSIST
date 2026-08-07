from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Document
from django.shortcuts import get_object_or_404
from pypdf import PdfReader
import os 


@login_required
def upload_document(request):

    if request.method == "POST":

        title = request.POST.get("title")
        uploaded_file = request.FILES.get("file")

        Document.objects.create(
            user=request.user,
            title=title,
            file=uploaded_file
        )

        return redirect("document_list")

    return render(request, "documents/upload.html")


@login_required
def document_list(request):

    documents = Document.objects.filter(
        user=request.user
    ).order_by("-uploaded_at")

    return render(request,
        "documents/document_list.html",
        {
            "documents": documents
        }
    )

@login_required
def delete_document(request, document_id):

    document = get_object_or_404(
        Document,
        id=document_id,
        user=request.user
    )

    if document.file:
        if os.path.isfile(document.file.path):
            os.remove(document.file.path)

    document.delete()

    return redirect("document_list")

@login_required
def extract_text(request, document_id):

    document = get_object_or_404(
        Document,
        id=document_id,
        user=request.user
    )

    reader = PdfReader(document.file.path)

    extracted_text = ""

    for page in reader.pages:
        text = page.extract_text()

        if text:
            extracted_text += text + "\n"

    document.extracted_text = extracted_text
    document.save()

    return render(
        request,
        "documents/extracted_text.html",
        {
            "document": document,
            "text": extracted_text
        }
    )