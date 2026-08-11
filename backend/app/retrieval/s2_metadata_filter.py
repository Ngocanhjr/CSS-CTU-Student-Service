# tách các điều kiện mà user nêu rõ, ví dụ document_key, version_key, hoặc loại/đơn vị nếu có;
# mục đích là thu hẹp đúng phạm vi khi user hỏi một tài liệu cụ thể;
# không tự đoán bừa metadata; nếu user không nêu rõ thì search toàn bộ kho tài liệu hợp lệ.

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class QueryMetadataFilter:
    department: str | None = None
    document_type: str | None = None
    domain: str | None = None
    document_key: str | None = None
    version_key: str | None = None


DEPARTMENT_ALIASES = {
    "PDT": ("pđt", "pdt", "phòng đào tạo"),
    "PCTSV": ("pctsv", "phòng công tác sinh viên"),
    "PKHTC": ("pkhtc", "phòng kế hoạch tài chính"),
    "PTV": ("ptv", "phòng tài vụ"),
}

DOCUMENT_TYPE_ALIASES = {
    "noi_quy": ("nội quy",),
    "quy_trinh": ("quy trình",),
    "bieu_mau": ("biểu mẫu", "mẫu đơn", "đơn mẫu"),
    "hoi_dap": ("hỏi đáp", "câu hỏi thường gặp", "faq"),
    "ke_hoach": ("kế hoạch",),
    "thong_bao": ("thông báo",),
    "bao_cao": ("báo cáo",),
    "huong_dan": ("hướng dẫn",),
    "quyet_dinh": ("quyết định",),
    "cong_van": ("công văn",),
    "thong_tu": ("thông tư",),
    "nghi_quyet": ("nghị quyết",),
    "vh_xh": ("văn hóa xã hội","bạo lực học đường","tệ nạn xã hội","an toàn trường học",)
}

DOMAIN_ALIASES = {
    "hoc_vu": ("học vụ", "đăng ký học phần", "lịch thi"),
    "hoc_phi": ("học phí", "miễn giảm học phí"),
    "dao_tao": ("chương trình đào tạo", "quy chế đào tạo"),
    "nghien_cuu_khoa_hoc": ("nghiên cứu khoa học", "nckh"),
    "hop_tac_quoc_te": ("hợp tác quốc tế", "trao đổi quốc tế", "du học"),
    "hoc_bong": ("học bổng",),
    "sinh_vien": ("ký túc xá", "ktx", "công tác sinh viên", "rèn luyện"),
}

# Kiểm tra có chứa alias không
def _contains_alias(query: str, aliases: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", query, flags=re.IGNORECASE)
        for alias in aliases
    )

# Kiểm tra câu hỏi thuộc metadata nào
def _match_alias(query: str, aliases: dict[str, tuple[str, ...]]) -> str | None:
    matches = [
        (len(alias), value)
        for value, values in aliases.items()
        for alias in values
        if _contains_alias(query, (alias,))
    ]
    return max(matches, default=(0, None))[1]


def extract_metadata_filter(
    query: str,
    *,
    document_key: str | None = None,
    version_key: str | None = None,
) -> QueryMetadataFilter:
    """Return only metadata that the query explicitly identifies.

    Context-provided document/version keys take precedence over values inferred
    from a query, and no metadata is guessed when no alias is present.
    """
    return QueryMetadataFilter(
        department=_match_alias(query, DEPARTMENT_ALIASES),
        document_type=_match_alias(query, DOCUMENT_TYPE_ALIASES),
        domain=_match_alias(query, DOMAIN_ALIASES),
        document_key=document_key,
        version_key=version_key,
    )
