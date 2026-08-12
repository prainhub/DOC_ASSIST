"""Views and helper functions for the AI Chat app."""
from google import genai
import traceback

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from documents.models import Document
from .models import ChatMessage, ChatSession




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

        doc_text = (
            document.extracted_text[:12000]
            if document.extracted_text
            else ""
        )

        prompt = f"""
You are FITGPT, an AI Document Assistant.

Answer the user's question using the uploaded document.

DOCUMENT TITLE:
{document.title}

DOCUMENT CONTENT:
{doc_text}

{history_str}

USER QUESTION:
{question}

Instructions:

- Use the document as the primary source.
- Answer clearly and accurately.
- If the answer cannot be found in the document, say:
  "The answer to this question is not available in the uploaded document."
- Do not invent information.
- Use bullet points when useful.
"""

    # -----------------------------------------
    # General AI
    # -----------------------------------------

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

    # -----------------------------------------
    # Gemini
    # -----------------------------------------

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


# -------------------------------------------------------
# Views
# -------------------------------------------------------

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

        # ── Validate question ────────────────────────────
        if not question:
            error = "Please enter a question."

        # ── GENERAL AI ───────────────────────────────────
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

        # ── DOCUMENT AI ──────────────────────────────────
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
