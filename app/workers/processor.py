from __future__ import annotations

import json
import signal
import time

import boto3
import structlog
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.models import Document
from app.db.session import SessionLocal, init_db
from app.services.document_service import index_document_text
from app.services.queue_service import ensure_queue_exists
from app.services.s3_service import download_bytes_from_s3
from app.services.parser_service import extract_text_from_blob

logger = structlog.get_logger("worker")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("shutdown_signal_received", signal=signum)
    _shutdown = True


def process_message(db: Session, message_body: str) -> None:
    payload = json.loads(message_body)
    document_id = int(payload["document_id"])
    tenant_id = payload["tenant_id"]
    s3_key = payload["s3_key"]

    logger.info("processing_document", document_id=document_id, s3_key=s3_key)

    blob = download_bytes_from_s3(s3_key)
    text = extract_text_from_blob(blob, s3_key)

    count = index_document_text(
        db,
        document_id=document_id,
        tenant_id=tenant_id,
        text=text,
    )
    db.query(Document).filter(Document.id == document_id).update(
        {"status": "indexed"}
    )
    db.commit()

    logger.info("document_processed", document_id=document_id, chunks=count)


def poll_queue() -> None:
    setup_logging(settings.log_level)
    init_db()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    queue_url = ensure_queue_exists()
    if not queue_url:
        logger.warning("sqs_not_configured", message="Worker running in idle mode")
        while not _shutdown:
            time.sleep(10)
        logger.info("worker_shutdown_complete")
        return

    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    client = boto3.client("sqs", **kwargs)

    logger.info("worker_started", queue=queue_url)
    backoff = 1

    while not _shutdown:
        try:
            response = client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=5,
                WaitTimeSeconds=10,
                VisibilityTimeout=60,
            )
            backoff = 1
        except ClientError as exc:
            logger.error("sqs_receive_failed", error=str(exc), backoff=backoff)
            time.sleep(min(backoff, 60))
            backoff *= 2
            continue
        except Exception as exc:
            logger.error("sqs_receive_failed", error=str(exc), backoff=backoff)
            time.sleep(min(backoff, 60))
            backoff *= 2
            continue

        messages = response.get("Messages", [])
        if not messages:
            continue

        db = SessionLocal()
        try:
            for msg in messages:
                try:
                    process_message(db, msg["Body"])
                    client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )
                except Exception as exc:
                    logger.error("message_processing_failed", error=str(exc))
                    db.rollback()
        finally:
            db.close()

    logger.info("worker_shutdown_complete")


if __name__ == "__main__":
    poll_queue()