import math

from .embeddings import embed_query_text


def cosine_similarity(vec_a, vec_b):
    if not vec_a or not vec_b:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def get_relevant_chunks(document, question, top_k=5):
    chunks = list(document.chunks.exclude(embedding__isnull=True))
    if not chunks:
        return []

    query_vector = embed_query_text(question)
    if not query_vector:
        return []

    scored = [
        (cosine_similarity(query_vector, chunk.embedding), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [chunk for _, chunk in scored[:top_k]]