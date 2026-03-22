# MeetSync
 
**An observable, fault-tolerant AI pipeline for converting meeting audio into structured decisions and tasks.**
 
MeetSync automates the process of turning raw meeting audio into actionable meeting minutes — with a structured summary, key decisions, and action items extracted and persisted to a database.
 
## Architecture Diagram

![MeetSync Architecture](assets/architecure_diagram_meetsync.png)

## Why I built this

In most meetings, the real value lies in what was discussed, what decisions were made, and who is responsible for what.

MeetSync automates this process and turns raw meeting audio into actionable meeting minutes that can be shared immediately after a meeting.


## Demo

[![MeetSync-Home](assets/meetsync_main_page.png)](https://youtu.be/fYaQ3g40ehY)
[![MeetSync-History](assets/meetsync_summary.png)](https://youtu.be/fYaQ3g40ehY)
[![tasks](assets/tasks.png)](https://youtu.be/fYaQ3g40ehY)
_click the image to play the video demo._


## Features

- Upload meeting audio files (WAV / MP3)
- Automatic speech-to-text transcription via Deepgram Nova-2
- AI-generated structured meeting minutes with summary, key decisions, and action items
- Each action item extracted with: owner, deadline (raw + parsed), and priority (only when explicitly stated)
- Async processing: upload returns instantly, result appears when ready
- Meeting history page with processing status and time
- Cross-meeting task search with filters for owner, status, and overdue tasks
- Downloadable meeting summary (TXT)
- Session-based isolation so each browser sees only its own meetings
- Clean, minimal UI optimized for readability
- Persistent storage of all meetings, transcripts, and tasks in PostgreSQL

 

## How It Works

1. The user uploads a meeting audio file
2. Flask saves the file and immediately inserts a meeting record with status `processing`
3. A background worker thread is started to process the meeting asynchronously
4. The user is redirected to a polling page that checks status every 3 seconds
5. The worker transcribes the audio using Deepgram, then calls Gemini to extract structured minutes
6. Gemini response is validated against a strict Pydantic schema before being accepted
7. On success, the meeting and tasks are saved to PostgreSQL in a single transaction
8. The polling page detects the success and redirects to the result page automatically
 
 

## Tech Stack

- **Backend:** Python, Flask
- **Async Processing:** Python threading
- **Speech-to-Text:** Deepgram API (Nova-2, numerals enabled)
- **LLM:** Google Gemini 2.5 Flash
- **Schema Validation:** Pydantic
- **Database:** PostgreSQL with SQLAlchemy (hosted on Neon)
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Scheduling:** APScheduler
- **Deployment:** Render
 


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
|-- requirements.txt              # Required libraries and depencies
|-- LICENSE                       # Official MIT LICENSE
`-- README.md
```


## System Evaluation

The system was evaluated across reliability, correctness, and cost. Latency, retries, and failure modes are measured per meeting via structured metrics stored in the `meeting_metrics` table. Output quality was evaluated against real meeting transcripts. Cost per meeting was estimated using real API pricing and observed token usage.

### Reliability

Every meeting job records whether it succeeded or failed, how long it took, and whether Gemini needed to be retried. This makes it possible to query the failure rate and retry patterns directly from the database rather than guessing.

In practice, Gemini 2.5 Flash returned valid JSON on the first attempt for most test meetings. The Pydantic validation layer never rejected a response that the JSON parser accepted, which means schema adherence is strong when the prompt is well formed.

The stale job detector was verified by manually inserting a meeting row with a `created_at` timestamp 15 minutes in the past and confirming it was marked failed on the next app startup. Worker crash recovery works as designed.

### Output Quality

Output quality was evaluated by uploading real meeting audio where the content was already known, then comparing the generated summary and task list against what was actually discussed.

The summary consistently captured the main topics and decisions. Task extraction was accurate when speaker attribution was clear in the audio. When multiple people spoke without introduction, owner assignment defaulted to Unassigned rather than guessing a name.

Deadline extraction worked well for specific phrases like "by Friday" or "end of next week." Vague phrases like "soon" or "as soon as possible" correctly produced a null in `deadline_parsed` with the original text preserved in `deadline_raw`.

### Performance

Processing time scales with audio length. A one-minute file completed in around 7-15 seconds. A 10-15 minute meeting takes around 30-35 seconds. The bottleneck is Deepgram transcription, not Gemini. Because processing is async, this has no impact on the user-facing response time.

### Cost

A typical 30-minute meeting costs under $0.15: around $0.13 for Deepgram transcription and under $0.01 for Gemini token usage. At 1000 meetings per day, API costs would be roughly $150/day. The dominant cost is transcription, not the LLM.

The system prioritizes correctness over forced success — failures are surfaced explicitly rather than silently ignored.

### Known Limitations

These are intentional tradeoffs, not bugs.

**Speech-to-text errors (Deepgram)**
Deepgram occasionally mishears technical terms (`auto-ML` becomes `auto amount`) and spoken dates (`March 29` becomes `My twenty nine`). These are transcription-layer errors, not extraction errors. The system stores what Deepgram returns without correction.

Spoken dates are particularly unreliable:

| Spoken | Transcribed |
 |---|---|
| "March twenty seventh" | "March t" (truncated mid-word) |
| "March twenty nine" | "My twenty nine" (mishearing) |
| "March twenty five" | "Mark twenty five" (phonetic substitution) |

Switching to `model=nova-2` with `numerals=true` reduces this but does not eliminate it. The workaround is for speakers to say dates numerically ("March 27th") rather than as words.

**Ambiguous deadlines**
Natural language like "March thirty" leads to inconsistent parsing. `deadline_raw` always stores the exact spoken phrase. `deadline_parsed` attempts resolution via dateparser and stores null on failure. Raw text is never silently discarded.

**Multiple owners**
Tasks sometimes get assigned to multiple people ("Marcus / Sarah"). The first mentioned person is treated as the primary owner. Storing multiple owners would break filtering and search.

**Implicit tasks**
Some decisions discussed in meetings are not explicitly structured as action items. The system relies on explicit ownership language in the transcript. If no owner is stated, the task is marked Unassigned rather than guessing.

**Priority inference**
Priority is only extracted when explicitly stated by a speaker. It is null by default and never inferred from context or tone. A null priority is more honest than a fabricated one.

**Speaker diarization**
The system does not identify who said what. Task ownership depends entirely on whether the transcript contains explicit assignment language.

 

## Design Decisions and Tradeoffs

### Why async processing was needed

The original version processed everything synchronously inside the Flask request. Deepgram transcription and Gemini summarization together take 10-30 seconds depending on audio length. Holding an HTTP request open that long ties up a worker thread, makes the app feel broken, and fails entirely if the client disconnects.

Moving to async processing meant the upload returns in under a second, the heavy work happens in a background thread, and the frontend polls for the result independently.

### Celery was built first, then removed

The original async implementation used Celery with Redis (Upstash) as the broker. This is the production-correct approach: Celery gives you distributed workers, task retries, visibility into the queue, and independent scaling. The full Celery implementation is preserved on the `celery-arch` branch.

It was removed for the deployed version because Render free tier has a 512MB memory limit per service. Running Gunicorn and a Celery worker in the same container exceeded this limit and crashed the service on startup. The deployed version uses Python threading instead.

Threading works correctly for a single-server demo. It would not be appropriate at production scale because threads share memory with the web process, there is no queue visibility, and a server restart loses any in-flight jobs. The Celery architecture is the right path forward at scale.

### Why RQ was considered and rejected

RQ was the first choice because it is simpler to set up than Celery. It failed on Windows because it depends on Unix-only process forking and signal handling. Celery with `--pool=solo` works correctly on both Windows and Linux without changes.

### Why APScheduler instead of Celery Beat

The stale job detector needs to run periodically to mark stuck meetings as failed. Celery Beat would have required a separate process alongside Flask, the Celery worker, and Redis. APScheduler runs inside the Flask process as a background thread, which is sufficient for a task that runs every 10 minutes and does a simple database query.

### Why Neon instead of Render PostgreSQL

Render free PostgreSQL databases are automatically deleted after 90 days. Neon offers a free PostgreSQL tier with no expiry. Migrating was a single environment variable change.

### Why priority is nullable

Earlier versions forced a High / Medium / Low classification on every task. This led to hallucinated priority values where the model invented urgency that was never stated. Priority is now null by default and only populated when the transcript explicitly signals it.

### Session-based isolation without authentication

The app uses a UUID stored in the Flask session cookie to isolate each browser's meetings. There is no login system. Every upload is tagged with the session UUID and all queries are filtered by it. Sufficient for a demo without the overhead of a full auth system.

### Failure handling

Every failure point has an explicit outcome. If transcription fails, the meeting is marked failed immediately. If Gemini returns malformed JSON, the system retries up to two times before giving up. If the retry limit is exhausted, the failure is recorded with a reason and not silently converted into a partial result. Meeting updates and task inserts happen in a single database transaction, so there is no state where a meeting shows success but has no tasks.

### Database reliability

Neon PostgreSQL automatically suspends idle connections on the free tier. SQLAlchemy is configured with connection health checks (`pool_pre_ping`) and periodic connection recycling (`pool_recycle`) to handle this.

All database writes are wrapped in a `safe_commit()` helper that performs rollback and retry logic if the connection temporarily fails. This prevents transient infrastructure issues from crashing the request lifecycle or background worker threads.

### What breaks at 1000 meetings per day

- A single background thread per request becomes a bottleneck. The Celery architecture with multiple workers pulling from a Redis queue is the correct fix.
- The `uploads/` folder on a local filesystem fills up or disappears on redeploy. Audio files would need to move to object storage like S3 or Cloudflare R2.
- Queries against the `tasks` table would slow down without additional indexes on `owner`, `priority`, and `deadline_parsed`.
- The stale job detector would benefit from a composite index on `processing_status` and `created_at` together.

### Cost estimate per meeting

Based on a typical 30-minute meeting producing roughly 3000-4000 words of transcript:

- Deepgram: ~$0.0043 per minute, so ~$0.13 per 30-minute meeting
- Gemini 2.5 Flash: ~$0.00015 per 1000 input tokens, so ~$0.00075 per meeting
- Total: under $0.15 per meeting

At 1000 meetings per day, that is roughly $150/day in API costs, not counting infrastructure.

 

## Observability

Every processed meeting records the following to the `meeting_metrics` table:

- `processing_time_seconds`: end-to-end time from job pickup to completion
- `transcript_word_count`: number of words sent to Gemini
- `gemini_retry_count`: how many times Gemini needed to be retried (0 means first attempt succeeded)
- `status`: success or failed
- `failure_reason`: exact reason if the job failed

Stats on the homepage are computed live from this table, not hardcoded.

```sql
-- Average processing time for successful meetings
SELECT ROUND(AVG(processing_time_seconds)::numeric, 2) AS avg_seconds
FROM meeting_metrics WHERE status = 'success';

-- Meetings that required Gemini retries
SELECT meeting_id, gemini_retry_count FROM meeting_metrics WHERE gemini_retry_count > 0;

-- Failure rate
SELECT status, COUNT(*) FROM meeting_metrics GROUP BY status;
```

 

## Deployment Notes

The live deployment runs on Render free tier with Neon PostgreSQL.

Render free tier does not support background worker services. The Celery-based architecture exceeded the 512MB memory limit when running Gunicorn and a Celery worker together. The deployed version uses Python threading instead. The full Celery + Redis implementation is preserved on the `celery-arch` branch.

Because Neon suspends compute when idle, database connections can occasionally become stale. SQLAlchemy connection pooling with health checks handles this automatically, which prevents errors like `SSL connection has been closed unexpectedly` during long-running processing jobs.

The database schema is created automatically on startup via `init_db()`. Redeploying to a new database requires only updating the `DATABASE_URL` environment variable.


## Roadmap

These are planned improvements, not missing features. The current system is intentionally scoped.

**Model Resilience**
Primary model is Gemini 2.5 Flash. A fallback to a secondary model (Mistral / Llama via API) is planned for cases where Gemini fails or returns invalid output after retries.

**Long Transcript Handling**
Currently the full transcript is sent to Gemini in one shot. For meetings over 60 minutes, this approaches token limits. Planned fix is to chunk the transcript, summarize each chunk, then merge into a final output.

**Observability Dashboard**
Metrics are already tracked in `meeting_metrics`. A simple `/dashboard` page showing processing time distribution, retry counts, and success vs failure over time is planned.

**Production Deployment**
Threading replaced Celery due to Render free tier memory limits. The Celery + Redis architecture is already built on the `celery-arch` branch and will replace threading when moving off the free tier.



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
