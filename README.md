# MeetSync: AI Meeting Minutes Generator

MeetSync is an AI-powered meeting minutes generator built to help users quickly extract key insights from meeting audio. The idea was simple: instead of listening to long recordings or writing notes manually, users should be able to upload meeting audio and instantly get clear, structured minutes with decisions and action items.

## Architecture Diagram

![MeetSync Architecture](assets/meetsync_architecture.svg)

## Why I built this

In most meetings, the real value lies in what was discussed, what decisions were made, and who is responsible for what.

MeetSync automates this process and turns raw meeting audio into actionable meeting minutes that can be shared immediately after a meeting.

## Features

- Upload meeting audio files (WAV / MP3)
- Automatic speech-to-text transcription via Deepgram
- AI-generated structured meeting minutes with summary, key decisions, and action items
- Each action item extracted with: owner, deadline, priority, and dependencies
- Async processing: upload returns instantly, result appears when ready
- Meeting history page with processing status and time
- Cross-meeting task search with filters for priority, status, and overdue tasks
- Downloadable meeting summary (TXT)
- Session-based isolation so each browser sees only its own meetings
- Clean, minimal UI optimized for readability
- Persistent storage of all meetings, transcripts, and tasks in PostgreSQL

---

## How It Works

1. The user uploads a meeting audio file
2. Flask saves the file and immediately inserts a meeting record with status `processing`
3. The meeting is dispatched to a background worker (Celery in local testing, threading in deployed version) for asynchronous processing. The worker is wrapped with crash protection so failures are logged instead of silently terminating the job.
4. The user is redirected to a polling page that checks status every 3 seconds
5. The worker transcribes the audio using Deepgram, then calls Gemini to extract structured minutes
6. Gemini response is validated against a strict Pydantic schema before being accepted
7. On success, the meeting and tasks are saved to PostgreSQL in a single transaction
8. The polling page detects the success and redirects to the result page automatically

---

## Tech Stack

- Backend: Python, Flask
- Async Processing: Celery with Redis (local testing), Python threading (deployed version)
- Load Testing: Locust
- Speech-to-Text: Deepgram API
- LLM: Google Gemini 2.5 Flash
- Schema Validation: Pydantic
- Database: PostgreSQL with SQLAlchemy (hosted on Neon)
- Frontend: HTML, CSS, vanilla JavaScript
- Scheduling: APScheduler
- Deployment: Render

---

## Project Structure
```
MeetSync/
|-- app.py                        # Flask application, routes, session handling
|-- summarizer.py                 # Gemini prompting, Pydantic validation, retry logic
|-- transcribe.py                 # Deepgram transcription
|-- tasks.py                      # Background processing function
|-- check_models.py               # Utility to check available Gemini models
|
|-- database/
|   |-- connection.py             # SQLAlchemy engine and session
|   |-- models.py                 # Meeting, Task, MeetingMetrics models
|   `-- init_db.py                # Table creation script
|
|-- utils/
|   |-- metrics.py                # Save and log processing metrics
|   |-- stale_job_detector.py     # Mark stuck jobs as failed
|   `-- db_safe_commit.py        # prevent app crash when the database connection temporarily fails.
|
|-- templates/
|   |-- index.html                # Upload page
|   |-- status.html               # Polling/processing page
|   |-- result.html               # Result page with summary and tasks
|   |-- history.html              # Meeting history page
|   `-- task_search.html          # Cross-meeting task search page
|
|-- uploads/                      # Uploaded audio files (not committed)
|-- .env                          # Environment variables (not committed)
|-- requirements.txt
`-- README.md
```

---

## Demo

