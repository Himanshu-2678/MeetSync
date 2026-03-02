import os
import json
import logging
from google import genai
from pydantic import BaseModel, field_validator, ValidationError
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")

logger = logging.getLogger(__name__)

class Task(BaseModel):
    task: str
    owner: str
    deadline: str
    priority: str
    dependencies: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        allowed = {"High", "Medium", "Low"}
        normalized = v.strip().capitalize()
        if normalized not in allowed:
            raise ValueError(f"priority must be one of {allowed}, got '{v}'")
        return normalized

    @field_validator("task", "owner", "deadline", "dependencies")
    @classmethod
    def must_be_non_empty_string(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field must be a non-empty string")
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
      "owner": "Person responsible, or 'Unassigned' if not mentioned",
      "deadline": "Deadline if mentioned, or 'Not specified'",
      "priority": "High or Medium or Low — infer from context",
      "dependencies": "Any task or condition this depends on, or 'None'"
    }}
  ]
}}

Rules:
- summary must be detailed and cover all discussed topics
- tasks must be a list; if no tasks exist, return an empty list []
- priority must be exactly one of: High, Medium, Low
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
                "retry_count": attempt - 1}

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
        "error": f"Schema validation failed after {MAX_ATTEMPTS} attempts. Last error: {last_error}",
        "summary": None,
        "tasks": [],
        "retry_count": attempt - 1}