import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import find_dotenv, load_dotenv

from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk


load_dotenv(find_dotenv())


EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL","@cf/baai/bge-m3",)
EMBEDDING_VECTOR_SIZE = 1024
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "4"))

CACHE_DIR = Path(".cache/embedding_vectors.json")


if EMBEDDING_BATCH_SIZE < 1:
    raise ValueError("EMBEDDING_BATCH_SIZE phải lớn hơn 0.")


class CloudflareEmbeddings:
    """HTTP client tối thiểu cho Cloudflare Workers AI."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
    ) -> None:
        self.account_id = account_id
        self.api_token = api_token
        self.model = EMBEDDING_MODEL_NAME

        self.base_url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model}"
        )

    def _embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        request = Request(
            self.base_url,
            data=json.dumps(
                {"text": texts}
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=120) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as exc:
            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"Cloudflare trả HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Không kết nối được Cloudflare: {exc.reason}"
            ) from exc

        if not response_data.get("success"):
            raise RuntimeError(
                f"Cloudflare embedding thất bại: {response_data}"
            )

        result = response_data.get("result", {})
        vectors = result.get("data")

        if (
            not isinstance(vectors, list)
            or len(vectors) != len(texts)
            or any(
                not isinstance(vector, list)
                for vector in vectors
            )
        ):
            raise RuntimeError(
                "Cloudflare trả response không đúng contract."
            )

        invalid_sizes = {
            len(vector)
            for vector in vectors
            if len(vector) != EMBEDDING_VECTOR_SIZE
        }

        if invalid_sizes:
            raise RuntimeError(
                f"{self.model} phải trả vector "
                f"{EMBEDDING_VECTOR_SIZE} chiều, "
                f"nhận được {sorted(invalid_sizes)}."
            )

        return vectors

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        vectors: list[list[float]] = []

        for start in range(
            0,
            len(texts),
            EMBEDDING_BATCH_SIZE,
        ):
            batch = texts[
                start : start + EMBEDDING_BATCH_SIZE
            ]
            vectors.extend(
                self._embed_batch(batch)
            )

        return vectors

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        query = query.strip()

        if not query:
            raise ValueError("Query không được để trống.")

        return self._embed_batch([query])[0]


def get_embedding() -> CloudflareEmbeddings:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if not account_id:
        raise ValueError(
            "CLOUDFLARE_ACCOUNT_ID chưa được cấu hình."
        )

    if not api_token:
        raise ValueError(
            "CLOUDFLARE_API_TOKEN chưa được cấu hình."
        )

    return CloudflareEmbeddings(
        account_id=account_id,
        api_token=api_token,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        raise ValueError("Danh sách text không được để trống.")

    return get_embedding().embed_documents(texts)


def embed_query(query: str) -> list[float]:
    return get_embedding().embed_query(query)

#method for save embedding file
def hash_text(text:str) -> str:
    """
    Generate a SHA256 hash for the given text.

    Args:
        text (str): The input text to hash.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_vector_cache(path: Path = CACHE_DIR) -> dict[str, dict[str, Any]]:
    """
    Load the embedding vector cache from a JSON file.

    Args:
        path (Path): The path to the cache file.
    """
    if not path.exists() or path.stat().st_size == 0:
        return {}
        
    return json.loads(path.read_text(encoding="utf-8"))

def save_vector_cache(cache: dict[str, dict[str, Any]], path: Path = CACHE_DIR) -> None:
    """
    Save the embedding vector cache to a JSON file.

    Args:
        cache (dict): The embedding vector cache to save.
        path (Path): The path to the cache file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    
def build_embedding_enriched_text(document: MarkdownDocument , chunk: Chunk)-> str:
    """
    Build enriched text for embedding from a document and chunk.

    Args:
        document (MarkdownDocument): The markdown document.
        chunk (Chunk): The chunk of text.

    Returns:
        str: The enriched text for embedding.
    """
    metadata = document.metadata
    page = f"Page {chunk.page_start}-{chunk.page_end}" if chunk.page_start and chunk.page_end else ""
    return "\n".join(
        [
           f"Tài liệu: {metadata.title}",
            f"Đơn vị: {', '.join(metadata.responsible_department)}",
            f"Loại: {metadata.document_type}",
            f"Mục: {' > '.join(chunk.heading_path)}",
            page,
            "",
            chunk.content.strip(),
        ]
    )
    
async def embed_chunks_with_cache(
    document: MarkdownDocument,
    chunks: list[Chunk],
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
    progress_callback: Callable[[int], Awaitable[None]] | None = None,
) -> list[list[float]]:
    cache = load_vector_cache()
    vectors_by_key: dict[str, list[float]] = {}
    missing_chunks: list[Chunk] = []
    cached_count = 0

    for chunk in chunks:
        embedding_text = build_embedding_enriched_text(document, chunk)
        hash_text_key = hash_text(embedding_text)
        cached_vector = cache.get(chunk.chunk_key)
        if(
            cached_vector 
            and cached_vector.get("model") == model_name
            and cached_vector.get("hash_text") == hash_text_key
            and len(cached_vector.get("vector", [])) == EMBEDDING_VECTOR_SIZE
        ): 
            vectors_by_key[chunk.chunk_key] = cached_vector["vector"]
            cached_count += 1
        else:
            missing_chunks.append(chunk)

    if cached_count and progress_callback:
        await progress_callback(cached_count)

    if missing_chunks:
        for start in range(0, len(missing_chunks), EMBEDDING_BATCH_SIZE):
            batch = missing_chunks[start : start + EMBEDDING_BATCH_SIZE]
            embedding_texts = [
                build_embedding_enriched_text(document, chunk)
                for chunk in batch
            ]
            new_vectors = await asyncio.to_thread(embed_texts, embedding_texts)
            invalid_sizes = {len(vector) for vector in new_vectors if len(vector) != EMBEDDING_VECTOR_SIZE}
            if invalid_sizes:
                raise ValueError(
                    f"{model_name} phải trả vector {EMBEDDING_VECTOR_SIZE} chiều, nhận được {sorted(invalid_sizes)}"
                )
            for chunk, vector, embedding_text in zip(batch, new_vectors, embedding_texts, strict=True):
                cache[chunk.chunk_key] = {
                    "model": model_name,
                    "hash_text": hash_text(embedding_text),
                    "vector": vector,
                }
                vectors_by_key[chunk.chunk_key] = vector
            if progress_callback:
                await progress_callback(len(batch))
        save_vector_cache(cache)

    return [vectors_by_key[chunk.chunk_key] for chunk in chunks]
