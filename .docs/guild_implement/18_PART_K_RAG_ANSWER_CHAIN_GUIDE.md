# 18. Part K - Hướng Dẫn RAG Answer Chain Bằng LangChain

**Last Updated:** 2026-07-10

File này bắt đầu sau guide 16.

Guide 16 làm retrieval đã resolve query, hydrate canonical content và structural expansion:

```text
resolved query
-> vector retrieval
-> hydrate PostgreSQL
-> parent/child/sibling/split expansion
-> deduplicate/source-order/context budget
-> RetrievalResult co citation
```

Guide 18 mới làm answer chain:

```text
question
  -> greeting/smalltalk guard
  -> query clarification/context completion
  -> retrieval
  -> hydrate PostgreSQL
  -> build cited context
  -> prompt
  -> LLM
  -> parse answer
  -> citation validation
```

---

## 1. Vì Sao Không Dùng Chain Thẳng Cho Production

LangChain example đơn giản:

```python
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

Dùng để demo nhanh, nhưng chưa đủ cho project này.

Lý do:

```text
retriever tra ve LangChain Documents tu Qdrant payload.
Qdrant khong phai source of truth.
Content/citation cuoi cung phai hydrate tu PostgreSQL.
Greeting/smalltalk nhu "hi" khong can retrieval.
Query mo ho nhu "dieu kien la gi" phai clarification truoc.
Citation phai validate truoc khi tra cho user.
```

Vì vậy production chain không đưa raw Qdrant retriever thẳng vào prompt.

---

## 2. Chain Dùng Cho Project

Flow nên dùng:

```text
input question
  -> is_greeting_or_smalltalk()
  -> complete_or_clarify_query()
  -> Retriever.search_resolved_query()
  -> hydrated + expanded list[RetrievalResult]
  -> build_context_block()
  -> prompt
  -> llm
  -> StrOutputParser()
  -> validate_answer_citations()
```

Tách file đề xuất:

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/app/llm/prompts.py
chatbot/backend/app/llm/rag_chain.py
chatbot/backend/app/llm/citation_validator.py
chatbot/backend/test/llm/test_rag_chain.py
```

---

## 3. Context Block Có Citation

Input là `list[RetrievalResult]` từ guide 16.

Function:

```python
def build_context_block(results: list[RetrievalResult]) -> str:
    ...
```

Format đề xuất:

```text
[SOURCE 1]
Title: <title>
Citation: <source_file>, trang <page_start>-<page_end>
Chunk key: <chunk_key>
Content:
<content>

[SOURCE 2]
...
```

Rule:

```text
LLM chi duoc tra loi dua tren SOURCE.
Moi claim quan trong phai dan citation.
Khong co source phu hop thi noi khong tim thay trong tai lieu hien co.
```

---

## 4. Prompt Đề Xuất

File:

```text
chatbot/backend/app/llm/prompts.py
```

```python
from langchain_core.prompts import ChatPromptTemplate


RAG_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "Ban la tro ly tu van dich vu sinh vien CTU. "
                "Chi tra loi dua tren ngu canh duoc cung cap. "
                "Neu ngu canh khong du, hay noi khong tim thay thong tin trong tai lieu hien co. "
                "Moi thong tin thu tuc, dieu kien, ho so, thoi han, noi nop phai co citation."
            ),
        ),
        (
            "human",
            "Cau hoi:\n{question}\n\nNgu canh:\n{context}",
        ),
    ]
)
```

---

## 5. RAG Chain Skeleton

File:

```text
chatbot/backend/app/llm/rag_chain.py
```

Skeleton production-friendly:

```python
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser

from app.llm.prompts import RAG_ANSWER_PROMPT
from app.retrieval.retriever import (
    Retriever,
    RetrievalContext,
    RetrievalResult,
    complete_or_clarify_query,
)


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[str]
    retrieval_results: list[RetrievalResult]
    clarification_question: str | None = None


def build_context_block(results: list[RetrievalResult]) -> str:
    blocks: list[str] = []
    for index, result in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"Title: {result.title}",
                    f"Citation: {result.citation}",
                    f"Chunk key: {result.chunk_key}",
                    "Content:",
                    result.content,
                ]
            )
        )
    return "\n\n".join(blocks)
```

Answer function:

