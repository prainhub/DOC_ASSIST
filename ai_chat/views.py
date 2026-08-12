"""Views and helper functions for the AI Chat app."""
from google import genai
import traceback

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from documents.models import Document
from .models import ChatMessage, ChatSession
from documents.models import Document, DocumentChunk
from documents.retrieval import get_relevant_chunks
from  .models import ChatMessage, ChatSession




# -------------------------------------------------------
# Helpers
# -------------------------------------------------------

def _build_sidebar_sessions(user):
    return ChatSession.objects.filter(
        user=user
    ).select_related("document")[:25]


def _ask_gemini(question, document=None, history=None):
    """
    Send a question to Gemini.

    If document is provided:
        Document AI mode.

    If document is None:
        General AI mode.
    """

    # -----------------------------------------
    # Conversation history
    # -----------------------------------------

    history_str = ""

    if history:
        history_str = "\n\nPREVIOUS CONVERSATION:\n"

        for msg in history:
            role_label = "User" if msg.role == "user" else "FITGPT"

            history_str += (
                f"{role_label}: {msg.content}\n"
            )

        history_str += (
            "\nContinue the conversation naturally."
        )

    # -----------------------------------------
    # Document AI
    # -----------------------------------------
    if document:

        relevant_chunks = get_relevant_chunks(document, question)

        if relevant_chunks:
            doc_text = "\n\n---\n\n".join(chunk.content for chunk in relevant_chunks)
        else:
            doc_text = (
                document.extracted_text[:12000]
                if document.extracted_text
                else ""
            )

        prompt = f"""
You are DOCASSIST, an AI Document Assistant.

Answer the user's question using the uploaded document.

DOCUMENT TITLE:
{document.title}

DOCUMENT CONTENT:
{doc_text}

{history_str}

USER QUESTION:
{question}

Instructions:

- Base your answer on the document's content.
- You may reason, summarize, compare, and give advice or suggestions using what's in the document — this is expected when the user asks things like "how can I improve this" or "what's missing."
- Only say the information is unavailable if the user asks about a specific fact or detail the document genuinely does not contain. In that case say:
  "I couldn't find that specific information in the uploaded document."
- Do not invent facts, numbers, or details that are not in the document.
- Use bullet points when useful.
"""

    else:

        prompt = f"""
You are FITGPT, a helpful general-purpose AI assistant.

{history_str}

USER QUESTION:
{question}

Instructions:

- Be helpful and conversational.
- Explain things clearly.
- Give accurate answers.
- Use bullet points when useful.
- If you are unsure, say so.
"""
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY
    )

    print("\n==============================")
    print("SENDING REQUEST TO GEMINI")
    print("==============================")
    print("Question:", question)
    print("Model: gemini-3.5-flash")

    try:

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        print("==============================")
        print("GEMINI RESPONSE RECEIVED")
        print("==============================")

        if response and response.text:
            return response.text

        return "Gemini returned an empty response."

    except Exception as exc:

        print("\n==============================")
        print("GEMINI ERROR")
        print("==============================")

        print(str(exc))

        traceback.print_exc()

        print("==============================\n")

        raise


def _format_ai_error(exc):
    """
    Convert a raw Gemini API exception into a short, user-friendly string
    that can be stored as the assistant's reply.
    """
    msg = str(exc)

    if '429' in msg or 'RESOURCE_EXHAUSTED' in msg:
        return (
            "⚠️ FITGPT is temporarily unavailable due to high demand. "
            "Please wait a moment and try again. "
            "(Free-tier API quota exceeded — this resets automatically.)"
        )

    if '401' in msg or 'API_KEY' in msg.upper() or 'INVALID_API_KEY' in msg:
        return (
            "⚠️ FITGPT could not connect: invalid or missing API key. "
            "Please check the GEMINI_API_KEY in your .env file."
        )

    if '503' in msg or 'UNAVAILABLE' in msg:
        return (
            "⚠️ The AI service is temporarily unavailable. "
            "Please try again in a few seconds."
        )

    if '400' in msg or 'INVALID_ARGUMENT' in msg:
        return (
            "⚠️ FITGPT could not process this request. "
            "The question or document content may be too long. Please try a shorter message."
        )

    # Generic fallback — do NOT expose internal stack traces to the user
    return (
        "⚠️ FITGPT encountered an unexpected error. "
        "Please try again. If the problem persists, check the server logs."
    )

