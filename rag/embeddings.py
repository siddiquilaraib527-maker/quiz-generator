from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


MODEL_NAME = "all-MiniLM-L6-v2"


def create_embeddings(chunks):
    """
    Convert text chunks into vector embeddings.
    """
    if not chunks:
        return np.array([])

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embeddings


def create_faiss_index(embeddings):
    """
    Create a FAISS vector index from embeddings.
    """
    if len(embeddings) == 0:
        raise ValueError("No embeddings available.")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings.astype("float32"))

    return index


if __name__ == "__main__":
    sample_chunks = [
        "Computer networks allow devices to communicate.",
        "A router forwards packets between networks."
    ]

    embeddings = create_embeddings(sample_chunks)
    index = create_faiss_index(embeddings)

    print("Embeddings shape:", embeddings.shape)
    print("FAISS vectors:", index.ntotal)