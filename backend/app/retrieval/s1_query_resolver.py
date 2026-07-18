# Xử lý câu hỏi nhận từ user
# Nếu là câu hỏi ngoài lề, thì xử lý ntn
# Nếu là câu hỏi nghiệp vụ thì sẽ gọi retrieval engine

from __future__ import annotations
from app.retrieval.models import QueryDecision, RetrievalContext

import re #thư viện Regular Expression (Regex)


ABBREVIATIONS = {
    "bhyt": "bảo hiểm y tế",
    "ctsv": "công tác sinh viên",
    "ctu": "đại học cần thơ",
    "ktx": "ký túc xá",
    "pctsv": "phòng công tác sinh viên",
    "pdt": "phòng đào tạo",
}


GREETINGS = {
    "hi",
    "hello",
    "chào",
    "xin chào",
    "alo",
}

UNDERSPECIFIED_QUERIES = {
    "điều kiện là gì",
    "hồ sơ gồm gì",
    "nộp ở đâu",
    "cần gì",
    "cần giấy gì",
}

# Chuẩn hóa câu hỏi 
def normalize_query(query: str) -> str:
    #viết thường
    query = query.lower()
    
    #bỏ khoảng trắng đầu/cuối
    query = query.strip()
    
    #thay nhiều khoảng trắng thành 1
    query = re.sub(r"\s+",  " ", query)
    
    #Bỏ dấu câu cuối câu
    query = re.sub(r"[?!.,;:]+$", "", query)    
    
    return query

#Xử lý câu hỏi có từ viết tắt
def expand_abbreviation(query: str) -> str:
    """Replace supported standalone abbreviations with their full Vietnamese names."""
    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, sorted(ABBREVIATIONS, key=len, reverse=True))) + r")\b",
        flags=re.IGNORECASE,
    )
    return pattern.sub(lambda match: ABBREVIATIONS[match.group(0).lower()], query)


# Nếu câu hỏi là lời chào 
def is_greeting_or_smalltalk(query: str) -> bool:
    return normalize_query(query).lower() in GREETINGS


def complete_or_clarify_query(
    query: str,
    *,
    context: RetrievalContext | None = None,
) -> QueryDecision:
    normalized = normalize_query(query) #Chuẩn hóa câu hỏi

    # Nếu câu hỏi trống thì yêu cầu nhập lại
    if not normalized:
        return QueryDecision(
            should_search=False,
            query="",
            response_message="Vui lòng nhập câu hỏi.",
        )
        
    expanded_query = expand_abbreviation(normalized)

    # Nếu câu chào hỏi hoặc câu hỏi ngoài lề thì trả lời chào hỏi
    if is_greeting_or_smalltalk(expanded_query):
        return QueryDecision(
            should_search=False,
            query=expanded_query,
            response_message=(
                "Chào bạn, mình là trợ lý hỗ trợ tra cứu thông tin "
                "sinh viên CTU. Bạn muốn hỏi về nội dung nào?"
            ),
        )
    context = context or RetrievalContext()
    
    # Nếu câu hỏi là câu hỏi nghiệp vụ nhưng chưa rõ ràng thì yêu cầu người dùng nhập thêm thông tin
    is_ambiguous = expanded_query.lower() in UNDERSPECIFIED_QUERIES

    has_context = bool(
        context.current_document_key
        or context.current_version_key
        or context.recent_topic
    )

    # Nếu câu hỏi chưa rõ ràng và không có ngữ cảnh thì yêu cầu người dùng nhập thêm thông tin
    if is_ambiguous and not has_context:
        return QueryDecision(
            should_search=False,
            query=expanded_query,
            clarification_question=(
                "Bạn muốn hỏi điều kiện hoặc hồ sơ của thủ tục nào?"
            ),
        )

    resolved_query = expanded_query
    
    # Nếu câu hỏi chưa rõ ràng nhưng có ngữ cảnh thì bổ sung ngữ cảnh vào câu hỏi
    if is_ambiguous and context.recent_topic:
        resolved_query = f"{expanded_query} cho {context.recent_topic}"

    return QueryDecision(
        should_search=True, #→ gọi Qdrant + PostgreSQL retrieval
        query=resolved_query, #gọi retrieval engine để tìm kiếm câu trả lời
        document_key=context.current_document_key,
        version_key=context.current_version_key,
    )
