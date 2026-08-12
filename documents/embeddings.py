from django.conf import settings
from google import genai
from google.genai import types

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
BATCH_SIZE = 20


def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def embed_texts(texts, task_type):
    if not texts:
        return []

    client = _get_client()
    config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )

    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
            config=config,
        )
        for item in response.embeddings:
            vectors.append(list(item.values))

    return vectors


def embed_query_text(text):
    vectors = embed_texts([text], task_type="RETRIEVAL_QUERY")
    return vectors[0] if vectors else None


def embed_chunks_for_document(document):
    chunks = list(document.chunks.filter(embedding__isnull=True))
    if not chunks:
        return

    texts = [chunk.content for chunk in chunks]
    vectors = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector
        chunk.save(update_fields=["embedding"])