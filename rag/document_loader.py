from pathlib import Path
from pypdf import PdfReader


def load_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(path))

    text = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text.append(page_text)

    return "\n\n".join(text)


if __name__ == "__main__":
    print("PDF loader is ready.")