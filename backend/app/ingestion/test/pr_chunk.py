from pathlib import Path

from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document

path = Path(__file__).parent / "Noi quy KTX nam 2016_llp.md"
output_path = Path(__file__).parent / "chunk_nq_ktx.txt"

document = read_markdown_document(path)
chunks = chunk_markdown_document(document)

lines: list[str] = []

for chunk in chunks:
    lines.append(
        "\n".join(
            [
                f"chunk_index: {chunk.chunk_index}",
                f"chunk_type: {chunk.chunk_type}",
                f"chunk_key: {chunk.chunk_key}",
                f"parent_chunk_key: {chunk.parent_chunk_key}",
                f"page_start: {chunk.page_start}",
                f"page_end: {chunk.page_end}",
                f"heading_path: {' > '.join(chunk.heading_path)}",
                "content:",
                chunk.content,
                "-" * 80,
            ]
        )
    )

output = "\n\n".join(lines)
output_path.write_text(output, encoding="utf-8")

print(output)
print(f"\nSaved chunk output to: {output_path}")
