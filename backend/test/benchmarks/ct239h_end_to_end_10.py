from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Callable

import httpx
import numpy as np
from langchain_core.documents import Document as LangChainDocument
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from app.databases.models import DocumentChunk
from app.databases.session import AsyncSessionLocal
from app.embedding.embedder import get_embedding
from app.retrieval.s7_hydration import hydrate_langchain_documents
from app.retrieval.s11_context_builder import build_retrieval_context
from test.benchmarks.common import (
    citation_precision,
    input_path,
    load_benchmark,
    no_answer_correct,
    summary_chart,
    write_csv,
    write_json,
)


DEFAULT_RAGAS_MODEL = "qwen/qwen3-next-80b-a3b-instruct"
DEFAULT_RAGAS_MAX_TOKENS = 1024
DEFAULT_RAGAS_BATCH_SIZE = 5


class ProjectBGEEmbeddings(Embeddings):
    """Expose the project's Cloudflare BGE-M3 embedder as LangChain Embeddings."""

    def __init__(self) -> None:
        self._embedding = get_embedding()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedding.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedding.embed_query(text)


def save_checkpoint(
    checkpoint_path: Path,
    *,
    source_name: str,
    rows: list[dict],
) -> None:
    """Persist progress so endpoint/RAGAS work is not lost after an error."""

    write_json(
        checkpoint_path,
        {
            "source_test_file": source_name,
            "rows": rows,
        },
    )


def load_checkpoint(
    checkpoint_path: Path,
    *,
    source_name: str,
    valid_case_ids: set[str],
) -> list[dict]:
    """Load and validate a previous benchmark checkpoint."""

    if not checkpoint_path.exists():
        return []

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    if payload.get("source_test_file") != source_name:
        raise RuntimeError(
            "Checkpoint thuộc test file khác: "
            f"{payload.get('source_test_file')!r} != {source_name!r}"
        )

    rows = payload.get("rows") or []
    checkpoint_ids = {row.get("id") for row in rows}

    unknown_ids = checkpoint_ids - valid_case_ids
    if unknown_ids:
        raise RuntimeError(
            "Checkpoint chứa case không có trong input hiện tại: "
            f"{sorted(unknown_ids)}"
        )

    return rows


async def run_case(
    client: httpx.AsyncClient,
    case: dict,
) -> dict:
    """Run one case through the real production RAG endpoint."""

    started = time.perf_counter()

    response = await client.post(
        "/api/v1/rag/answer",
        json={
            "question": case["question"],
            "top_k": 5,
        },
    )

    latency = time.perf_counter() - started

    response.raise_for_status()
    payload = response.json()

    return {
        "id": case["id"],
        "question": case["question"],
        "answerable": case["answerable"],
        "reference_facts": case["reference_facts"],
        "expected_document_keys": case["expected_document_keys"],
        "expected_behavior": case.get("expected_behavior"),
        "response": payload,
        "http_status": response.status_code,
        "response_latency_seconds": latency,
        "citation_precision": citation_precision(
            payload["citations"],
            case["expected_document_keys"],
            answerable=case["answerable"],
        ),
        "no_answer_correct": (
            not case["answerable"]
            and no_answer_correct(payload)
        ),
        "answer_correctness": None,
        "faithfulness": None,
        "evaluation_contexts": [],
    }


