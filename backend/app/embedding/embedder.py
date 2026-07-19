# Quản lý embedding.

# Chức năng:

# Tạo NVIDIAEmbeddings
# → embed câu hỏi
# → embed danh sách nội dung
# → tạo enriched text
# → cache vector theo hash

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

#save embeddings to a file
import hashlib
import json
from pathlib import Path
from typing import Any

from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk

#Neu khong co bien moi truong, mac dinh là baai
EMBEDDING_MODEL_NAME = os.getenv("NVIDIA_EMBEDDING_MODEL", "baai/bge-m3")

CACHE_DIR = Path(".cache/embedding_vectors.json")

def get_embedding() -> NVIDIAEmbeddings:
    """
    Get the NVIDIA embedding model.

    Returns:
        NVIDIAEmbeddings: The NVIDIA embedding model.
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY environment variable is not set.")
    
    return NVIDIAEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        api_key=api_key
        )
    
def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the NVIDIA embedding model.

    Args:
        texts (list[str]): A list of texts to embed.

    Returns:
        list[list[float]]: A list of embeddings for the input texts.
    """
    if not texts:
        raise ValueError("The input list of texts is empty.")
        return []
    
    embedding_model = get_embedding()
    return embedding_model.embed_documents(texts)

def embed_query(query: str) -> list[float]:
    """
    Embed a single query using the NVIDIA embedding model.

    Args:
        query (str): The query to embed.

    Returns:
        list[float]: The embedding for the input query.
    """
    query = query.strip()
    if not query:
        raise ValueError("The input query is empty.")
        return []
    
    embedding_model = get_embedding()
    return embedding_model.embed_query(query)

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
    
def embed_chunks_with_cache(
    document: MarkdownDocument,
    chunks: list[Chunk], 
    * ,
    model_name: str  = EMBEDDING_MODEL_NAME
    ) -> list[list[float]]:
    
    cache = load_vector_cache()
    vectors_by_key: dict[str, list[float]] = {}
    missing_chunks: list[Chunk] = []
    
    for chunk in chunks:
        embedding_text = build_embedding_enriched_text(document, chunk)
        hash_text_key = hash_text(embedding_text)
        cached_vector = cache.get(chunk.chunk_key)
        if(
            cached_vector 
            and cached_vector.get("model") == model_name
            and cached_vector.get("hash_text") == hash_text_key
        ): 
            vectors_by_key[chunk.chunk_key] = cached_vector["vector"]
        else:
            missing_chunks.append(chunk)
    
    if missing_chunks:
        embedding_texts = [
            build_embedding_enriched_text(document, chunk)
            for chunk in missing_chunks
        ]
        new_vectors = embed_texts(embedding_texts)
        for chunk, vector in zip(missing_chunks, new_vectors, strict=True):
            embedding_text = build_embedding_enriched_text(document, chunk)
            cache[chunk.chunk_key] = {
                "model": model_name,
                "hash_text": hash_text(embedding_text),
                "vector": vector,
            }
            vectors_by_key[chunk.chunk_key] = vector
        save_vector_cache(cache)

    return [vectors_by_key[chunk.chunk_key] for chunk in chunks]
