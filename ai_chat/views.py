from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings

from documents.models import Document
from .models import ChatSession, ChatMessage
from google import genai


def _build_sidebar_sessions(user):
    return ChatSession.objects.filter(user=user).select_related("document")


def _ask_gemini(document, question):
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

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt
    )

    return response.text


@login_required
def chat_home(request):
    """New chat screen: no session selected yet."""

    documents = Document.objects.filter(user=request.user)
    sessions = _build_sidebar_sessions(request.user)

    error = None

    if request.method == "POST":

        document_id = request.POST.get("document")
        question = request.POST.get("question")

        if not documents.exists():
            error = "You don't have any documents yet. Upload one first."

        elif not document_id:
            error = "Please select a document."

        elif not question:
            error = "Please enter a question."

        else:

            document = Document.objects.filter(id=document_id, user=request.user).first()

            if not document:
                error = "That document could not be found. Please select it again."

            elif not document.extracted_text:
                error = "This document has no extracted text. Extract it first from My Documents."

            else:

                session = ChatSession.objects.create(
                    user=request.user,
                    document=document,
                    title=question[:60],
                )

                ChatMessage.objects.create(session=session, role="user", content=question)

                try:
                    answer = _ask_gemini(document, question)
                except Exception as e:
                    answer = f"AI error: {str(e)}"

                ChatMessage.objects.create(session=session, role="assistant", content=answer)

                return redirect("chat_session", session_id=session.id)

    return render(
        request,
        "ai_chat/chat.html",
        {
            "documents": documents,
            "sessions": sessions,
            "active_session": None,
            "messages": [],
            "error": error,
        }
    )


@login_required
def chat_session(request, session_id):
    """Continue an existing chat session."""

    active_session = get_object_or_404(ChatSession, id=session_id, user=request.user)

    documents = Document.objects.filter(user=request.user)
    sessions = _build_sidebar_sessions(request.user)

    error = None

    if request.method == "POST":

        question = request.POST.get("question")
        document = active_session.document

        if not document or not document.extracted_text:
            error = "This session has no linked document text. Extract text first."
        elif not question:
            error = "Please enter a question."
        else:
            ChatMessage.objects.create(session=active_session, role="user", content=question)

            try:
                answer = _ask_gemini(document, question)
            except Exception as e:
                answer = f"AI error: {str(e)}"

            ChatMessage.objects.create(session=active_session, role="assistant", content=answer)

            active_session.save()  # bump updated_at

            return redirect("chat_session", session_id=active_session.id)

    return render(
        request,
        "ai_chat/chat.html",
        {
            "documents": documents,
            "sessions": sessions,
            "active_session": active_session,
            "messages": active_session.messages.all(),
            "error": error,
        }
    )


@login_required
def delete_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    session.delete()
    return redirect("chat_home")