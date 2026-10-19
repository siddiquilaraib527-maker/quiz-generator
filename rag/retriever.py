from pathlib import Path
import json
import faiss
from sentence_transformers import SentenceTransformer


VECTOR_DIR = Path(__file__).parent / "vectorstore"
MODEL_NAME = "all-MiniLM-L6-v2"


class Retriever:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)

        index_path = VECTOR_DIR / "index.faiss"
        chunks_path = VECTOR_DIR / "chunks.json"

        if not index_path.exists():
            raise FileNotFoundError("FAISS index not found.")

        if not chunks_path.exists():
            raise FileNotFoundError("Chunks file not found.")

        self.index = faiss.read_index(str(index_path))

        with open(chunks_path, "r", encoding="utf-8") as file:
            self.chunks = json.load(file)

    def search(self, query: str, top_k: int = 5):
        """
        Find the most relevant PDF chunks for a query.
        """

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        scores, indices = self.index.search(
            query_embedding.astype("float32"),
            top_k
        )

        results = []

        for score, index in zip(scores[0], indices[0]):
            if index == -1:
                continue

            results.append({
                "score": float(score),
                "text": self.chunks[index]
            })

        return results


if __name__ == "__main__":
    retriever = Retriever()

    query = "What is the OSI model?"

    results = retriever.search(query, top_k=3)

    print("\nRelevant content:\n")

    for i, result in enumerate(results, start=1):
        print(f"\n--- Result {i} ---")
        print(f"Score: {result['score']:.4f}")
        print(result["text"][:1000])