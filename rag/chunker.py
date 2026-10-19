def split_text(text: str, chunk_size: int = 800, overlap: int = 100):
    """
    Split text into overlapping chunks for RAG.
    """

    if not text.strip():
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


if __name__ == "__main__":
    sample = "This is a sample document. " * 100
    chunks = split_text(sample)

    print(f"Created {len(chunks)} chunks.")
    print("\nFirst chunk:\n")
    print(chunks[0])