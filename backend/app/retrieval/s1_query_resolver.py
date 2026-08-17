# Xử lý câu hỏi nhận từ user
# Nếu là câu hỏi ngoài lề, thì xử lý ntn
# Nếu là câu hỏi nghiệp vụ thì sẽ gọi retrieval engine
# chuẩn hoá chữ thường/khoảng trắng/dấu câu;
# mở rộng từ viết tắt;
# nhận diện chào hỏi hoặc câu hỏi quá mơ hồ để trả lời/làm rõ ngay, không cần search.   

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
    "nvqs": "nghĩa vụ quân sự"
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

# Những câu này chỉ có nghĩa khi đặt trong mạch hội thoại trước đó. Không được
# đưa nguyên văn vào retrieval toàn kho vì các từ như "tiếp" hay "còn" không
# mô tả nghiệp vụ sinh viên nào.
CONTINUATION_QUERIES = {
    "tiếp",
    "tiếp đi",
    "nói tiếp",
    "trả lời tiếp",
    "còn gì",
    "còn gì không",
    "còn nữa không",
    "còn không",
    "có gì thêm không",
}

FOLLOW_UP_CLARIFICATION = (
    "Bạn muốn hỏi tiếp về nội dung nào? Vui lòng nêu lại chủ đề hoặc câu hỏi trước đó."
)

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
    is_continuation = expanded_query in CONTINUATION_QUERIES
    is_ambiguous = expanded_query in UNDERSPECIFIED_QUERIES

    has_context = bool(
        context.current_document_key
        or context.current_version_key
        or context.recent_topic
    )

    # Follow-up không có chủ đề là vô nghĩa. Dừng ở đây để tránh retrieval
    # toàn kho và một câu trả lời lạc đề.
    if is_continuation and not has_context:
        return QueryDecision(
            should_search=False,
            query=expanded_query,
            clarification_question=FOLLOW_UP_CLARIFICATION,
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

    # Với follow-up, chủ đề trước là truy vấn có ngữ nghĩa duy nhất. Document
    # và version từ context bên dưới tiếp tục giới hạn phạm vi retrieval.
    if is_continuation:
        resolved_query = context.recent_topic or expanded_query
    else:
        resolved_query = expanded_query
    
    # Nếu câu hỏi chưa rõ ràng nhưng có ngữ cảnh thì bổ sung ngữ cảnh vào câu hỏi.
    # Follow-up đã dùng recent_topic làm toàn bộ truy vấn ở trên.
    if is_ambiguous and not is_continuation and context.recent_topic:
        resolved_query = f"{expanded_query} cho {context.recent_topic}"

    # Chỉ khóa vào tài liệu/version trước đó khi câu hỏi thực sự cần ngữ cảnh
    # hội thoại. Một câu hỏi mới, đầy đủ ý nghĩa phải tìm trên toàn bộ kho;
    # nếu luôn mang document_key/version_key cũ sang thì chatbot không thể
    # chuyển sang một chủ đề nằm ở tài liệu khác.
    should_scope_to_context = is_continuation or is_ambiguous

    return QueryDecision(
        should_search=True, #→ gọi Qdrant + PostgreSQL retrieval
        query=resolved_query, #gọi retrieval engine để tìm kiếm câu trả lời
        document_key=(
            context.current_document_key
            if should_scope_to_context
            else None
        ),
        version_key=(
            context.current_version_key
            if should_scope_to_context
            else None
        ),
        is_follow_up=is_continuation,
    )
