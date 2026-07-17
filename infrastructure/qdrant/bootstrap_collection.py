"""Create the Qdrant collection and payload indexes for chatbot retrieval."""

from __future__ import annotations

import os

from qdrant_client import QdrantClient, models


COLLECTION_NAME = "ctu_chunks_bge_m3"
VECTOR_NAME = "embedding"
VECTOR_SIZE = 1024

PAYLOAD_INDEXES = {
    models.PayloadSchemaType.KEYWORD: (
        "document_key",
        "version_key",
        "document_type",
        "domain",
        "audience",
        "review_status",
        "rag_status",
        "chunk_key",
        "parent_chunk_key",
        "chunk_type",
        "block_type",
        "legal_unit_type",
        "logical_item_key",
        "parent_item_key",
        "logical_table_key",
        "logical_code_key",
    ),
    models.PayloadSchemaType.BOOL: ("audience_student", "is_latest"),
    models.PayloadSchemaType.INTEGER: (
        "postgres_chunk_id",
        "postgres_parent_chunk_id",
    ),
}


def _client() -> QdrantClient:
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )


def _verify_existing_collection(client: QdrantClient) -> None:
    vectors = client.get_collection(COLLECTION_NAME).config.params.vectors
    if not isinstance(vectors, dict) or VECTOR_NAME not in vectors:
        raise RuntimeError(
            f"{COLLECTION_NAME!r} does not expose named vector {VECTOR_NAME!r}"
        )

    vector = vectors[VECTOR_NAME]
    if vector.size != VECTOR_SIZE or vector.distance != models.Distance.COSINE:
        raise RuntimeError(
            f"{COLLECTION_NAME!r} has an incompatible vector contract: "
            f"expected {VECTOR_NAME}/{VECTOR_SIZE}/Cosine"
        )


def _ensure_payload_indexes(client: QdrantClient) -> None:
    existing = client.get_collection(COLLECTION_NAME).payload_schema

    for schema, fields in PAYLOAD_INDEXES.items():
        for field in fields:
            current = existing.get(field)
            if current is not None:
                if current.data_type != schema:
                    raise RuntimeError(
                        f"Payload index {field!r} is {current.data_type}, expected {schema}"
                    )
                continue

            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=schema,
                wait=True,
            )


def main() -> None:
    client = _client()

    if client.collection_exists(COLLECTION_NAME):
        _verify_existing_collection(client)
    else:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                VECTOR_NAME: models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                )
            },
        )

    _ensure_payload_indexes(client)

    print(f"Qdrant collection ready: {COLLECTION_NAME}")


if __name__ == "__main__":
    main()
