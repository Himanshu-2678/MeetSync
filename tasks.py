from database.connection import SessionLocal
from database.models import Meeting, Task
from summarizer import summarize_text
from transcribe import transcribe_audio
from utils.metrics import save_metrics
import dateparser
import logging
import time
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_deadline(raw: str):
    if not raw or raw.strip().lower() in ("not specified", "none", ""):
        return None
    try:
        parsed = dateparser.parse(raw, settings={"RETURN_AS_TIMEZONE_AWARE": False})
        return parsed.date() if parsed else None
    except Exception as e:
        logger.warning(f"Deadline parsing failed for '{raw}': {e}")
        return None


def process_meeting(meeting_id: int, file_path: str):
    logger.info(f"Worker picked up meeting {meeting_id}")
    start_time = time.time()
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found in DB")
            return

        # Idempotency guard
        if meeting.processing_status == "success":
            logger.warning(f"Meeting {meeting_id} already successfully processed — skipping")
            return

        if meeting.processing_status == "failed":
            logger.warning(f"Meeting {meeting_id} already marked failed — skipping")
            return

        existing_tasks = db.query(Task).filter_by(meeting_id=meeting_id).count()
        if existing_tasks > 0:
            logger.warning(f"Meeting {meeting_id} already has {existing_tasks} tasks — skipping")
            return

        # Step 1: Transcribing the audio file
        try:
            transcript = transcribe_audio(file_path)
            transcript_word_count = len(transcript.split()) if transcript else 0
            logger.info(f"Meeting {meeting_id} transcription complete — {transcript_word_count} words")
        except Exception as e:
            logger.error(f"Transcription failed for meeting {meeting_id}: {e}")
            meeting.processing_status = "failed"
            db.commit()
            save_metrics(
                meeting_id=meeting_id,
                status="failed",
                processing_time_seconds=time.time() - start_time,
                failure_reason=f"Transcription failed: {str(e)}")
            return

        # Step 2: Summarizing
        result = summarize_text(transcript)
        retry_count = result.get("retry_count", 0)

        if result["status"] != "success":
            logger.warning(f"Summarization failed for meeting {meeting_id}: {result['error']}")
            meeting.transcript = transcript
            meeting.processing_status = "failed"
            db.commit()
            save_metrics(
                meeting_id=meeting_id,
                status="failed",
                processing_time_seconds=time.time() - start_time,
                transcript_word_count=transcript_word_count,
                gemini_retry_count=retry_count,
                failure_reason=f"Summarization failed: {result['error']}")
            return

        summary = result["summary"]
        raw_tasks = result["tasks"]

        # Step 3: Single transaction
        try:
            meeting.transcript = transcript
            meeting.summary = summary
            meeting.processing_status = "success"

            for t in raw_tasks:
                deadline_raw = t.get("deadline", "")
                task = Task(
                    meeting_id=meeting_id,
                    description=t.get("task", ""),
                    owner=t.get("owner", "Unassigned"),
                    deadline_raw=deadline_raw,
                    deadline_parsed=parse_deadline(deadline_raw),
                    priority=t.get("priority", "Medium"),
                    status="pending")
                db.add(task)

            db.commit()
            processing_time = time.time() - start_time
            logger.info(f"Meeting {meeting_id} completed in {round(processing_time, 2)}s, "
                        f"{len(raw_tasks)} tasks inserted")

            save_metrics(
                meeting_id=meeting_id,
                status="success",
                processing_time_seconds=processing_time,
                transcript_word_count=transcript_word_count,
                gemini_retry_count=retry_count)

        except Exception as e:
            db.rollback()
            logger.error(f"DB transaction failed for meeting {meeting_id}: {e}")
            try:
                meeting.processing_status = "failed"
                db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to mark meeting as failed: {inner_e}")
                db.rollback()

            save_metrics(
                meeting_id=meeting_id,
                status="failed",
                processing_time_seconds=time.time() - start_time,
                transcript_word_count=transcript_word_count,
                gemini_retry_count=retry_count,
                failure_reason=f"DB transaction failed: {str(e)}")

    except Exception as e:
        db.rollback()
        logger.error(f"Unhandled worker error for meeting {meeting_id}: {e}")
        try:
            meeting = db.query(Meeting).filter_by(id=meeting_id).first()
            if meeting:
                meeting.processing_status = "failed"
                db.commit()
        except Exception:
            db.rollback()

        save_metrics(
            meeting_id=meeting_id,
            status="failed",
            processing_time_seconds=time.time() - start_time,
            failure_reason=f"Unhandled error: {str(e)}")
    finally:
        db.close()