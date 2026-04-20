from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from utils.db_safe_commit import safe_commit
from datetime import datetime, timedelta, date
import io
from tasks import process_meeting
from dotenv import load_dotenv
load_dotenv()

import uuid

from database.init_db import init_db

from sqlalchemy import func as sa_func

from utils.stale_job_detector import mark_stale_meetings
import os
import logging

from database.connection import SessionLocal
from database.models import Meeting, Task, MeetingMetrics
from celery_app import celery

from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

with app.app_context():
    init_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")

logger = logging.getLogger(__name__)


upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)


def get_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def scheduled_stale_check():
    return
    with app.app_context():
        mark_stale_meetings()

scheduler = BackgroundScheduler()
"""scheduler.add_job(
    func=scheduled_stale_check,
    trigger="interval",
    minutes=10,
    id="stale_job_detector",
    replace_existing=True,
    next_run_time=datetime.now() + timedelta(seconds=30)
)
scheduler.start()"""

# Run once immediately on startup too
##threading.Thread(target=scheduled_stale_check, daemon=True).start()

# Shut down scheduler cleanly when app exits
atexit.register(lambda: scheduler.shutdown())


@app.route("/download/<int:meeting_id>")
def download_summary(meeting_id):
    db = SessionLocal()
    try:
        # Session validation — only owner can download
        meeting = db.query(Meeting).filter_by(
            id=meeting_id,
            session_id=get_session_id()
        ).first()

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


# API: Meeting history
@app.route("/api/meetings")
def api_meetings():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    sid = get_session_id()

    db = SessionLocal()
    try:
        total = db.query(Meeting).filter_by(session_id=sid).count()
        meetings = (
            db.query(Meeting)
            .filter_by(session_id=sid)
            .order_by(Meeting.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": -(-total // per_page),
            "meetings": [
                {
                    "id": m.id,
                    "filename": m.filename,
                    "processing_status": m.processing_status,
                    "created_at": m.created_at.strftime("%d %b %Y, %H:%M"),
                    "processing_time_seconds": (
                        round(m.metrics.processing_time_seconds, 2)
                        if m.metrics and m.metrics.processing_time_seconds else None
                    )
                }
                for m in meetings
            ]
        })
    finally:
        db.close()


# Tasks with filters
@app.route("/api/tasks")
def api_tasks():
    owner    = request.args.get("owner")
    status   = request.args.get("status")
    overdue  = request.args.get("overdue")
    sid = get_session_id()

    db = SessionLocal()
    try:
        query = db.query(Task).join(Meeting).filter(Meeting.session_id == sid)

        if owner:
            query = query.filter(Task.owner.ilike(f"%{owner}%"))

        if status:
            query = query.filter(Task.status == status)

        if overdue and overdue.lower() == "true":
            today = date.today()
            query = query.filter(
                Task.deadline_parsed < today,
                Task.deadline_parsed.isnot(None),
                Task.status != "completed"
            )

        tasks = query.order_by(Task.created_at.desc()).all()

        return jsonify({
            "count": len(tasks),
            "tasks": [
                {
                    "id": t.id,
                    "meeting_id": t.meeting_id,
                    "meeting_filename": t.meeting.filename,
                    "description": t.description,
                    "owner": t.owner,
                    "deadline_raw": t.deadline_raw,
                    "deadline_parsed": t.deadline_parsed.isoformat() if t.deadline_parsed else None,
                    "priority": t.priority,
                    "status": t.status
                }
                for t in tasks
            ]
        })
    finally:
        db.close()


# Meeting history page
@app.route("/history")
def history():
    return render_template("history.html")


