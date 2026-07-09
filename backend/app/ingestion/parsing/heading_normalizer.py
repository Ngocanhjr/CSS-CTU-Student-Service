import re

# --- Số La Mã ---
PATTERN_ROMAN_UPPER = re.compile(r"^[IVXLCDM]+\.\s+.+$")   # "IV. Giới thiệu"
PATTERN_ROMAN_LOWER = re.compile(r"^[ivxlcdm]+\.\s+.+$")   # "iv. giới thiệu"

# --- Số thường ---
PATTERN_NUMBER = re.compile(r"^\d+\.\s+.+$")               # "1. Mục tiêu"

# --- Chữ cái ---
PATTERN_LETTER_UPPER = re.compile(r"^[A-ZĐ][/\.]\s*.+$")   # "A. Phạm vi"
PATTERN_LETTER_LOWER = re.compile(r"^[a-zđ][/\.]\s*.+$")   # "a. phạm vi"

# Thứ tự trong danh sách RẤT quan trọng:
# ví dụ "i." vừa khớp La Mã thường vừa khớp chữ cái thường,
# nên phải xếp La Mã thường lên TRƯỚC chữ cái thường.
HEADING_RULES = [
    (PATTERN_ROMAN_UPPER, "###"),
    (PATTERN_NUMBER, "####"),
    (PATTERN_LETTER_UPPER, "#####"),
    (PATTERN_ROMAN_LOWER, "######"),
    (PATTERN_LETTER_LOWER, "######"),  # markdown chỉ hỗ trợ tối đa h6
]

MAX_HEADING_LENGTH = 160


def is_probable_heading_line(line: str) -> bool:
    """Kiểm tra xem dòng này có khả năng là 1 đề mục hay không."""
    stripped = line.strip()

    if not stripped:
        return False
    if stripped.startswith(("#", "-", "|", "<!--")):
        return False
    if len(stripped) > MAX_HEADING_LENGTH:
        return False

    return True


def detect_heading_prefix(stripped_line: str) -> str | None:
    """Trả về ký hiệu markdown (###, ####, #####) nếu dòng khớp 1 trong các mẫu.
    Nếu không khớp mẫu nào, trả về None."""
    for pattern, prefix in HEADING_RULES:
        if pattern.match(stripped_line):
            return prefix
    return None


def normalize_structural_headings(body: str) -> str:
    """Duyệt qua từng dòng văn bản, tự động thêm '#' cho các dòng
    được nhận diện là đề mục (số La Mã, số thường, chữ cái)."""
    lines = body.splitlines()
    normalized_lines: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Nếu gặp dấu ``` thì đổi trạng thái đang/không đang ở trong code block
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            normalized_lines.append(line)
            continue

        # Không xử lý các dòng nằm trong code block hoặc không giống đề mục
        if in_code_block or not is_probable_heading_line(line):
            normalized_lines.append(line)
            continue

        # Thử tìm xem dòng này thuộc loại đề mục nào
        heading_prefix = detect_heading_prefix(stripped)

        if heading_prefix:
            normalized_lines.append(f"{heading_prefix} {stripped}")
        else:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)