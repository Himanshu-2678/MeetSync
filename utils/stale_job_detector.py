# utils/stale_job_detector.py
from datetime import datetime, timezone, timedelta
import logging
from database.connection import SessionLocal
from database.models import Meeting

logger = logging.getLogger(__name__)

STALE_THRESHOLD_MINUTES = 10

def mark_stale_meetings():
    """
    Mark meetings stuck at 'processing' for too long as 'failed'.
    Calling this periodically or on app startup.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)

        stale_meetings = db.query(Meeting).filter(
            Meeting.processing_status == "processing",
            Meeting.created_at < cutoff).all()

        for meeting in stale_meetings:
            meeting.processing_status = "failed"
            logger.warning(f"Meeting {meeting.id} marked as failed — stale after {STALE_THRESHOLD_MINUTES} mins")

        if stale_meetings:
            db.commit()
            logger.info(f"Marked {len(stale_meetings)} stale meetings as failed")

    except Exception as e:
        db.rollback()
        logger.error(f"Stale job detection failed: {e}")
    finally:
        db.close()