async def attach_evaluation_contexts(
    rows: list[dict],
) -> None:
    """
    Rebuild the same bounded context used by production generation.

    The API returns conversation_context.used_chunk_keys instead of document
    contents. The benchmark resolves those child keys from PostgreSQL,
    reuses the production hydration code, then reuses build_retrieval_context().
    This makes Faithfulness compare the answer with the evidence the generator
    actually had available, while keeping full document content off the public API.
    """

    all_chunk_keys: set[str] = set()

    row_chunk_keys: dict[str, list[str]] = {}

    for row in rows:
        conversation_context = (
            row["response"].get("conversation_context") or {}
        )

        chunk_keys = (
            conversation_context.get("used_chunk_keys")
            or []
        )

        # Preserve production order while removing duplicates.
        chunk_keys = list(dict.fromkeys(chunk_keys))

        row_chunk_keys[row["id"]] = chunk_keys
        all_chunk_keys.update(chunk_keys)

    if not all_chunk_keys:
        for row in rows:
            row["evaluation_contexts"] = []
        return

    async with AsyncSessionLocal() as session:
        chunk_rows = (
            await session.execute(
                select(
                    DocumentChunk.id,
                    DocumentChunk.chunk_key,
                ).where(
                    DocumentChunk.chunk_key.in_(all_chunk_keys)
                )
            )
        ).all()

        chunk_id_by_key = {
            chunk_key: chunk_id
            for chunk_id, chunk_key in chunk_rows
        }

        for row in rows:
            docs: list[LangChainDocument] = []

            for chunk_key in row_chunk_keys[row["id"]]:
                chunk_id = chunk_id_by_key.get(chunk_key)

                if chunk_id is None:
                    continue

                docs.append(
                    LangChainDocument(
                        page_content="",
                        metadata={
                            "postgres_chunk_id": chunk_id,
                        },
                    )
                )

            if not docs:
                row["evaluation_contexts"] = []
                continue

            hydrated_results = await hydrate_langchain_documents(
                session,
                docs,
            )

            context = build_retrieval_context(
                hydrated_results,
                max_characters=12_000,
            )

            row["evaluation_contexts"] = (
                [context] if context else []
            )

            if (
                row["answerable"]
                and row["response"].get("answer_status")
                == "answered"
                and not context
            ):
                raise RuntimeError(
                    f"{row['id']}: answer_status='answered' nhưng "
                    "không dựng lại được production retrieval context."
                )


def build_ragas_evaluators():
    """
    Configure RAGAS explicitly.

    LLM judge:
      RAGAS_LLM_MODEL -> fallback LLM_MODEL -> project default.
      Uses the existing OpenRouter-compatible LLM_API_KEY / LLM_BASE_URL.

    Embeddings:
      Uses the project's Cloudflare Workers AI BGE-M3 embedder.

    This avoids RAGAS silently creating an OpenAI evaluator and asking for
    OPENAI_API_KEY.
    """

    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY chưa được cấu hình.")

    base_url = os.getenv(
        "LLM_BASE_URL",
        "https://openrouter.ai/api/v1",
    )

    model = os.getenv(
        "RAGAS_LLM_MODEL",
        os.getenv("LLM_MODEL", DEFAULT_RAGAS_MODEL),
    )

    max_tokens = int(
        os.getenv(
            "RAGAS_MAX_TOKENS",
            str(DEFAULT_RAGAS_MAX_TOKENS),
        )
    )

    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0,
            max_tokens=max_tokens,
            request_timeout=180,
            max_retries=0,
        )
    )

    evaluator_embeddings = LangchainEmbeddingsWrapper(
        ProjectBGEEmbeddings()
    )

    return evaluator_llm, evaluator_embeddings


def ragas_scores(
    rows: list[dict],
    *,
    checkpoint_callback: Callable[[], None],
    ragas_batch_size: int,
) -> None:
    """
    Score only answerable cases.

    RAGAS:
      - Faithfulness: generated answer vs reconstructed production context.
      - Answer Correctness: generated answer vs reviewed reference facts.

    Results are checkpointed after every small batch so a later provider error
    does not force the whole endpoint benchmark or all previous RAGAS judging
    to run again.
    """

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import AnswerCorrectness, Faithfulness
    from ragas.run_config import RunConfig

    evaluator_llm, evaluator_embeddings = build_ragas_evaluators()

    pending_rows = [
        row
        for row in rows
        if (
            row["answerable"]
            and (
                row.get("answer_correctness") is None
                or row.get("faithfulness") is None
            )
        )
    ]

    if not pending_rows:
        print("RAGAS: không còn case answerable nào cần chấm.")
        return

    run_config = RunConfig(
        timeout=180,
        max_retries=1,
        max_wait=10,
        max_workers=1,
        seed=42,
    )

    total = len(pending_rows)

    for start in range(0, total, ragas_batch_size):
        batch_rows = pending_rows[
            start : start + ragas_batch_size
        ]

        dataset = Dataset.from_dict(
            {
                "question": [
                    row["question"]
                    for row in batch_rows
                ],
                "answer": [
                    row["response"]["answer"]
                    for row in batch_rows
                ],
                "contexts": [
                    row["evaluation_contexts"]
                    for row in batch_rows
                ],
                "ground_truth": [
                    "\n".join(row["reference_facts"])
                    for row in batch_rows
                ],
            }
        )

        result = evaluate(
            dataset,
            metrics=[
                Faithfulness(),
                AnswerCorrectness(),
            ],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            run_config=run_config,
            raise_exceptions=True,
            show_progress=True,
        )

        table = result.to_pandas()

        for row, (_, score) in zip(
            batch_rows,
            table.iterrows(),
            strict=True,
        ):
            row["answer_correctness"] = float(
                score["answer_correctness"]
            )

            row["faithfulness"] = float(
                score["faithfulness"]
            )

        checkpoint_callback()

        finished = min(
            start + len(batch_rows),
            total,
        )

        print(
            f"RAGAS scored {finished}/{total} pending answerable cases."
        )


