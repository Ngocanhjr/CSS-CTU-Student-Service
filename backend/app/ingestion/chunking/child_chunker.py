# Chia nội dung Parent thành các Child nhỏ hơn theo:

# kích thước chunk;
# overlap;
# metadata của Parent.

# Sau đó tạo các object Chunk loại child.

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion.chunking.text_stats import count_units
from app.ingestion.parsing.page_markers import require_page_range
from app.schemas.chunks import Chunk
def build_child_splitter(
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        separators=[
            "\n\\*\\*\\**\n", # Horizontal rules (---, ***, ___)
            "\n---+\n", # Horizontal rules (---, ***, ___)
            "\n___+\n", # Horizontal rules (---, ***, ___)
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        strip_whitespace=True, #remove whitespace at the beginning and end of each chunk
    )
    
def split_parent_chunk_to_child_texts(
    parent_chunk: Chunk,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,) -> list[str]:
        splitter = build_child_splitter(
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        texts = splitter.split_text(parent_chunk.content)
        return [text.strip() for text in texts if text.strip()]
    
def make_child_chunks(
    *,
    child_texts: list[str],
    parent_chunk: Chunk,
    document_key: str,
    version_key: str,
    child_start_index: int,
    chunk_start_index: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for offset, text in enumerate(child_texts):
        # offset: index trong parent (0, 1, 2...)
        # child_number: index tich luy qua cac parent cho stable key
        child_number = child_start_index + offset
        # Tim page marker trong child text.
        # Neu child ko co marker, fallback ve page range cua parent chunk.
        page_start, page_end = require_page_range(
            text,
            fallback=(parent_chunk.page_start, parent_chunk.page_end),
        )

        chunks.append(
            Chunk(
                document_key=document_key,
                version_key=version_key,
                chunk_key=f"{version_key}::c::{child_number:04d}",
                parent_chunk_key=parent_chunk.chunk_key,
                chunk_type="child",
                content=text,
                heading_path=parent_chunk.heading_path,
                page_start=page_start,
                page_end=page_end,
                chunk_index=chunk_start_index + offset,
                token_count=count_units(text),
            )
        )
    return chunks