from __future__ import annotations

import structlog
import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger("s3_service")


def get_s3_client():
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **kwargs)


import pathlib

def _local_s3_fallback_upload(key: str, body: bytes) -> str:
    local_dir = pathlib.Path(__file__).parent.parent.parent / "local_storage" / "s3"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_file = local_dir / key.replace("/", "_")
    local_file.write_bytes(body)
    logger.warning("s3_fallback_upload_used", key=key, local_path=str(local_file))
    return key


def _local_s3_fallback_download(key: str) -> bytes:
    local_dir = pathlib.Path(__file__).parent.parent.parent / "local_storage" / "s3"
    local_file = local_dir / key.replace("/", "_")
    if local_file.exists():
        logger.info("s3_fallback_download_ok", key=key, local_path=str(local_file))
        return local_file.read_bytes()
    raise FileNotFoundError(f"Local S3 fallback file not found for key: {key}")


def ensure_bucket_exists() -> None:
    """Create the S3 bucket if it doesn't already exist (useful for LocalStack)."""
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception as exc:
        if settings.env == "local":
            logger.info("s3_bucket_check_failed_in_local_skipping", error=str(exc))
            return
        logger.info("creating_s3_bucket", bucket=settings.s3_bucket)
        try:
            client.create_bucket(
                Bucket=settings.s3_bucket,
                CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
            )
        except ClientError as e:
            logger.warning("bucket_creation_failed", error=str(e))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5), reraise=True)
def _try_upload_bytes_to_s3(key: str, body: bytes, content_type: str | None = None) -> str:
    client = get_s3_client()
    extra_args: dict = {}
    if content_type:
        extra_args["ContentType"] = content_type
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=body, **extra_args)
    return key


def upload_bytes_to_s3(key: str, body: bytes, content_type: str | None = None) -> str:
    try:
        res = _try_upload_bytes_to_s3(key, body, content_type)
        logger.info("s3_upload_ok", key=key, size=len(body))
        return res
    except Exception as exc:
        if settings.env == "local":
            logger.warning("s3_upload_failed_using_local_fallback", error=str(exc))
            return _local_s3_fallback_upload(key, body)
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5), reraise=True)
def _try_download_bytes_from_s3(key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def download_bytes_from_s3(key: str) -> bytes:
    try:
        data = _try_download_bytes_from_s3(key)
        logger.info("s3_download_ok", key=key, size=len(data))
        return data
    except Exception as exc:
        if settings.env == "local":
            logger.warning("s3_download_failed_using_local_fallback", error=str(exc))
            return _local_s3_fallback_download(key)
        raise


def _local_s3_fallback_delete(key: str) -> None:
    local_dir = pathlib.Path(__file__).parent.parent.parent / "local_storage" / "s3"
    local_file = local_dir / key.replace("/", "_")
    if local_file.exists():
        local_file.unlink()
        logger.info("s3_fallback_delete_ok", key=key, local_path=str(local_file))
    else:
        logger.warning("s3_fallback_delete_missing", key=key, local_path=str(local_file))


def delete_from_s3(key: str) -> None:
    try:
        client = get_s3_client()
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
        logger.info("s3_delete_ok", key=key)
    except Exception as exc:
        if settings.env == "local":
            logger.warning("s3_delete_failed_using_local_fallback", error=str(exc))
            _local_s3_fallback_delete(key)
            return
        raise
