# 18. Part K - Huong Dan RAG Answer Chain Bang LangChain

**Last Updated:** 2026-06-27

File nay bat dau sau guide 16.

Guide 16 chi lam retrieval:

```text
query -> retriever -> hydrate PostgreSQL -> RetrievalResult co citation
```

Guide 18 moi lam answer chain:

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

## 1. Vi Sao Khong Dung Chain Thang Cho Production

LangChain example don gian:

```python
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

Dung de demo nhanh, nhung chua du cho project nay.

Ly do:

```text
retriever tra ve LangChain Documents tu Qdrant payload.
Qdrant khong phai source of truth.
Content/citation cuoi cung phai hydrate tu PostgreSQL.
Greeting/smalltalk nhu "hi" khong can retrieval.
Query mo ho nhu "dieu kien la gi" phai clarification truoc.
Citation phai validate truoc khi tra cho user.
```

Vi vay production chain khong dua raw Qdrant retriever thang vao prompt.

---

## 2. Chain Dung Cho Project

Flow nen dung:

```text
input question
  -> is_greeting_or_smalltalk()
  -> complete_or_clarify_query()
  -> Retriever.search()
  -> list[RetrievalResult]
  -> build_context_block()
  -> prompt
  -> llm
  -> StrOutputParser()
  -> validate_answer_citations()
```

Tach file de xuat:

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/app/llm/prompts.py
chatbot/backend/app/llm/rag_chain.py
chatbot/backend/app/llm/citation_validator.py
chatbot/backend/test/llm/test_rag_chain.py
```

---

## 3. Context Block Co Citation

Input la `list[RetrievalResult]` tu guide 16.

Function:

```python
def build_context_block(results: list[RetrievalResult]) -> str:
    ...
```

Format de xuat:

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

## 4. Prompt De Xuat

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
from app.retrieval.retriever import Retriever, RetrievalContext, RetrievalResult


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
async def answer_question(
    *,
    session,
    retriever: Retriever,
    llm,
    question: str,
    context: RetrievalContext | None = None,
    top_k: int = 5,
) -> RagAnswer:
    # Production nen goi complete_or_clarify_query() truoc do.
    # Neu la greeting/smalltalk hoac query can clarification, tra response truc tiep
    # va khong goi retriever/LLM.
    results = await retriever.search(
        session,
        query=question,
        top_k=top_k,
        context=context,
    )

    if not results:
        return RagAnswer(
            answer="Tôi chưa tìm thấy thông tin phù hợp trong tài liệu hiện có.",
            citations=[],
            retrieval_results=[],
        )

    context_block = build_context_block(results)
    chain = RAG_ANSWER_PROMPT | llm | StrOutputParser()
    answer = await chain.ainvoke(
        {
            "question": question,
            "context": context_block,
        }
    )

    citations = [result.citation for result in results]
    return RagAnswer(
        answer=answer,
        citations=citations,
        retrieval_results=results,
    )
```

Luu y:

```text
Skeleton tren chua validate citation trong text answer.
Greeting/smalltalk va clarification nen xu ly truoc khi goi retriever de tranh search Qdrant voi query nhu "hi".
Buoc production tiep theo phai them citation_validator.py.
```

---

## 6. Demo Chain Don Gian Chi De Hoc LangChain

Neu chi muon hoc cach pipe cua LangChain, co the viet demo:

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

Neu `context` da la string co dinh, vi du `context_str` duoc build tu retrieval results, khong duoc truyen thang string vao dict pipe:

```python
# Sai: context_str la str, khong phai Runnable/callable.
rag_chain = (
    {"context": context_str, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

Dung:

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

Neu khong boc `context_str`, LangChain se bao loi:

```text
TypeError: Expected a Runnable, callable or dict. Instead got an unsupported type: <class 'str'>
```

Nhung demo nay:

```text
Khong hydrate PostgreSQL.
Khong query clarification.
Khong validate citation.
Khong dam bao source of truth.
```

Chi dung de hoc LangChain pipe, khong dung lam production RAG endpoint.

---

## 7. Checklist

- [ ] Guide 16 retrieval tra `RetrievalResult` co content/citation.
- [ ] Query mo ho duoc clarification truoc retrieval.
- [ ] `build_context_block()` tao context co SOURCE/citation.
- [ ] Prompt yeu cau tra loi dua tren source.
- [ ] Chain dung `RAG_ANSWER_PROMPT | llm | StrOutputParser()`.
- [ ] Khong dua raw Qdrant retriever thang vao prompt production.
- [ ] Co citation list trong response.
- [ ] Them `citation_validator.py` truoc khi public endpoint cho user.
