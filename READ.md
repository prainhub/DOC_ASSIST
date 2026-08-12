# DOCASSIST

DOCASSIST is a Django-based AI assistant that supports both general conversation and
document-grounded conversation. Users can upload a PDF, DOCX, or TXT file directly
inside the chat. The system extracts the text, splits it into overlapping chunks,
generates a vector embedding for each chunk, retrieves only the chunks relevant to a
given question, and passes that retrieved context to Gemini to produce a grounded
answer — a full Retrieval-Augmented Generation (RAG) pipeline, not just "paste the
whole document into the prompt."

## Tech stack

- **Backend:** Django 5.2
- **AI:** Google Gemini API via the `google-genai` SDK
  - Chat: `gemini-3.5-flash`
  - Embeddings: `gemini-embedding-001` (768 dimensions)
- **Database:** SQLite (Django ORM)
- **Frontend:** Django templates, Bootstrap 5, vanilla JavaScript
- **File parsing:** `pypdf` (PDF), `python-docx` (DOCX)

## Architecture

### Apps

| App | Responsibility |
|---|---|
| `accounts` | Registration, login, logout |
| `documents` | Upload, text extraction, chunking, embeddings, retrieval |
| `ai_chat` | Chat sessions, messages, Gemini prompt construction |
| `core` | Landing page |

### Two AI modes

**General AI** — a plain question goes straight to Gemini with conversation history,
no document involved.