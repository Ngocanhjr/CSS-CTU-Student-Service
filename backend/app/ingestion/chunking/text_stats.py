# Đếm số đơn vị hoặc độ dài nội dung để phục vụ việc chia chunk.

def count_units(text: str) -> int:
    return len(text.split())