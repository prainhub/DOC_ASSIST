DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP):
    if not text:
        return []

    cleaned = text.strip()
    if not cleaned:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size.")

    chunks = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = start + chunk_size
        piece = cleaned[start:end].strip()

        if piece:
            chunks.append(piece)

        if end >= text_length:
            break

        start = end - overlap

    return chunks