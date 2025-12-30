"""import whisper

model = whisper.load_model("base")

## function for transcribing audio
def transcribe_audio(file_path: str) -> str:
    ans = model.transcribe(file_path)
    return ans["text"]"""

import os
import requests

import logging

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

def transcribe_audio(file_path: str) -> str:
    with open(file_path, "rb") as audio_file:
        audio_bytes = audio_file.read()

    response = requests.post(
        "https://api.deepgram.com/v1/listen?punctuate=true&model=general",
        headers={
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/octet-stream",
        },
        data=audio_bytes
    )

    result = response.json()
    transcript = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
    logging.warning(f"DEEPGRAM STATUS: {response.status_code} {response.text}")

    return transcript