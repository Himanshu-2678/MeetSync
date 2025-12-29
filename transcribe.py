import whisper

model = whisper.load_model("base")

## function for transcribing audio
def transcribe_audio(file_path: str) -> str:
    ans = model.transcribe(file_path)
    return ans["text"]