# MeetSync: AI Meeting Minutes Generator

MeetSync is an AI-powered meeting minutes generator I built to help users quickly extract key insights from meeting audio.
The idea was simple: instead of listening to long recordings or writing notes manually, users should be able to upload meeting audio and instantly get clear, structured minutes with decisions and action items.

## Architecture Diagram

![MeetSync Architecture](assets/architecure_diagram_meetsync.png)

## Why I built this

In most meetings, the real value lies in:
- what was discussed
- what decisions were made
- who is responsible for what

I created MeetSync to automate this process and turn raw meeting audio into actionable meeting minutes that can be shared immediately after a meeting.

## Features

- Upload meeting audio files (WAV / MP3)
- Automatic speech-to-text transcription via Deepgram
- AI-generated structured meeting minutes with summary, key decisions, and action items
- Each action item extracted with: owner, deadline, priority, and dependencies
- Async processing upload returns instantly, result appears when ready
- Meeting history page with processing status and time
- Cross-meeting task search with filters for priority, status, and overdue tasks
- Downloadable meeting summary (TXT)
- Clean, minimal UI optimized for readability
- Persistent storage of all meetings, transcripts, and tasks in PostgreSQL

---

## How It Works

1. The user uploads a meeting audio file
2. Flask saves the file and immediately inserts a meeting record with status `processing`
3. The job is enqueued to a Celery worker via Redis. In the demo deployment, the worker runs in the same service as the web app due to platform constraints.
4. The user is redirected to a polling page that checks status every 3 seconds
5. The worker transcribes the audio using Deepgram, then calls Gemini to extract structured minutes
6. Gemini's response is validated against a strict Pydantic schema before being accepted
7. On success, the meeting and tasks are saved to PostgreSQL in a single transaction
8. The polling page detects the success and redirects to the result page automatically

---

## Tech Stack

- Backend: Python, Flask
- Task Queue: Celery with Redis as broker
- Speech-to-Text: Deepgram API
- LLM: Google Gemini 2.5 Flash
- Schema Validation: Pydantic
- Database: PostgreSQL with SQLAlchemy
- Frontend: HTML, CSS, vanilla JavaScript
- Scheduling: APScheduler
- Deployment: Render

---

## Project Structure