# Task searching
@app.route("/tasks/search")
def task_search():
    return render_template("task_search.html")


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        audio_file = request.files['audio']

        # Prevent filename collisions across users
        original_filename = audio_file.filename
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        audio_file.save(file_path)

        db = SessionLocal()

        try:
            meeting = Meeting(
                filename=original_filename,
                processing_status="processing",
                session_id=get_session_id()
            )

            db.add(meeting)
            success = safe_commit(db, logger)

            if success:
                db.refresh(meeting)
                meeting_id = meeting.id
                logger.info(f"Meeting {meeting_id} inserted")
            else:
                logger.error("DB insert failed. Cannot continue processing.")
                return render_template(
                    "index.html",
                    error="Database temporarily unavailable. Please try again."
                )

        finally:
            db.close()

        try:
            process_meeting.delay(meeting_id, file_path)
            logger.info(f"Dispatching meeting {meeting_id} to Celery")
            #celery.send_task("tasks.process_meeting", args=[meeting_id, file_path])
            session['last_meeting_id'] = meeting_id

        except Exception as e:
            logger.error(f"Celery dispatch failed: {e}", exc_info=True)
            db = SessionLocal()
            try:
                if isinstance(meeting_id, int):
                    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
                else:
                    meeting = None
                if meeting:
                    meeting.processing_status = "failed"
                    safe_commit(db, logger)
            except Exception as inner_e:
                logger.error(f"Failed to mark meeting as failed after thread error: {inner_e}")
                db.rollback()
            finally:
                db.close()
            return render_template("index.html", error="Service temporarily unavailable. Please try again.")

        return redirect(url_for("meeting_status", meeting_id=meeting_id))

    """last_meeting_id = session.get('last_meeting_id')
    if last_meeting_id:
        db = SessionLocal()
        try:
            meeting = db.query(Meeting).filter_by(id=last_meeting_id).first()
            if meeting and meeting.processing_status == "success":
                return redirect(url_for("meeting_result", meeting_id=last_meeting_id))
        finally:
            db.close()
"""
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

        meeting = db.query(Meeting).filter_by(
            id=meeting_id,
            session_id=get_session_id()
        ).first()

        if not meeting:
            return jsonify({"status": "not_found"}), 404

        if meeting.processing_status == "success":
            return jsonify({"status": "success"})

        return jsonify({"status": meeting.processing_status})

    finally:
        db.close()


@app.route("/result/<int:meeting_id>")
def meeting_result(meeting_id):

    db = SessionLocal()
    try:
        # Session validation — only owner can view result
        meeting = db.query(Meeting).filter_by(
            id=meeting_id,
            session_id=get_session_id()
        ).first()

        if not meeting or meeting.processing_status != "success":
            return redirect(url_for("meeting_status", meeting_id=meeting_id))

        tasks = db.query(Task).filter_by(meeting_id=meeting_id).all()
        return render_template("result.html", meeting=meeting, tasks=tasks)
    finally:
        db.close()


@app.route("/new")
def new_meeting():
    session.pop('last_meeting_id', None)
    return redirect(url_for("home"))


@app.route("/api/stats")
def api_stats():
    db = SessionLocal()
    try:
        total_meetings = db.query(Meeting).filter_by(
            processing_status="success"
        ).count()

        metrics = db.query(MeetingMetrics).filter_by(status="success").all()

        total_words = sum(
            m.transcript_word_count for m in metrics
            if m.transcript_word_count
        )
        # ~130 words/min average speech rate
        estimated_audio_hours = round((total_words / 130) / 60, 1)

        processing_times = [
            m.processing_time_seconds for m in metrics
            if m.processing_time_seconds
        ]
        avg_latency = round(
            sum(processing_times) / len(processing_times), 1
        ) if processing_times else 0

        total_all = db.query(MeetingMetrics).count()
        success_count = db.query(MeetingMetrics).filter_by(
            status="success"
        ).count()
        success_rate = round(
            (success_count / total_all) * 100, 1
        ) if total_all else 0

        # Distribution: % of meetings that completed under 30s
        under_30 = sum(1 for t in processing_times if t <= 30)
        pct_under_30 = round(
            (under_30 / len(processing_times)) * 100
        ) if processing_times else 0

        return jsonify({
            "total_meetings": total_meetings,
            "estimated_audio_hours": estimated_audio_hours,
            "avg_latency_seconds": avg_latency,
            "success_rate": success_rate,
            "pct_under_30s": pct_under_30
        })
    finally:
        db.close()

if __name__ == "__main__":
    app.run(debug=True)