from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk

from app.ingestion.chunking.child_chunker import (
    make_child_chunks,
    split_parent_chunk_to_child_texts,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)

def chunk_markdown_body(
    *,
    body: str,  
    document_key: str,
    version_key: str,
    child_chunk_size: int = 1200,
    child_chunk_overlap: int = 100,
) -> list[Chunk]:
    if not body.strip():
        raise ValueError("Markdown body is empty")
    
    sections = build_parent_sections(body)
    chunks: list[Chunk] = []
    child_counter = 1
    chunk_index = 0
    
    for parent_counter, section in enumerate(sections, start=1):
        parent = make_parent_chunk(
            section=section,
            document_key=document_key,
            version_key=version_key,
            parent_index=parent_counter,
            chunk_index=chunk_index,
        )
        chunk_index += 1
        
        child_texts = split_parent_chunk_to_child_texts(
            parent,
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        
        child_chunks = make_child_chunks(
            child_texts=child_texts,
            parent_chunk=parent,
            document_key=document_key,
            version_key=version_key,
            child_start_index=child_counter,
            chunk_start_index=chunk_index,
        )
        
        chunks.append(parent)
        chunks.extend(child_chunks)
        
        child_counter += len(child_chunks)
        chunk_index += len(child_chunks)
    
    return chunks

def chunk_markdown_document(document: MarkdownDocument) -> list[Chunk]:
    return chunk_markdown_body(
        body=document.body,
        document_key=document.metadata.document_key,
        version_key=document.metadata.version_key
    )

