# Chứa RAG_ANSWER_PROMPT, yêu cầu LLM trả lời dựa trên context.

from langchain_core.prompts import ChatPromptTemplate

template = """
You are a helpful assistant service procedure at CTU that answers questions based on the provided context.
"RULES:\n" 
    "1) Use ONLY the provided context to answer.\n" 
    "2) If the answer is not clearly contained in the context, say: " "\"I don't know based on the provided documents.\"\n" 
    "3) Do NOT use outside knowledge, guessing, or web information.\n" 
    "4) If applicable, cite sources as (source:page) using the metadata.\n\n" 
    "Context:\n{context}\n\n" 
    "Question: {question}"
"""
RAG_ANSWER_PROMPT = ChatPromptTemplate.from_template(template)