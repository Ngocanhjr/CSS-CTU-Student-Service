# Hàm điều phối việc index một tài liệu:

from app.embedding.embedder import embed_chunks_with_cache, get_embedding
from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import (
    upsert_chunks,
)

from pathlib import Path

def index_document(path: str | Path) -> int:
    """     
    Index a markdown document by reading, chunking, embedding, and upserting to Qdrant.

    Args:
        path (str | Path): The path to the markdown document.
    
    Returns:
        int: The number of chunks indexed.
    """
    print(f"Indexing document: {path}")
    document = read_markdown_document(path)
    print('Read document successfully. Chunking...')
    chunks = chunk_markdown_document(document)
    child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]
    if not child_chunks:
        raise ValueError("No child chunks generated")
    
    print('Chunking completed. Embedding and upserting to Qdrant...')
    vectors = embed_chunks_with_cache(document, child_chunks)
    
    client = get_qdrant_client()
    print('Upserting chunks to Qdrant...')
    return upsert_chunks(client, document, child_chunks, vectors)

path = Path(__file__).parent / "chunking" / "test" / "Noi quy KTX nam 2016_llp.md"

if not path:
        raise ValueError("Markdown path is required")
inserted = index_document(path)

with open("answer.txt", "w", encoding="utf-8") as file:
        file.write(str(inserted))