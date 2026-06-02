from __future__ import annotations

import json

import boto3
import structlog
from botocore.exceptions import ClientError

from app.core.config import settings

logger = structlog.get_logger("queue_service")

QUEUE_NAME = "document-jobs"


def get_sqs_client():
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sqs", **kwargs)


def ensure_queue_exists() -> str | None:
    """
    Ensure the SQS queue exists and return its queue URL.

    This is safe to call repeatedly:
    - if the queue exists, it returns the existing URL
    - if the queue does not exist, it creates it and returns the new URL
    """
    client = get_sqs_client()

    try:
        response = client.get_queue_url(QueueName=QUEUE_NAME)
        queue_url = response["QueueUrl"]
        logger.info("sqs_queue_found", queue_url=queue_url)
        return queue_url
    except ClientError:
        try:
            response = client.create_queue(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            logger.info("sqs_queue_created", queue_url=queue_url)
            return queue_url
        except ClientError as exc:
            logger.error("sqs_queue_creation_failed", error=str(exc))
            return None


import pathlib
import time

def _local_sqs_fallback_enqueue(document_id: int, tenant_id: str, s3_key: str) -> None:
    import threading
    from app.services.s3_service import download_bytes_from_s3
    from app.services.document_service import index_document_text
    from app.services.parser_service import extract_text_from_blob
    from app.db.session import SessionLocal
    from app.db.models import Document

    local_dir = pathlib.Path(__file__).parent.parent.parent / "local_storage" / "sqs"
    local_dir.mkdir(parents=True, exist_ok=True)
    job_file = local_dir / f"job_{document_id}_{int(time.time())}.json"
    job_file.write_text(json.dumps({
        "document_id": document_id,
        "tenant_id": tenant_id,
        "s3_key": s3_key,
    }))
    logger.warning("sqs_fallback_used", document_id=document_id, job_path=str(job_file))

    def _job():
        # Pause slightly to allow parent request transactions to commit
        time.sleep(0.5)
        db = SessionLocal()
        try:
            logger.info("local_inline_processing_started", document_id=document_id)
            blob = download_bytes_from_s3(s3_key)
            text = extract_text_from_blob(blob, s3_key)
            count = index_document_text(db, document_id=document_id, tenant_id=tenant_id, text=text)
            
            db.query(Document).filter(Document.id == document_id).update({"status": "indexed"})
            db.commit()
            logger.info("local_inline_processing_success", document_id=document_id, chunks=count)
        except Exception as e:
            logger.error("local_inline_processing_failed", document_id=document_id, error=str(e))
            db.rollback()
        finally:
            db.close()

    # Launch daemon background thread
    threading.Thread(target=_job, daemon=True).start()


def enqueue_document_job(document_id: int, tenant_id: str, s3_key: str) -> None:
    """
    Send a document processing job to SQS.
    """
    try:
        queue_url = ensure_queue_exists()
        if not queue_url:
            raise RuntimeError("SQS queue URL is empty or unavailable")

        client = get_sqs_client()
        body = json.dumps(
            {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "s3_key": s3_key,
            }
        )
        client.send_message(QueueUrl=queue_url, MessageBody=body)
        logger.info("sqs_enqueued", document_id=document_id, queue_url=queue_url)
    except Exception as exc:
        if settings.env == "local":
            logger.warning("sqs_enqueue_failed_using_local_fallback", error=str(exc))
            _local_sqs_fallback_enqueue(document_id, tenant_id, s3_key)
            return
        raise