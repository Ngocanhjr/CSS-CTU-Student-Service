from pathlib import Path


def test_chunk_constraint_migration_matches_contract():
    migration = next(Path(__file__).parents[2].glob("alembic/versions/*tighten_document_chunk_constraints.py"))
    text = migration.read_text(encoding="utf-8")
    for name in (
        "chk_document_chunks_parent",
        "chk_document_chunks_heading_path",
        "chk_document_chunks_page_start",
        "chk_document_chunks_page_end",
        "chk_document_chunks_token_count",
        "chk_document_chunks_index_status",
    ):
        assert name in text
