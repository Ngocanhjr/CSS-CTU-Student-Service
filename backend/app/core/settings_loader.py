from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RUNTIME_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "runtime.yaml"
)

#default value 
@dataclass(frozen=True)
class ChunkingSettings:
    child_chunk_size: int = 1000
    child_chunk_overlap: int = 100
    # chunking_strategy: str = "recursive"
    # chunking_depth: int = 2
    # chunking_heading_levels: list[str] = field(default_factory=lambda: ["h1", "h2", "h3"])
    # chunking_min_heading_length: int = 5
    # chunking_max_heading_length: int = 100
    # chunking_min_content_length: int = 50
    # chunking_max_content_length: int = 5000
    
@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int = 5
    candidate_k: int = 30
    score_threshold: float = 0.5
    
@dataclass(frozen=True)
class AppSettings:
    chunking: ChunkingSettings = field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)
    
def load_settings(path: str | Path) -> AppSettings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    
    settings = AppSettings(
        chunking=ChunkingSettings(**data.get("chunking", {})),
        retrieval=RetrievalSettings(**data.get("retrieval", {})),
    )
    validate_settings(settings)
    return settings

 
"""@lru_cache (Least Recently Used) là một decorator trong Python, thường import từ functools.

Ý nghĩa: nó nhớ kết quả của hàm sau lần gọi đầu tiên, rồi những lần gọi lại với cùng tham số thì trả kết quả đã cache, không chạy lại hàm nữa.
"""

@lru_cache
def get_rag_settings() -> AppSettings:
    return load_settings(DEFAULT_RUNTIME_CONFIG)
  
def validate_settings(settings: AppSettings) -> None:
    if settings.chunking.child_chunk_size <= 0:
        raise ValueError("chunking.child_chunk_size must be > 0")
    if settings.chunking.child_chunk_overlap < 0:
        raise ValueError("chunking.child_chunk_overlap must be >= 0")
    if settings.chunking.child_chunk_overlap >= settings.chunking.child_chunk_size:
        raise ValueError("chunking.child_chunk_overlap must be smaller than child_chunk_size")
    if settings.retrieval.top_k <= 0:
        raise ValueError("retrieval.top_k must be > 0")
    if settings.retrieval.candidate_k < settings.retrieval.top_k:
        raise ValueError("retrieval.candidate_k must be >= retrieval.top_k")
    if not 0 <= settings.retrieval.score_threshold <= 1:
        raise ValueError("retrieval.score_threshold must be between 0 and 1")