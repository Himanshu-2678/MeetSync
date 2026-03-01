from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import io
from dotenv import load_dotenv
load_dotenv()

from utils.stale_job_detector import mark_stale_meetings
import os
import logging

from database.connection import SessionLocal
from database.models import Meeting, Task
from tasks import process_meeting

from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)


def scheduled_stale_check():
    with app.app_context():
        mark_stale_meetings()

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scheduled_stale_check,
    trigger="interval",
    minutes=10,
    id="stale_job_detector",
    replace_existing=True
)
scheduler.start()

# Run once immediately on startup too
scheduled_stale_check()

# Shut down scheduler cleanly when app exits
atexit.register(lambda: scheduler.shutdown())
@app.route("/download/<int:meeting_id>")
def download_summary(meeting_id):
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting or meeting.processing_status != "success":
            return "No summary available.", 400

        tasks = db.query(Task).filter_by(meeting_id=meeting_id).all()

        lines = []
        lines.append("MEETING SUMMARY")
        lines.append("=" * 50)
        lines.append(meeting.summary)
        lines.append("")

        if tasks:
            lines.append("ACTION ITEMS & TASKS")
            lines.append("=" * 50)
            for i, t in enumerate(tasks, 1):
                lines.append(f"\nTask {i}: {t.description}")
                lines.append(f"  Owner       : {t.owner}")
                lines.append(f"  Deadline    : {t.deadline_raw or 'Not specified'}")
                lines.append(f"  Priority    : {t.priority}")
                lines.append(f"  Status      : {t.status}")

        buffer = io.BytesIO()
        buffer.write("\n".join(lines).encode('utf-8'))
        buffer.seek(0)

        return send_file(buffer, as_attachment=True,
                         download_name="meeting_summary.txt",
                         mimetype='text/plain')
    finally:
        db.close()


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        audio_file = request.files['audio']
        filename = audio_file.filename
        file_path = os.path.join(upload_folder, filename)
        audio_file.save(file_path)

        db = SessionLocal()
        try:
            meeting = Meeting(filename=filename, processing_status="processing")
            db.add(meeting)
            db.commit()
            db.refresh(meeting)
            meeting_id = meeting.id
            logger.info(f"Meeting {meeting_id} inserted, enqueuing job")
        finally:
            db.close()

        # Fix 2: Graceful enqueue failure
        try:
            process_meeting.delay(meeting_id, file_path)
            logger.info(f"Meeting {meeting_id} enqueued successfully")
        except Exception as e:
            logger.error(f"Failed to enqueue meeting {meeting_id}: {e}")

            # Mark meeting as failed immediately
            db = SessionLocal()
            try:
                meeting = db.query(Meeting).filter_by(id=meeting_id).first()
                if meeting:
                    meeting.processing_status = "failed"
                    db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to mark meeting as failed after enqueue error: {inner_e}")
                db.rollback()
            finally:
                db.close()

            return render_template("index.html", error="Service temporarily unavailable. Please try again.")

        return redirect(url_for("meeting_status", meeting_id=meeting_id))

    return render_template("index.html", error=None)


@app.route("/meeting/<int:meeting_id>")
def meeting_status(meeting_id):
    """Page that polls until processing is done."""
    return render_template("status.html", meeting_id=meeting_id)


@app.route("/status/<int:meeting_id>")
def check_status(meeting_id):
    """JSON endpoint polled by frontend."""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting:
            return jsonify({"status": "not_found"}), 404

        if meeting.processing_status == "success":
            tasks = db.query(Task).filter_by(meeting_id=meeting_id).all()
            return jsonify({
                "status": "success",
                "meeting_id": meeting_id,
                "filename": meeting.filename,
                "summary": meeting.summary,
                "tasks": [
                    {
                        "task": t.description,
                        "owner": t.owner,
                        "deadline": t.deadline_raw or "Not specified",
                        "priority": t.priority,
                        "status": t.status
                    }
                    for t in tasks
                ]
            })

        return jsonify({"status": meeting.processing_status})

    finally:
        db.close()


@app.route("/result/<int:meeting_id>")
def meeting_result(meeting_id):
    """Final result page."""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting or meeting.processing_status != "success":
            return redirect(url_for("meeting_status", meeting_id=meeting_id))

        tasks = db.query(Task).filter_by(meeting_id=meeting_id).all()
        return render_template("result.html", meeting=meeting, tasks=tasks)
    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=True)