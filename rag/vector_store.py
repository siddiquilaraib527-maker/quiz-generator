from pathlib import Path
import json
import faiss
import numpy as np

from .document_loader import load_pdf
from .chunker import split_text
from .embeddings import create_embeddings, create_faiss_index

DATA_DIR = Path(__file__).parent / "data"
VECTOR_DIR = Path(__file__).parent / "vectorstore"


def build_vector_store(pdf_path: str):
    """
    Create a FAISS vector store from a PDF.
    """

    print("Reading PDF...")
    text = load_pdf(pdf_path)

    if not text.strip():
        raise ValueError("No text could be extracted from the PDF.")

    print("Splitting text into chunks...")
    chunks = split_text(text)

    print(f"Created {len(chunks)} chunks.")

    print("Creating embeddings...")
    embeddings = create_embeddings(chunks)

    print("Creating FAISS index...")
    index = create_faiss_index(embeddings)

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    index_path = VECTOR_DIR / "index.faiss"
    chunks_path = VECTOR_DIR / "chunks.json"

    faiss.write_index(index, str(index_path))

    with open(chunks_path, "w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    print("Vector store created successfully!")
    print(f"Index: {index_path}")
    print(f"Chunks: {chunks_path}")


if __name__ == "__main__":
    pdf_files = list(DATA_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No PDF found in rag/data/")
        print("Please put a PDF inside rag/data/")

    else:
        pdf_path = pdf_files[0]

        print(f"Using PDF: {pdf_path.name}")

        build_vector_store(str(pdf_path))