from pathlib import Path

def index_document(path: str | Path) -> int:
    raise RuntimeError(
        "Legacy one-shot indexing is disabled; use "
        "app.ingestion.indexing_service.index_document_version"
    )

path = Path(__file__).parent / "chunking" / "test" / "Noi quy KTX nam 2016_llp.md"

if __name__ == "__main__":
    if not path:
        raise ValueError("Markdown path is required")
    inserted = index_document(path)
    print(f"Inserted {inserted} chunks")
