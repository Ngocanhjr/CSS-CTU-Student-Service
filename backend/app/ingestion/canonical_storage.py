from pathlib import Path
from tempfile import NamedTemporaryFile


MAX_MARKDOWN_BYTES = 10 * 1024 * 1024

BACKEND_DIR = Path(__file__).resolve().parents[2]
CANONICAL_DIR = BACKEND_DIR / "storage" / "canonical"


def make_canonical_relative_path(version_key: str) -> str:
    return (
        Path("storage") / "canonical" / f"{version_key}.md"
    ).as_posix()


def _resolve_canonical_path(relative_path: str) -> Path:
    root = CANONICAL_DIR.resolve()
    target = (BACKEND_DIR / relative_path).resolve()

    if not target.is_relative_to(root):
        raise ValueError("Canonical Markdown path không hợp lệ")

    return target


def create_canonical_markdown(
    relative_path: str,
    content: str,
) -> None:
    path = _resolve_canonical_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as file:
        file.write(content)


def read_canonical_markdown(relative_path: str) -> str:
    path = _resolve_canonical_path(relative_path)
    return path.read_text(encoding="utf-8")


def replace_canonical_markdown(
    relative_path: str,
    content: str,
) -> None:
    path = _resolve_canonical_path(relative_path)
    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        temporary_path.replace(path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def delete_canonical_markdown(relative_path: str) -> None:
    _resolve_canonical_path(relative_path).unlink(missing_ok=True)