async def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--input")

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument("--output-dir")

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse ct239h_e2e_checkpoint.json and continue only "
            "unfinished endpoint/RAGAS cases."
        ),
    )

    parser.add_argument(
        "--ragas-batch-size",
        type=int,
        default=DEFAULT_RAGAS_BATCH_SIZE,
    )

    args = parser.parse_args()

    if args.ragas_batch_size < 1:
        raise ValueError("--ragas-batch-size phải >= 1.")

    source = input_path(
        "ct239h_end_to_end_10.json",
        args.input,
    )

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else source.parent
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = load_benchmark(source)

    benchmark_cases = payload["cases"]

    valid_case_ids = {
        benchmark_case["id"]
        for benchmark_case in benchmark_cases
    }

    checkpoint_path = (
        output_dir / "ct239h_e2e_checkpoint.json"
    )

    rows: list[dict] = []

    if args.resume:
        rows = load_checkpoint(
            checkpoint_path,
            source_name=source.name,
            valid_case_ids=valid_case_ids,
        )

        if rows:
            print(
                f"Resume checkpoint: {len(rows)} endpoint cases đã có."
            )

    row_by_id = {
        row["id"]: row
        for row in rows
    }

    # ---------------------------------------------------------
    # 1. Run only endpoint cases that are not already checkpointed
    # ---------------------------------------------------------

    missing_cases = [
        benchmark_case
        for benchmark_case in benchmark_cases
        if benchmark_case["id"] not in row_by_id
    ]

    if missing_cases:
        async with httpx.AsyncClient(
            base_url=args.base_url.rstrip("/"),
            timeout=180,
        ) as client:

            for benchmark_case in missing_cases:
                row = await run_case(
                    client,
                    benchmark_case,
                )

                row_by_id[row["id"]] = row

                # Keep original benchmark order.
                rows = [
                    row_by_id[case["id"]]
                    for case in benchmark_cases
                    if case["id"] in row_by_id
                ]

                save_checkpoint(
                    checkpoint_path,
                    source_name=source.name,
                    rows=rows,
                )

                print(
                    f"Endpoint completed: {len(rows)}/"
                    f"{len(benchmark_cases)} "
                    f"({benchmark_case['id']})"
                )

    rows = [
        row_by_id[case["id"]]
        for case in benchmark_cases
    ]

    # ---------------------------------------------------------
    # 2. Reconstruct actual production contexts
    # ---------------------------------------------------------

    await attach_evaluation_contexts(rows)

    save_checkpoint(
        checkpoint_path,
        source_name=source.name,
        rows=rows,
    )

    # ---------------------------------------------------------
    # 3. RAGAS evaluation with explicit OpenRouter + BGE-M3
    # ---------------------------------------------------------

    def checkpoint_after_ragas_batch() -> None:
        save_checkpoint(
            checkpoint_path,
            source_name=source.name,
            rows=rows,
        )

    ragas_scores(
        rows,
        checkpoint_callback=checkpoint_after_ragas_batch,
        ragas_batch_size=args.ragas_batch_size,
    )

    # ---------------------------------------------------------
    # 4. Aggregate metrics
    # ---------------------------------------------------------

    latencies = [
        row["response_latency_seconds"]
        for row in rows
    ]

    answerable_rows = [
        row
        for row in rows
        if row["answerable"]
    ]

    unanswerable_rows = [
        row
        for row in rows
        if not row["answerable"]
    ]

    scores = {
        "answer_correctness": float(
            np.mean(
                [
                    row["answer_correctness"]
                    for row in answerable_rows
                ]
            )
        ),
        "faithfulness": float(
            np.mean(
                [
                    row["faithfulness"]
                    for row in answerable_rows
                ]
            )
        ),
        "citation_precision": float(
            np.mean(
                [
                    row["citation_precision"]
                    for row in answerable_rows
                ]
            )
        ),
        "no_answer_accuracy": float(
            np.mean(
                [
                    row["no_answer_correct"]
                    for row in unanswerable_rows
                ]
            )
        ),
        "mean_latency_seconds": float(
            np.mean(latencies)
        ),
        "p95_latency_seconds": float(
            np.quantile(latencies, 0.95)
        ),
    }

    # ---------------------------------------------------------
    # 5. Per-case result
    # ---------------------------------------------------------

    cases = []

    for row in rows:
        cases.append(
            {
                "id": row["id"],
                "input": {
                    "question": row["question"],
                },
                "expected": {
                    "answerable": row["answerable"],
                    "document_keys": row[
                        "expected_document_keys"
                    ],
                    "reference_facts": row[
                        "reference_facts"
                    ],
                    "expected_behavior": (
                        row.get("expected_behavior")
                        or (
                            None
                            if row["answerable"]
                            else "insufficient_evidence"
                        )
                    ),
                },
                "actual": {
                    "http_status": row["http_status"],
                    "should_search": row["response"][
                        "should_search"
                    ],
                    "answer_status": row["response"].get(
                        "answer_status"
                    ),
                    "answer": row["response"]["answer"],
                    "citations": row["response"][
                        "citations"
                    ],
                    "used_chunk_keys": (
                        row["response"].get(
                            "conversation_context"
                        )
                        or {}
                    ).get(
                        "used_chunk_keys",
                        [],
                    ),
                    "evaluation_contexts": row[
                        "evaluation_contexts"
                    ],
                    "response_latency_seconds": row[
                        "response_latency_seconds"
                    ],
                    "answer_correctness": row[
                        "answer_correctness"
                    ],
                    "faithfulness": row[
                        "faithfulness"
                    ],
                    "citation_precision": row[
                        "citation_precision"
                    ],
                    "no_answer_correct": (
                        None
                        if row["answerable"]
                        else row["no_answer_correct"]
                    ),
                    "notes": None,
                },
            }
        )

    # ---------------------------------------------------------
    # 6. Final JSON / CSV / chart
    # ---------------------------------------------------------

    result = {
        "meta": {
            "name": "CT239H End-to-End RAG Results",
            "source_test_file": source.name,
            "case_count": len(rows),
            "answerable_count": len(answerable_rows),
            "unanswerable_count": len(unanswerable_rows),
            "ragas_llm_model": os.getenv(
                "RAGAS_LLM_MODEL",
                os.getenv(
                    "LLM_MODEL",
                    DEFAULT_RAGAS_MODEL,
                ),
            ),
            "ragas_embedding_model": os.getenv(
                "EMBEDDING_MODEL",
                "@cf/baai/bge-m3",
            ),
            "note": (
                "Production RAG endpoint evaluation. Faithfulness uses "
                "the production context reconstructed from "
                "conversation_context.used_chunk_keys with the same "
                "PostgreSQL hydration and bounded context builder. "
                "Answer Correctness and Faithfulness are evaluated "
                "only for answerable cases."
            ),
        },
        "summary": scores,
        "cases": cases,
    }

    write_json(
        output_dir / "ct239h_e2e_results.json",
        result,
    )

    write_csv(
        output_dir / "ct239h_e2e_results.csv",
        [
            {
                "id": case["id"],
                "question": case["input"]["question"],
                "answerable": case["expected"][
                    "answerable"
                ],
                "expected_document_keys": case[
                    "expected"
                ]["document_keys"],
                "reference_facts": case["expected"][
                    "reference_facts"
                ],
                "expected_behavior": case["expected"][
                    "expected_behavior"
                ],
                **case["actual"],
            }
            for case in cases
        ],
    )

    summary_chart(
        output_dir / "ct239h_e2e_summary.png",
        "CT239H End-to-End RAG Evaluation",
        scores,
        seconds={
            "mean_latency_seconds",
            "p95_latency_seconds",
        },
    )

    print("\nDONE")
    print(json.dumps(scores, indent=2, ensure_ascii=False))
    print(f"Checkpoint: {checkpoint_path}")
    print(
        "Final JSON: "
        f"{output_dir / 'ct239h_e2e_results.json'}"
    )
    print(
        "Final CSV: "
        f"{output_dir / 'ct239h_e2e_results.csv'}"
    )
    print(
        "Summary chart: "
        f"{output_dir / 'ct239h_e2e_summary.png'}"
    )


if __name__ == "__main__":
    asyncio.run(main())
