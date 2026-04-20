import logging
import json
from database.connection import SessionLocal
from database.models import MeetingMetrics

logger = logging.getLogger(__name__)

def save_metrics(
    meeting_id: int,
    status: str,
    processing_time_seconds: float = None,
    transcript_word_count: int = None,
    gemini_retry_count: int = 0,
    failure_reason: str = None,
    queue_delay_seconds=None,
    experiment_tag=None,
    worker_count=None,
):

    log_data = {
        "event": "meeting_processed",
        "meeting_id": meeting_id,
        "status": status,
        "processing_time_seconds": round(processing_time_seconds, 2) if processing_time_seconds else None,
        "transcript_word_count": transcript_word_count,
        "gemini_retry_count": gemini_retry_count,
        "failure_reason": failure_reason,
        "queue_delay_seconds": round(queue_delay_seconds, 2) if queue_delay_seconds else None,
        "experiment_tag": experiment_tag,
        "worker_count": worker_count,
    }

    if status == "success":
        logger.info(json.dumps(log_data))
    else:
        logger.error(json.dumps(log_data))

    db = SessionLocal()
    try:
        existing = db.query(MeetingMetrics).filter_by(meeting_id=meeting_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        metrics = MeetingMetrics(
            meeting_id=meeting_id,
            processing_time_seconds=round(processing_time_seconds, 2) if processing_time_seconds else None,
            transcript_word_count=transcript_word_count,
            gemini_retry_count=gemini_retry_count,
            status=status,
            failure_reason=failure_reason,
            queue_delay_seconds=round(queue_delay_seconds, 2) if queue_delay_seconds else None,
            experiment_tag=experiment_tag,
            worker_count=worker_count
        )

        db.add(metrics)
        db.commit()
        logger.info(f"Metrics saved for meeting {meeting_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save metrics for meeting {meeting_id}: {e}")
    finally:
        db.close()