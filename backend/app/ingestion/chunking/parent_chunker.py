# Chia tài liệu theo Markdown heading:

# Heading
## Heading
### Heading

from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.ingestion.chunking.text_stats import count_units
from app.ingestion.parsing.page_markers import require_page_range
from dataclasses import dataclass
from app.schemas.chunks import Chunk

#khong cho phai thay doi object sau khi tao
@dataclass(frozen=True)
class ParentSection:
    content: str
    heading_path: list[str]
    page_start: int
    page_end: int    
    
HEADERS_TO_SPLIT_ON = [
    ("#", "h1" ),
    ("##", "h2" ),
    ("###", "h3" ),
    ("####", "h4" ),
    ("#####", "h5" ),
    ("######", "h6" ),
]

def make_parent_section(
    content: str,
    heading_path: list[str],
    *,
    fallback_page_range: tuple[int, int] | None = None,
) -> ParentSection:
    page_start, page_end = require_page_range(content, fallback=fallback_page_range)
    return ParentSection(
        content=content,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
    )
    
def build_parent_sections(body:str) -> list[ParentSection]:
    #tạo splitter 
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False)
    
    #tach heading va noi dung theo heading
    docs = splitter.split_text(body)
    
    if not docs:
        return [make_parent_section(body.strip(), ["Document"], fallback_page_range=(1, 1))]
    
    sections: list[ParentSection] = []
    
    for doc in docs:
        content = doc.page_content.strip()
        if not content:
            continue
        
        metadata = doc.metadata or {}
        
        heading_path = [
            str(metadata[key]).strip()
            for key in ("h1", "h2", "h3", "h4", "h5", "h6")
            if metadata.get(key)
        ] or ["Document"]
        
        sections.append(make_parent_section(content, heading_path, fallback_page_range=(1, 1)))

    return sections

def make_parent_chunk(    *,
    section: ParentSection,
    document_key: str,
    version_key: str,
    parent_index: int,
    chunk_index: int,
) -> Chunk:
    parent_key = f"{version_key}::p::{parent_index:04d}"
    return Chunk(
        document_key = document_key,
        version_key = version_key,

        chunk_key = parent_key,
        chunk_type = "parent",

        content = section.content,
        heading_path = section.heading_path,

        page_start = section.page_start,
        page_end = section.page_end,
        chunk_index = chunk_index,
        token_count = count_units(section.content)

    )
