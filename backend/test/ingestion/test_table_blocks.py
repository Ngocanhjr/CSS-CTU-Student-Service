from app.ingestion.chunking.table_blocks import split_large_table_block


QD3266_TABLE = """\
| Thời gian thiết kế của CTĐT | Thời gian học tập tối đa để SV hoàn thành CTĐT |
| --- | --- |
| 4 năm | 8 năm |
| 4,5 năm | 9 năm |
| 5 năm | 10 năm |
"""


def test_table_stays_whole_or_splits_between_rows_with_repeated_header():
    assert split_large_table_block(QD3266_TABLE, max_size=1200) == [
        QD3266_TABLE.strip()
    ]

    parts = split_large_table_block(QD3266_TABLE, max_size=130)

    assert len(parts) == 3
    assert all(
        part.startswith(
            "| Thời gian thiết kế của CTĐT | Thời gian học tập tối đa để SV hoàn thành CTĐT |\n"
            "| --- | --- |"
        )
        for part in parts
    )
    assert [part.splitlines()[-1] for part in parts] == [
        "| 4 năm | 8 năm |",
        "| 4,5 năm | 9 năm |",
        "| 5 năm | 10 năm |",
    ]
