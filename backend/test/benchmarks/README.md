# CT239H benchmark runners

Put input JSON in `backend/test/file_test` (or pass `--input`). Start backend first for end-to-end benchmark.

```powershell
cd backend
.\.venv\Scripts\python.exe -m test.benchmarks.ct239h_retrieval_benchmark_30
.\.venv\Scripts\python.exe -m test.benchmarks.ct239h_end_to_end_10
```

Each command writes JSON plus PNG beside input file, therefore by default in `backend/test/file_test`. Optional: `--output-dir .\evaluation-output`.
It also writes a flat CSV result file for spreadsheet analysis.

`--input` accepts JSON or CSV. CSV has one case per row. Encode array fields as a JSON array inside its cell, for example `gold_answer_spans` as `"[\"Đoạn evidence đầy đủ.\"]"`, `page_hint` as `"[1, 1]"`, and `answerable` as `true` or `false`.

`ct239h_retrieval_benchmark_30` needs PostgreSQL, Qdrant, embedding credentials, and `JINA_API_KEY` for `hybrid_rrf_jina`. Each `gold_answer_spans` value is resolved once into an audited child `chunk_key`; it evaluates direct hits before structural expansion. `ct239h_end_to_end_10` needs running backend plus LLM credentials used by Ragas.
