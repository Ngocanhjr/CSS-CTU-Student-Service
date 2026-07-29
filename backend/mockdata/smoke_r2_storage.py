from uuid import uuid4

from dotenv import load_dotenv

from app.ingestion.canonical_storage import (
    create_canonical_markdown,
    delete_canonical_markdown,
    make_canonical_relative_path,
    read_canonical_markdown,
    replace_canonical_markdown,
)

load_dotenv()

version_key = f"r2-smoke-{uuid4().hex}"
object_key = make_canonical_relative_path(
    version_key=version_key,
    department_code="SMOKE",
)

first_content = "---\ntitle: smoke test\n---\n\nBản đầu tiên.\n"
updated_content = "---\ntitle: smoke test\n---\n\nBản đã thay thế.\n"

try:
    create_canonical_markdown(object_key, first_content)
    assert read_canonical_markdown(object_key) == first_content

    replace_canonical_markdown(object_key, updated_content)
    assert read_canonical_markdown(object_key) == updated_content

    print(f"PASS: create/read/replace — {object_key}")
finally:
    delete_canonical_markdown(object_key)

try:
    read_canonical_markdown(object_key)
    raise AssertionError("Object vẫn còn sau delete")
except FileNotFoundError:
    print("PASS: delete")