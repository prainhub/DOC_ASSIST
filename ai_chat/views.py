from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings

from documents.models import Document
from google import genai


@login_required
def chat_home(request):

    documents = Document.objects.filter(user=request.user)

    answer = None
    error = None

    if request.method == "POST":

        document_id = request.POST.get("document")
        question = request.POST.get("question")

        document = get_object_or_404(
            Document,
            id=document_id,
            user=request.user
        )

        if not document.extracted_text:
            error = "This document has no extracted text."

        elif not question:
            error = "Please enter a question."

        else:

            prompt = f"""
You are an AI Document Assistant.

Answer the user's question using the document content provided below.

DOCUMENT CONTENT:
{document.extracted_text}

USER QUESTION:
{question}

Instructions:
- Answer clearly and accurately.
- Use the document as your primary source.
- If the answer cannot be found in the document, say that it is not available in the document.
"""

            try:

                client = genai.Client(
                    api_key=settings.GEMINI_API_KEY
                )

                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt
                )

                answer = response.text

            except Exception as e:

                error = f"AI error: {str(e)}"

    return render(
        request,
        "ai_chat/chat.html",
        {
            "documents": documents,
            "answer": answer,
            "error": error,
        }
    )