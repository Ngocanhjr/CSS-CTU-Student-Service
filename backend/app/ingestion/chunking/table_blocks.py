def split_large_table_block(
    content: str,
    *,
    max_size: int,
) -> list[str]:
    table = content.strip()

    if not table:
        raise ValueError("Table content is empty")

    if max_size <= 0:
        raise ValueError("max_size must be greater than zero")

    if len(table) <= max_size:
        return [table]

    lines = [
        line.strip()
        for line in table.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        raise ValueError("Markdown table requires a header and separator")

    header = lines[0]
    separator = lines[1]
    rows = lines[2:]

    if not rows:
        return [table]

    def render(selected_rows: list[str]) -> str:
        return "\n".join([header, separator, *selected_rows])

    parts: list[str] = []
    current_rows: list[str] = []

    for row in rows:
        candidate = render([*current_rows, row])

        if current_rows and len(candidate) > max_size:
            parts.append(render(current_rows))
            current_rows = [row]
            continue

        current_rows.append(row)

    if current_rows:
        parts.append(render(current_rows))

    # ponytail: một row quá dài vẫn giữ nguyên; chỉ split cell khi dữ liệu thật chứng minh cần thiết.
    return parts
