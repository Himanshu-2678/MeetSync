import os
import json
import logging
from google import genai
from pydantic import BaseModel, field_validator, ValidationError
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")

logger = logging.getLogger(__name__)

class Task(BaseModel):
    task: str
    owner: str
    deadline_raw: str
    priority: Optional[str] = None
    dependencies: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v is None:
            return None
        allowed = {"High", "Medium", "Low"}
        normalized = v.strip().capitalize()
        if normalized not in allowed:
            return None  # don't crash, just drop it
        return normalized

    @field_validator("task", "owner", "dependencies")
    @classmethod
    def must_be_non_empty_string(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field must be a non-empty string")
        return v.strip()

    @field_validator("deadline_raw")
    @classmethod
    def clean_deadline(cls, v):
        if not isinstance(v, str) or not v.strip():
            return "Not specified"
        return v.strip()


class MeetingOutput(BaseModel):
    summary: str
    tasks: List[Task]

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("summary must be a non-empty string")
        return v.strip()


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MAX_ATTEMPTS = 2

PROMPT_TEMPLATE = """
You are generating professional meeting minutes with structured task extraction.

Return ONLY a valid JSON object with this exact structure (no markdown, no extra text, no code fences):

{{
  "summary": "A detailed paragraph summarizing the overall meeting discussion, key decisions, and outcomes.",
  "tasks": [
    {{
      "task": "Description of the task",
      "owner": "Person responsible, or 'Unassigned' if not explicitly named",
      "deadline_raw": "Deadline exactly as spoken in the transcript (e.g. 'by Wednesday night'), or 'Not specified'",
      "priority": "High or Medium or Low — ONLY if the transcript explicitly states urgency or importance. If not mentioned, return null.",
      "dependencies": "Any task or condition this depends on, or 'None'",
    }}
  ]
}}

Strict rules:
- Extract ALL tasks mentioned, including those listed in any recap or summary section of the transcript
- Do NOT infer or hallucinate priority — only set it if the speaker explicitly signals it
- deadline_raw must be the exact phrase from the transcript, not a reformatted date
- owner must be a name from the transcript, or 'Unassigned' — never invent a name
- summary must cover all topics discussed, all decisions made, and accurate durations or numbers
- tasks must be a list; if no tasks exist, return []
- Do NOT wrap output in markdown or code blocks
- Return raw JSON only

Transcript:
{transcript}
"""


def summarize_text(text: str) -> dict:
    if not text or len(text.split()) < 5:
        logger.warning("Input too short to summarize.")
        return {
            "status": "failed",
            "error": "Input transcript is too short.",
            "summary": None,
            "tasks": [],
            "retry_count": 0}

    prompt = PROMPT_TEMPLATE.format(transcript=text)
    last_error = None
    attempt = 0
    json_failures = 0
    validation_failures = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(f"Attempt {attempt}/{MAX_ATTEMPTS} — Calling Gemini API")

        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=prompt)
            
            raw = response.text.strip()

            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            logger.info(f"Attempt {attempt} — Raw output received ({len(raw)} chars)")

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                json_failures += 1
                last_error = f"JSONDecodeError: {str(e)}"
                logger.error(json.dumps({
                    "attempt": attempt,
                    "failure_reason": "JSON parse failed",
                    "error": str(e),
                    "raw_output": raw[:300]}))
                
                continue

            try:
                validated = MeetingOutput(**parsed)
            except ValidationError as e:
                validation_failures += 1
                errors = e.errors()
                last_error = f"Schema validation failed: {errors}"
                logger.error(json.dumps({
                    "attempt": attempt,
                    "failure_reason": "Schema validation failed",
                    "validation_errors": errors,
                    "raw_output": raw[:300]
                }, default=str))
                continue

            logger.info(json.dumps({
                "attempt": attempt,
                "status": "success",
                "task_count": len(validated.tasks)}))

            return {
                "status": "success",
                "summary": validated.summary,
                "tasks": [t.model_dump() for t in validated.tasks],
                "retry_count": attempt - 1,
                "json_failures": json_failures,
                "validation_failures": validation_failures
            }

        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(json.dumps({
                "attempt": attempt,
                "failure_reason": "Unexpected exception",
                "error": str(e)}))
            continue

    logger.error(json.dumps({
        "status": "failed",
        "error": "All attempts exhausted",
        "last_error": last_error}))

    return {
        "status": "failed",
        "error": f"...",
        "summary": None,
        "tasks": [],
        "retry_count": attempt - 1,
        "json_failures": json_failures,
        "validation_failures": validation_failures
    }