@login_required
def chat_home(request):
    """
    New / home chat screen. No active session.
    """
    documents = Document.objects.filter(
        user=request.user
    ).order_by('-uploaded_at')

    error = None

    if request.method == "POST":

        mode = request.POST.get("mode", "general")
        document_id = request.POST.get("document")
        question = request.POST.get("question", "").strip()

        
        if not question:
            error = "Please enter a question."
 
        elif mode == "general":

            session = ChatSession.objects.create(
                user=request.user,
                mode="general",
                document=None,
                title=question[:60],
            )

            ChatMessage.objects.create(
                session=session,
                role="user",
                content=question
            )

            try:
                answer = _ask_gemini(question=question)
            except Exception as e:  # pylint: disable=broad-exception-caught
                answer = _format_ai_error(e)

            ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=answer
            )

            return redirect("chat_session", session_id=session.id)

        
        elif mode == "document":

            if not document_id:
                error = "Please select or upload a document."

            else:
                document = Document.objects.filter(
                    id=document_id,
                    user=request.user
                ).first()

                if not document:
                    error = "That document could not be found."

                elif not document.extracted_text:
                    error = (
                        "This document has no extracted text yet. "
                        "Please wait for processing to complete or try re-uploading."
                    )

                else:
                    session = ChatSession.objects.create(
                        user=request.user,
                        mode="document",
                        document=document,
                        title=question[:60],
                    )

                    ChatMessage.objects.create(
                        session=session,
                        role="user",
                        content=question
                    )

                    try:
                        answer = _ask_gemini(
                            question=question,
                            document=document
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        answer = _format_ai_error(e)

                    ChatMessage.objects.create(
                        session=session,
                        role="assistant",
                        content=answer
                    )

                    return redirect("chat_session", session_id=session.id)

        else:
            error = "Invalid chat mode."

    return render(
        request,
        "ai_chat/chat.html",
        {
            "documents": documents,
            "active_session": None,
            "messages": [],
            "error": error,
        }
    )


@login_required
def chat_session(request, session_id):
    """
    Continue an existing conversation.
    """
    active_session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )

    documents = Document.objects.filter(
        user=request.user
    ).order_by('-uploaded_at')

    error = None

    if request.method == "POST":

        question = request.POST.get("question", "").strip()
        document = active_session.document

        if not question:
            error = "Please enter a question."

        elif active_session.mode == "document":

            if not document:
                error = "This chat session has no associated document."

            elif not document.extracted_text:
                error = "This document has no extracted text. Please re-upload the document."

            else:
                # Get history BEFORE adding new message
                history = list(active_session.messages.all())

                ChatMessage.objects.create(
                    session=active_session,
                    role="user",
                    content=question
                )

                try:
                    answer = _ask_gemini(
                        question=question,
                        document=document,
                        history=history
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    answer = _format_ai_error(e)

                ChatMessage.objects.create(
                    session=active_session,
                    role="assistant",
                    content=answer
                )

                active_session.save()  # update updated_at

                return redirect("chat_session", session_id=active_session.id)

        else:
            # GENERAL AI

            history = list(active_session.messages.all())

            ChatMessage.objects.create(
                session=active_session,
                role="user",
                content=question
            )

            try:
                answer = _ask_gemini(
                    question=question,
                    history=history
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                answer = _format_ai_error(e)

            ChatMessage.objects.create(
                session=active_session,
                role="assistant",
                content=answer
            )

            active_session.save()

            return redirect("chat_session", session_id=active_session.id)

    return render(
        request,
        "ai_chat/chat.html",
        {
            "documents": documents,
            "active_session": active_session,
            "messages": active_session.messages.all(),
            "error": error,
        }
    )


@login_required
def delete_session(request, session_id):

    session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )

    session.delete()

    return redirect("chat_home")


@login_required
@require_POST
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, user=request.user)

@login_required
@require_POST
def delete_session(request, session_id):
    session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )

    session.delete()

    return redirect("chat_home")