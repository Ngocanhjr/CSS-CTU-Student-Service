from __future__ import annotations

import json
import os
import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def input_path(name: str, supplied: str | None) -> Path:
    fixture_dir = Path(__file__).resolve().parents[1] / "file_test"
    candidates = [
        Path(supplied) if supplied else None,
        fixture_dir / name,
        Path.cwd() / name,
        Path(os.getenv("CT239H_EVAL_DATA_DIR", "")) / name,
        Path.home() / "Downloads" / name,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Không tìm thấy {name}; dùng --input hoặc CT239H_EVAL_DATA_DIR.")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_benchmark(path: Path | str) -> dict[str, Any]:
    """Load JSON benchmark objects or one-case-per-row CSV files."""
    path = Path(path)
    if path.suffix.casefold() == ".json":
        return load_json(path)
    if path.suffix.casefold() != ".csv":
        raise ValueError("Benchmark input phải là file .json hoặc .csv.")
    list_fields = {"page_hint", "gold_answer_spans", "expected_document_keys", "reference_facts"}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        cases = []
        for row in csv.DictReader(handle):
            for field in list_fields:
                if row.get(field):
                    try:
                        row[field] = json.loads(row[field])
                    except json.JSONDecodeError as exc:
                        if field != "gold_answer_spans":
                            raise ValueError(f"CSV {path.name}: {field} phải là JSON array.") from exc
            if "answerable" in row:
                row["answerable"] = str(row["answerable"]).strip().casefold() in {"true", "1", "yes"}
            if row.get("page_hint_start") and row.get("page_hint_end"):
                row["page_hint"] = [int(row["page_hint_start"]), int(row["page_hint_end"])]
            if isinstance(row.get("gold_answer_spans"), str) and row["gold_answer_spans"].strip():
                row["gold_answer_spans"] = [span.strip() for span in row["gold_answer_spans"].split("||") if span.strip()]
            cases.append(row)
    return {"meta": {"source_format": "csv"}, "cases": cases}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for field, value in row.items()})


def summary_chart(path: Path, title: str, metrics: dict[str, float], *, seconds: set[str] | None = None) -> None:
    """Write one compact chart; quality scores stay on 0..1, latency keeps seconds."""
    seconds = seconds or set()
    quality = {key: value for key, value in metrics.items() if key not in seconds}
    latency = {key: value for key, value in metrics.items() if key in seconds}
    columns = 2 if latency else 1
    figure, axes = plt.subplots(1, columns, figsize=(11, max(3.8, len(metrics) * 0.55)))
    axes = [axes] if columns == 1 else list(axes)
    for axis, values, x_max, suffix in ((axes[0], quality, 1.0, ""), *([(axes[1], latency, max(latency.values(), default=1.0) * 1.2, " s")] if latency else [])):
        labels, scores = list(values), list(values.values())
        bars = axis.barh(labels, scores, color="#2563eb")
        axis.set_xlim(0, max(1.0, x_max))
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.2)
        axis.set_axisbelow(True)
        for bar, score in zip(bars, scores):
            axis.text(bar.get_width() + x_max * 0.02, bar.get_y() + bar.get_height() / 2, f"{score:.3f}{suffix}", va="center", fontsize=9)
    figure.suptitle(title, fontweight="bold")
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def citation_precision(citations: list[dict[str, Any]], expected_document_keys: list[str], *, answerable: bool) -> float:
    if not citations:
        return 0.0 if answerable else 1.0
    expected = set(expected_document_keys)
    return sum(citation.get("document_key") in expected for citation in citations) / len(citations)


def no_answer_correct(payload: dict[str, Any]) -> bool:
    return payload.get("answer_status") == "insufficient_evidence"
