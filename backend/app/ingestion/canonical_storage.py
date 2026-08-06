from __future__ import annotations

import os
from datetime import timedelta

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


MAX_MARKDOWN_BYTES = 20 * 1024 * 1024
MAX_SOURCE_BYTES = 100 * 1024 * 1024

DEFAULT_PREVIEW_EXPIRES_MINUTES = 5


def make_canonical_relative_path(
    version_key: str,
    department_code: str,
) -> str:
    return (
        f"canonical/md/"
        f"{department_code.lower()}/"
        f"{version_key}.md"
    )


def make_source_relative_path(
    version_key: str,
    department_code: str,
    extension: str,
) -> str:
    source_type = extension.lstrip(".").lower()

    normalized_extension = (
        ".md"
        if source_type == "markdown"
        else f".{source_type}"
    )

    if source_type == "markdown":
        source_type = "md"

    return (
        f"sources/{source_type}/"
        f"{department_code.lower()}/"
        f"{version_key}{normalized_extension}"
    )


def _bucket() -> str:
    bucket = os.getenv("R2_BUCKET")

    if not bucket:
        raise RuntimeError("R2_BUCKET is not set")

    return bucket


def _client():
    endpoint_url = os.getenv("R2_ENDPOINT_URL")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not endpoint_url or not access_key or not secret_key:
        raise RuntimeError(
            "R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, "
            "and R2_SECRET_ACCESS_KEY are required"
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.getenv("R2_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def _object_exists(key: str) -> bool:
    try:
        _client().head_object(
            Bucket=_bucket(),
            Key=key,
        )
        return True

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            return False

        raise


def _put_object(
    key: str,
    content: bytes,
    content_type: str,
) -> None:
    _client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=content,
        ContentType=content_type,
    )


def create_canonical_markdown(
    relative_path: str,
    content: str,
) -> None:
    if _object_exists(relative_path):
        raise FileExistsError(
            "Canonical Markdown đã tồn tại trên R2"
        )

    _put_object(
        relative_path,
        content.encode("utf-8"),
        "text/markdown; charset=utf-8",
    )


def read_canonical_markdown(
    relative_path: str,
) -> str:
    try:
        response = _client().get_object(
            Bucket=_bucket(),
            Key=relative_path,
        )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            raise FileNotFoundError(
                relative_path
            ) from exc

        raise

    return response["Body"].read().decode("utf-8")


def replace_canonical_markdown(
    relative_path: str,
    content: str,
) -> None:
    _put_object(
        relative_path,
        content.encode("utf-8"),
        "text/markdown; charset=utf-8",
    )


def delete_canonical_markdown(
    relative_path: str,
) -> None:
    _client().delete_object(
        Bucket=_bucket(),
        Key=relative_path,
    )


def create_source_file(
    relative_path: str,
    content: bytes,
    content_type: str,
) -> None:
    if _object_exists(relative_path):
        raise FileExistsError(
            "File nguồn đã tồn tại trên R2"
        )

    _put_object(
        relative_path,
        content,
        content_type,
    )


def delete_source_file(
    relative_path: str,
) -> None:
    _client().delete_object(
        Bucket=_bucket(),
        Key=relative_path,
    )


def get_object_preview_url(
    relative_path: str,
    *,
    expires_minutes: int = DEFAULT_PREVIEW_EXPIRES_MINUTES,
) -> str:
    """Tạo URL tạm thời để xem object trên R2."""

    if not relative_path:
        raise ValueError("Đường dẫn object R2 không được để trống")

    if expires_minutes < 1:
        raise ValueError(
            "Thời gian hết hạn phải lớn hơn hoặc bằng 1 phút"
        )

    if not _object_exists(relative_path):
        raise FileNotFoundError(relative_path)

    return _client().generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": _bucket(),
            "Key": relative_path,
            "ResponseContentDisposition": "inline",
        },
        ExpiresIn=int(
            timedelta(
                minutes=expires_minutes
            ).total_seconds()
        ),
    )


def get_source_preview_url(
    relative_path: str,
    *,
    expires_minutes: int = DEFAULT_PREVIEW_EXPIRES_MINUTES,
) -> str:
    """Tạo URL xem PDF hoặc file nguồn gốc."""

    return get_object_preview_url(
        relative_path,
        expires_minutes=expires_minutes,
    )


def get_canonical_markdown_preview_url(
    relative_path: str,
    *,
    expires_minutes: int = DEFAULT_PREVIEW_EXPIRES_MINUTES,
) -> str:
    """Tạo URL xem file Markdown OCR."""

    return get_object_preview_url(
        relative_path,
        expires_minutes=expires_minutes,
    )