```python
DEFAULT_TOP_K = 5


async def answer_question(
    *,
    session,
    retriever: Retriever,
    llm,
    question: str,
    context: RetrievalContext | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> RagAnswer:
    decision = complete_or_clarify_query(question, context=context)

    if not decision.should_search:
        response = decision.clarification_question or "Vui lòng nhập câu hỏi cụ thể hơn."
        return RagAnswer(
            answer=response,
            citations=[],
            retrieval_results=[],
            clarification_question=decision.clarification_question,
        )

    results = await retriever.search_resolved_query(
        session,
        query=decision.query,
        document_key=decision.document_key,
        version_key=decision.version_key,
        top_k=top_k,
    )

    if not results:
        return RagAnswer(
            answer="Tôi chưa tìm thấy thông tin phù hợp trong tài liệu hiện có.",
            citations=[],
            retrieval_results=[],
            clarification_question=None,
        )

    context_block = build_context_block(results)
    chain = RAG_ANSWER_PROMPT | llm | StrOutputParser()
    answer = await chain.ainvoke(
        {
            "question": decision.query,
            "context": context_block,
        }
    )

    citations = list(dict.fromkeys(result.citation for result in results))
    return RagAnswer(
        answer=answer,
        citations=citations,
        retrieval_results=results,
        clarification_question=None,
    )
```

`top_k` mặc định lấy từ runtime settings ở caller (`retrieval.top_k = 5`). Không dùng fallback kiểu `settings.retrieval.top_k or 5`.

Lưu ý:

```text
- Greeting/smalltalk và clarification được xử lý trước Retriever/Qdrant/LLM.
- `results == []` sau `search_resolved_query()` chỉ còn nghĩa là no-result.
- Skeleton chưa validate citation xuất hiện trong text answer; cần citation_validator.py trước public endpoint.
```

---

## 6. Demo Chain Đơn Giản Chỉ Để Học LangChain

Nếu chỉ muốn học cách pipe của LangChain, có thể viết demo:

```python
while True:
    question = input("Question (nhập 0 để dừng): ").strip()
    if question == "0":
        print("Đã dừng chương trình.")
        return
    if not question:
        print("Vui lòng nhập câu hỏi hoặc nhập 0 để dừng.")
        continue

    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    answer = rag_chain.invoke(question)
    print(answer)
```

Nếu `context` đã là string cố định, ví dụ `context_str` được build từ retrieval results, không được truyền thẳng string vào dict pipe:

```python
# Sai: context_str la str, khong phai Runnable/callable.
rag_chain = (
    {"context": context_str, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

Đúng:

```python
from langchain_core.runnables import RunnableLambda, RunnablePassthrough


rag_chain = (
    {
        "context": RunnableLambda(lambda _: context_str),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)
```

Nếu không bọc `context_str`, LangChain sẽ báo lỗi:

```text
TypeError: Expected a Runnable, callable or dict. Instead got an unsupported type: <class 'str'>
```

Nhưng demo này:

```text
Khong hydrate PostgreSQL.
Khong query clarification.
Khong validate citation.
Khong dam bao source of truth.
```

Chỉ dùng để học LangChain pipe, không dùng làm production RAG endpoint.

---

## 6.1 Test Answer Chain Decision

```python
async def test_greeting_does_not_call_retriever_or_llm(...):
    answer = await answer_question(question="hi", ...)
    assert answer.clarification_question
    assert answer.retrieval_results == []
    # fake retriever/LLM assert not called


async def test_ambiguous_query_returns_clarification(...):
    answer = await answer_question(question="điều kiện là gì", ...)
    assert answer.clarification_question


async def test_no_result_is_not_clarification(...):
    answer = await answer_question(question="điều kiện xin giấy X", ...)
    assert answer.clarification_question is None
    assert "chưa tìm thấy" in answer.answer.lower()


async def test_context_filter_is_forwarded(...):
    context = RetrievalContext(current_document_key="xin-giay-khai-sinh")
    await answer_question(question="điều kiện là gì", context=context, ...)
    # fake retriever assert document_key == "xin-giay-khai-sinh"
```

---

## 7. Checklist

- [ ] Guide 16 retrieval trả `RetrievalResult` có content/citation.
- [ ] Greeting/smalltalk không gọi Qdrant hoặc LLM.
- [ ] Query mơ hồ được clarification trước retrieval.
- [ ] Clarification và no-result có response contract khác nhau.
- [ ] `current_document_key`/`current_version_key` được truyền xuống retrieval filter.
- [ ] `build_context_block()` tạo context có SOURCE/citation.
- [ ] Prompt yêu cầu trả lời dựa trên source.
- [ ] Chain dùng `RAG_ANSWER_PROMPT | llm | StrOutputParser()`.
- [ ] Không đưa raw Qdrant retriever thẳng vào prompt production.
- [ ] Có citation list trong response.
- [ ] Thêm `citation_validator.py` trước khi public endpoint cho user.