[![MeetSync-Home](assets/meetsync_main_page.png)](https://youtu.be/fYaQ3g40ehY)
[![MeetSync-History](assets/meetsync_summary.png)](https://youtu.be/fYaQ3g40ehY)
_click the image to play the video demo._

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

### 6. Run the application
```bash
python app.py
```

## System Evolution

### V1
- Thread-based async processing
- No queue visibility
- Limited failure tracking

### V2 (current)
- Celery + Redis queue
- Worker-based processing
- Retry logic with failure tracking
- Metrics collection (queue delay, processing time)

This transition enabled controlled load testing and clear identification of system bottlenecks.

## System Evaluation

The system was evaluated across reliability, correctness, and cost. Latency, retries, and failure modes are measured per meeting via structured metrics stored in the `meeting_metrics` table. Output quality was evaluated qualitatively against real meeting transcripts. Cost per meeting was estimated using real API pricing and observed token usage.

### Reliability

Every meeting job records whether it succeeded or failed, how long it took, and whether Gemini needed to be retried. This makes it possible to query the failure rate and retry patterns directly from the database rather than guessing. In practice, Gemini 2.5 Flash returned valid JSON on the first attempt for the majority of test meetings. During testing, the Pydantic validation layer never rejected a response that the JSON parser accepted, indicating strong schema adherence when the prompt is well formed.

The stale job detector was verified by manually inserting a meeting row with a `created_at` timestamp 15 minutes in the past and confirming it was marked failed on the next app startup. Worker crash recovery works as designed.
 

### Structured Output Reliability

LLM responses are validated against a strict Pydantic schema before being accepted by the system.

Under normal conditions, Gemini outputs consistently adhered to the expected JSON structure and passed validation on the first attempt. No cases were observed where syntactically valid JSON failed schema validation, indicating strong alignment between prompting and schema design.

Validation acts as a safeguard against malformed or incomplete outputs. Any response failing schema validation triggers a retry, ensuring that only structured and complete data is stored in the system.

This ensures that downstream components operate on reliable structured data rather than raw LLM output.


### Output Quality

Output quality was evaluated by uploading real meeting audio where the content was already known and comparing the generated summary and task list against what was actually discussed. The summary consistently captured the main discussion topics and decisions. Task extraction was accurate when speaker attribution was clear in the audio. When multiple people spoke without introduction, owner assignment defaulted to Unassigned correctly rather than hallucinating a name.

Deadline extraction from natural language worked well for specific phrases like "by Friday" or "end of next week." Vague phrases like "soon" or "as soon as possible" correctly produced a NULL in `deadline_parsed` with the original text preserved in `deadline_raw`.

### Performance

Processing time scales roughly with audio length. A one-minute audio file completed in around 7-15 seconds end to end. A 10-15 minute meeting may take 30-35 seconds. The bottleneck is Deepgram transcription, not Gemini summarization. Because processing is async, this has no impact on the user-facing response time. The upload returns instantly regardless of audio length.

### Cost

At real API pricing, a typical 30-minute meeting costs under $0.15, approximately $0.13 for Deepgram transcription and under $0.01 for Gemini token usage. At 1000 meetings per day, API costs would be roughly $150/day. The dominant cost is transcription, not the LLM.

Because retries are rare and observable, retry-related cost inflation is minimal in practice.

### Known Limitations

These are intentional tradeoffs rather than bugs.

The system does not handle speaker diarization so it cannot attribute statements to specific speakers when they are not introduced by name in the audio. Task ownership extraction depends entirely on whether the transcript contains explicit ownership language. If a meeting discusses work without assigning it to named people, all tasks will show Unassigned. Additionally, `deadline_parsed` relies on dateparser resolving relative dates against the system clock at processing time, which means a deadline like "next Friday" will resolve differently depending on when the job runs. 
Under high load, the system is constrained by single-worker processing and external API rate limits. Queue latency can grow significantly when the ingestion rate exceeds processing capacity.

## Load Testing & System Behavior

The system was evaluated using controlled burst experiments to understand how queueing and processing behave under different worker configurations.

### Setup

- Fixed workload: 10 meeting uploads triggered simultaneously using Locust
- Audio length: ~1 minute
- Mock LLM enabled with fixed latency (~3 seconds) to isolate system behavior from external API limits
- Celery worker with thread-based concurrency

### Worker Configurations Tested

| Workers | Configuration |
|--------|--------------|
| 1 | `--concurrency=1` |
| 2 | `--concurrency=2` |
| 4 | `--concurrency=4` |


### Results

| Workers | Avg Queue Delay (s) | Avg Processing Time (s) | Avg Total Time (s) |
|--------|--------------------|--------------------------|--------------------|
| 1 | ~24.7 | ~5.3 | ~30.0 |
| 2 | ~14.3 | ~6.6 | ~20.9 |
| 4 | ~5.9  | ~6.3 | ~12.2 |


### Observations

With a single worker, jobs are processed sequentially. Queue delay increases linearly as each request waits for the previous one to finish.

With two workers, jobs are processed in pairs. Queue delay shows a step pattern where every two jobs are processed together before the next batch starts.

With four workers, jobs are processed in groups of four. Queue delay drops significantly and follows a clear batched execution pattern.

Processing time remains roughly constant across all configurations, indicating that the compute pipeline is stable and not the bottleneck.  

This behavior shows a clear separation between queue delay and processing time, indicating that system latency is dominated by scheduling constraints rather than computational inefficiency.


### Key Insights

- System latency is dominated by queue delay under low concurrency  
- Increasing worker concurrency reduces queue delay significantly  
- Processing time remains stable, confirming that the bottleneck is scheduling, not computation  
- The system exhibits batch-based execution behavior proportional to worker count  


### Notes on Real API Testing

Initial tests using real Gemini API calls showed similar queueing behavior, but were limited by rate limits under concurrent load. To ensure controlled and repeatable experiments, LLM inference was simulated with fixed latency during load testing.


## Design Decisions and Tradeoffs

### Why async processing was needed

The original version processed everything synchronously inside the Flask request. Deepgram transcription and Gemini summarization together take 10-30 seconds depending on audio length. Holding an HTTP request open that long is not acceptable in production: it ties up a worker thread, makes the app feel broken, and fails entirely if the client disconnects.

Moving to async processing meant the upload returns in under a second, the heavy work happens in a background process, and the frontend polls for the result independently.

### Celery was built first, then removed

The original async implementation used Celery with Redis (Upstash) as the broker. This is the production-correct approach: Celery gives you distributed workers, task retries, visibility into the queue, and independent scaling of processing capacity. The full Celery implementation is preserved on the `celery-arch` branch for reference.

It was removed for the deployed version for one reason: Render free tier has a 512MB memory limit per service. Running Gunicorn and a Celery worker in the same container pushed memory usage over the limit and crashed the service on startup. Splitting them into two separate services is the right fix, but Render free tier does not support background worker services.

The deployed version replaces Celery with Python threading. A daemon thread is started per upload and runs the same processing logic. This works correctly for a single-server demo. It would not be appropriate at production scale because threads share memory with the web process, there is no queue visibility, and a server restart loses any in-flight jobs. At scale, the Celery architecture on the `celery-arch` branch is the right path forward.

### Why RQ was considered and rejected

RQ was the first choice because it is simpler to set up than Celery. It failed on Windows because it depends on Unix-only process forking and signal handling. Celery with `--pool=solo` works correctly on Windows and on Linux-based production servers without any changes.

### Why APScheduler instead of Celery Beat

The stale job detector needs to run periodically to mark meetings stuck at `processing` as `failed`, for example when a worker crashes mid-task. Celery Beat would have required a separate process alongside Flask, the Celery worker, and Redis. APScheduler runs inside the Flask process as a background thread, which is sufficient for a task that runs every 10 minutes and does a simple database query. There is no need for the additional overhead at this scale.

### Why Neon instead of Render PostgreSQL

Render free PostgreSQL databases are automatically deleted after 90 days. Neon offers a free PostgreSQL tier with no expiry. Since the schema is recreated automatically on startup via `create_all()`, migrating was a single environment variable change with no data migration required.

### Session-based isolation without authentication

The app uses a UUID stored in the Flask session cookie to isolate each browser's meetings. There is no login system. Every upload is tagged with the session UUID, and all queries are filtered by it. This is sufficient for a demo app where the goal is to prevent one user from seeing another user's history, without the overhead of building a full auth system.

### Failure handling 

Every failure point has an explicit outcome. If transcription fails, the meeting is marked `failed` immediately. If Gemini returns malformed JSON, the system retries up to two times before giving up. If the retry limit is exhausted, the failure is recorded with a reason and not silently converted into a partial result. Meeting updates and task inserts happen in a single database transaction, so there is no state where a meeting shows `success` but has no tasks.

### Database reliability

The deployed system uses Neon PostgreSQL, which automatically suspends idle connections on the free tier. To prevent failures caused by stale connections, SQLAlchemy is configured with connection health checks (`pool_pre_ping`) and periodic connection recycling (`pool_recycle`).

All database writes are wrapped in a `safe_commit()` helper that performs rollback and retry logic if the connection temporarily fails. This prevents transient infrastructure issues from crashing the request lifecycle or background worker threads.

### What breaks at 1000 meetings per day

At that volume, a few things would need to change:

- A single background thread per request would become a bottleneck and a stability risk. The Celery architecture with multiple workers pulling from a Redis queue is the correct fix.
- The `uploads/` folder on a local or ephemeral filesystem would fill up or disappear on redeploy. Audio files would need to move to object storage like S3 or Cloudflare R2.
- PostgreSQL with default settings can handle this load, but queries against the `tasks` table without additional indexing would slow down as the table grows. Indexes on `owner`, `priority`, and `deadline_parsed` would be needed.
- The stale job detector running every 10 minutes on a full `meetings` table would benefit from a composite index on `processing_status` and `created_at` together.

### Cost estimate per meeting

Based on a typical 30-minute meeting producing roughly 3000-4000 words of transcript:

- Deepgram: approximately $0.0043 per minute of audio, so $0.13 per 30-minute meeting
- Gemini 2.5 Flash: approximately $0.00015 per 1000 input tokens. A 4000-word transcript is roughly 5000 tokens, costing around $0.00075 per meeting
- Total per meeting: under $0.15

At 1000 meetings per day, that is roughly $150/day in API costs, not counting infrastructure.



## Observability

Every processed meeting records the following metrics to the `meeting_metrics` table:

- `processing_time_seconds`: end-to-end time from job pickup to completion
- `transcript_word_count`: number of words in the transcript sent to Gemini
- `gemini_retry_count`: how many times Gemini needed to be retried (0 means first attempt succeeded)
- `status`: success or failed
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

- `queue_delay_seconds`: time between meeting creation and worker pickup (used to measure queue latency under load)

### Failure Handling

Failure types observed:
- Rate limit (429)
- External API failures

Retry strategy:
- Exponential backoff
- Max retries: 2

Observations:
- Failures were primarily due to external API limits
- System correctly records failure reasons and avoids partial writes

## Deployment Notes

The live deployment runs on Render free tier with Neon PostgreSQL.

Render free tier does not support background worker services. The Celery-based architecture built for this project exceeded the 512MB memory limit when running Gunicorn and a Celery worker in the same container. The deployed version uses Python threading instead. The full Celery + Redis implementation is preserved on the `celery-arch` branch.

Because Neon suspends compute when idle on the free tier, database connections can occasionally become stale. The application configures SQLAlchemy connection pooling with health checks to automatically detect and refresh dropped connections. This prevents errors such as `SSL connection has been closed unexpectedly` during long-running processing jobs.

The database schema is created automatically on startup via `init_db()`. Redeployment to a new database requires only updating the `DATABASE_URL` environment variable.
