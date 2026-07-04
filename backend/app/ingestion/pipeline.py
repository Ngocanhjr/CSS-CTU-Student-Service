from __future__ import annotations

from pathlib import Path
from pprint import pprint

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.llm.prompts import RAG_ANSWER_PROMPT
    
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.embedding.embedder import embed_chunks_with_cache, get_embedding
from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import (
    RetrievalFilter,
    COLLECTION_NAME,
    search_points,
)


def is_greeting_or_smalltalk(query: str) -> bool:
    normalized = query.strip().lower()
    return normalized in {"hi", "hello", "chào", "xin chào", "alo"}


def search_document(
    query: str,
    *,
    top_k: int = 5,
    filter: RetrievalFilter | None = None,
) -> list[dict]:
    """
    Search for relevant chunks in the indexed documents based on a query.

    Args:
        query (str): The search query.
        top_k (int, optional): The number of top results to return. Defaults to 5.
        filter (RetrievalFilter | None, optional): Optional filter for the search. Defaults to None.

    Returns:
        list[dict]: A list of dictionaries containing the search results.
    """
    embedding = get_embedding()
    query_vector = embedding.embed_query(query)
    client = get_qdrant_client()
    results = search_points(
        client,
        query_vector=query_vector,
        top_k=top_k,
        filters=filter
    )
    
    return [
        {
            "score": item.score,
            "chunk_key": item.payload.get("chunk_key"),
            "parent_chunk_key": item.payload.get("parent_chunk_key"),
            "heading_path": item.payload.get("heading_path"),
            "page_start": item.payload.get("page_start"),
            "page_end": item.payload.get("page_end"),
            "content_preview": (item.payload.get("content") or "")[:300],
        }
        for item in results
    ]

def main() -> None:
    import json

    llm = ChatNVIDIA(
        model="qwen/qwen3-next-80b-a3b-instruct",
        temperature=0.1,
        top_p=0.7, #Limit scope of token most likely ones
        max_completion_tokens=1024,
    )

    prompt = RAG_ANSWER_PROMPT
    top_k = 5

    while True:
        question = input("Question (nhập 0 để dừng): ").strip()

        if question == "0":
            print("Đã dừng chương trình.")
            return

        if not question:
            print("Vui lòng nhập câu hỏi hoặc nhập 0 để dừng.")
            continue

        if is_greeting_or_smalltalk(question):
            answer = (
                "Chào bạn, mình là trợ lý hỗ trợ tra cứu thông tin sinh viên CTU. "
                "Bạn muốn hỏi về thủ tục, quy định, học bổng, ký túc xá hay nội dung nào?"
            )
            print("CTU student assistance:", answer)

            with open("answer.txt", "w", encoding="utf-8") as file:
                file.write(answer)

            continue

        results = search_document(question, top_k=top_k)

        context_str = "\n\n".join(
            f"[{r['chunk_key']}] {r['content_preview']}"
            for r in results
        )
        
        # pprint(
        #     json.dumps(
        #         {
        #             "collection": COLLECTION_NAME,
        #             "query": question,
        #             "context": context_str,
        #             "results": results,
        #         },
        #         ensure_ascii=False,
        #         indent=2,
        #     )
        # )
        
        print("----------------HI I'M ASSISTANT AT CTU----------------")

        #Represent RAG pipe
        rag_chain = (
            {
                "context": RunnableLambda(lambda _: context_str),
                "question": RunnablePassthrough(),
            }
            | prompt
            | llm 
            | StrOutputParser()
        )

        answer = rag_chain.invoke(question)

        print("CTU student assistance:", answer)

        with open("answer.txt", "w", encoding="utf-8") as file:
            file.write(answer)

        print("Đã lưu câu trả lời vào answer.txt")


if __name__ == "__main__":
    main()