```
MeetSync/
│
├── app.py                        # Flask application, routes, session handling
├── summarizer.py                 # Gemini prompting, Pydantic validation, retry logic
├── transcribe.py                 # Deepgram transcription
├── tasks.py                      # Celery background task
├── worker.py                     # Celery app definition
├── check_models.py               # Utility to check available Gemini models
│
├── database/
│   ├── __init__.py
│   ├── connection.py             # SQLAlchemy engine and session
│   ├── models.py                 # Meeting, Task, MeetingMetrics models
│   └── init_db.py                # Table creation script
│
├── utils/
│   ├── __init__.py
│   ├── metrics.py                # Save and log processing metrics
│   └── stale_job_detector.py     # Mark stuck jobs as failed
│
├── templates/
│   ├── index.html                # Upload page
│   ├── status.html               # Polling/processing page
│   ├── result.html               # Result page with summary and tasks
│   ├── history.html              # Meeting history page
│   └── task_search.html          # Cross-meeting task search page
│
├── assets/
│   ├── meetsync-architecture.png # Architecture diagram
│   ├── meetsync-logo.html        # Logo source
│   └── meetsync-logo_files/      # Logo assets
│
├── uploads/                      # Uploaded audio files (not committed)
├── .env                          # Environment variables (not committed)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Screenshots

![MeetSync-Home](assets/main_page(1).png)
![MeetSync-History](assets/main_page(2).png)

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Himanshu-2678/MeetSync.git
cd MeetSync
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

macOS / Linux:
```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_gemini_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
FLASK_SECRET_KEY=your_secret_key
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/meetsync
```

### 5. Initialize the database

```bash
python -m database.init_db
```

### 6. Start Redis

On WSL or Linux:
```bash
sudo service redis-server start
```

### 7. Start the Celery worker

```bash
celery -A worker.celery_app worker --loglevel=info --pool=solo
```

### 8. Run the application

```bash
python app.py
```

---
### System Evaluation
The system was evaluated across reliability, correctness, and cost. Latency, retries, and failure modes are measured per meeting via structured metrics stored in the meeting_metrics table. Output quality was evaluated qualitatively against real meeting transcripts. Cost per meeting was estimated using real API pricing and observed token usage.
#### Reliability
Every meeting job records whether it succeeded or failed, how long it took, and whether Gemini needed to be retried. This makes it possible to query the failure rate and retry patterns directly from the database rather than guessing. In practice, Gemini 2.5 Flash returned valid JSON on the first attempt for the majority of test meetings. During testing, the Pydantic validation layer never rejected a response that the JSON parser accepted, indicating strong schema adherence when the prompt is well formed.
The stale job detector was verified by manually inserting a meeting row with a created_at timestamp 15 minutes in the past and confirming it was marked failed on the next app startup. Worker crash recovery works as designed.
#### Output Quality
Output quality was evaluated by uploading real meeting audio where the content was already known and comparing the generated summary and task list against what was actually discussed. The summary consistently captured the main discussion topics and decisions. Task extraction was accurate when speaker attribution was clear in the audio. When multiple people spoke without introduction, owner assignment defaulted to Unassigned correctly rather than hallucinating a name.
Deadline extraction from natural language worked well for specific phrases like "by Friday" or "end of next week." Vague phrases like "soon" or "as soon as possible" correctly produced a NULL in deadline_parsed with the original text preserved in deadline_raw.
#### Performance
Processing time scales roughly with audio length. A one-minute audio file completed in around 7-15 seconds end to end. A 10-15 minute meeting maybe take 30-35 seconds. The bottleneck is Deepgram transcription, not Gemini summarization. Because processing is async, this has no impact on the user-facing response time, the upload returns instantly regardless of audio length.
#### Cost
At real API pricing, a typical 30-minute meeting costs under $0.15, approximately $0.13 for Deepgram transcription and under $0.01 for Gemini token usage. At 1000 meetings per day, API costs would be roughly $150/day. The dominant cost is transcription, not the LLM.
Because retries are rare and observable, retry-related cost inflation is minimal in practice.
#### Known Limitations
These limitations are intentional tradeoffs rather than bugs - 
The system does not handle speaker diarization so it cannot attribute statements to specific speakers when they are not introduced by name in the audio. Task ownership extraction depends entirely on whether the transcript contains explicit ownership language. If a meeting discusses work without assigning it to named people, all tasks will show Unassigned. Additionally, deadline_parsed relies on dateparser resolving relative dates against the system clock at processing time, which means a deadline like "next Friday" will resolve differently depending on when the job runs.

## Design Decisions and Tradeoffs

### Why async processing was needed

The original version processed everything synchronously inside the Flask request. Deepgram transcription and Gemini summarization together take 10-30 seconds depending on audio length. Holding an HTTP request open that long is not acceptable in production it ties up a worker thread, makes the app feel broken, and fails entirely if the client disconnects.

Moving to async processing meant the upload returns in under a second, the heavy work happens in a background process, and the frontend polls for the result independently.

### Why Celery over RQ

RQ was the first choice because it is simpler to set up. It failed on Windows because it depends on Unix-only process forking (`fork` context) and signal handling (`SIGALRM`). Celery with `--pool=solo` works correctly on Windows and will also work on Linux-based production servers like Render without any changes.

### Why APScheduler instead of Celery Beat

The stale job detector needs to run periodically to mark meetings that are stuck at `processing` as `failed`. for example when a worker crashes mid-task. Celery Beat would have required a fourth process running alongside Flask, the Celery worker, and Redis. APScheduler runs inside the Flask process as a background thread, which is sufficient for a task that runs every 10 minutes and does a simple database query. There is no need for the additional operational overhead of Celery Beat at this scale.

### Failure handling philosophy

Every failure point has an explicit outcome. If transcription fails, the meeting is marked `failed` immediately. If Gemini returns malformed JSON, the system retries up to two times before giving up. If the retry limit is exhausted, the failure is recorded with a reason which not silently converted into a partial result. Meeting updates and task inserts happen in a single database transaction, so there is no state where a meeting shows `success` but has no tasks. This was a deliberate decision: silent failures are harder to debug than loud ones.

### What breaks at 1000 meetings per day

At that volume, a few things would need to change:

- A single Celery worker would become a bottleneck. The queue would grow faster than it drains. The fix is horizontal scaling with multiple worker processes or machines pulling from the same Redis queue.
- The `uploads/` folder on a local or ephemeral filesystem would fill up or disappear on redeploy. Audio files would need to move to object storage like S3 or Cloudflare R2.
- PostgreSQL with default settings can handle this load, but queries against the `tasks` table without proper indexing (beyond what is already in place) would slow down as the table grows. Additional indexes on `owner`, `priority`, and `deadline_parsed` would be needed.
- The stale job detector running every 10 minutes on a full `meetings` table would benefit from a tighter index on `processing_status` and `created_at` together.

### Cost estimate per meeting

Based on a typical 30-minute meeting producing roughly 3000-4000 words of transcript:

- Deepgram: approximately $0.0043 per minute of audio, so $0.13 per 30-minute meeting
- Gemini 2.5 Flash: approximately $0.00015 per 1000 input tokens. A 4000-word transcript is roughly 5000 tokens, costing around $0.00075 per meeting
- Total per meeting: under $0.15

At 1000 meetings per day, that is roughly $150/day in API costs, not counting infrastructure.

---

## Observability

Every processed meeting records the following metrics to the `meeting_metrics` table:

- `processing_time_seconds`: end-to-end time from job pickup to completion
- `transcript_word_count`: number of words in the transcript sent to Gemini
- `gemini_retry_count`: how many times Gemini needed to be retried (0 means first attempt succeeded)
- `status` : success or failed
- `failure_reason`: exact reason if the job failed

These can be queried directly:

```sql
-- Average processing time for successful meetings
SELECT ROUND(AVG(processing_time_seconds)::numeric, 2) AS avg_seconds
FROM meeting_metrics WHERE status = 'success';

-- Meetings that required Gemini retries
SELECT meeting_id, gemini_retry_count FROM meeting_metrics WHERE gemini_retry_count > 0;

-- Failure rate
SELECT status, COUNT(*) FROM meeting_metrics GROUP BY status;
```

## Deployment Notes (Render Free Tier)

Render’s free tier does not support background worker services or interactive shells.  
To keep the asynchronous architecture intact for demonstration purposes, the Celery worker is co-located with the Flask web service and runs in the same container.

The web service start command launches both Gunicorn and the Celery worker process:
```bash
gunicorn app:app & celery -A worker.celery_app worker --loglevel=info --pool=solo
```

In a production setup, the Celery worker would run as a separate service and scale independently.  
This deployment choice is a platform constraint, not an architectural limitation of the system.



gunicorn app:app & celery -A worker.celery_app worker --loglevel=info --pool=solo
