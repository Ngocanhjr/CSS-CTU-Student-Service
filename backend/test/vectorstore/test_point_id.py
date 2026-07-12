from app.vectorstore.repository import make_point_id


def test_make_point_id_is_deterministic_per_version_and_chunk() -> None:
    assert make_point_id("doc-v1", "doc::c::0001") == make_point_id(
        "doc-v1", "doc::c::0001"
    )
    assert make_point_id("doc-v1", "doc::c::0001") != make_point_id(
        "doc-v2", "doc::c::0001"
    )
