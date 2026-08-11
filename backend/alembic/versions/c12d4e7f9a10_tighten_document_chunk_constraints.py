"""Add the normative document_chunks checks from Contract 10."""

from typing import Sequence, Union

from alembic import op

revision: str = "c12d4e7f9a10"
down_revision: Union[str, Sequence[str], None] = "7b0c2fd5a1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    constraints = {
        "chk_document_chunks_parent": "(chunk_type = 'parent' AND parent_chunk_id IS NULL) OR (chunk_type = 'child' AND parent_chunk_id IS NOT NULL)",
        "chk_document_chunks_heading_path": "jsonb_typeof(heading_path) = 'array'",
        "chk_document_chunks_page_start": "page_start IS NULL OR page_start >= 1",
        "chk_document_chunks_page_end": "page_end IS NULL OR page_end >= 1",
        "chk_document_chunks_token_count": "token_count IS NULL OR token_count >= 0",
        "chk_document_chunks_index_status": "index_status IN ('not_indexed', 'indexed', 'deactivated', 'failed')",
    }
    for name, expression in constraints.items():
        op.create_check_constraint(name, "document_chunks", expression, schema="css")


def downgrade() -> None:
    for name in (
        "chk_document_chunks_index_status",
        "chk_document_chunks_token_count",
        "chk_document_chunks_page_end",
        "chk_document_chunks_page_start",
        "chk_document_chunks_heading_path",
        "chk_document_chunks_parent",
    ):
        op.drop_constraint(name, "document_chunks", schema="css", type_="check")
