# MeetSync: AI Meeting Minutes Generator

MeetSync is an AI-powered meeting minutes generator I built to help users quickly extract key insights from meeting audio.
The idea was simple: instead of listening to long recordings or writing notes manually, users should be able to upload meeting audio and instantly get clear, structured minutes with decisions and action items.


## Why I built this

In most meetings, the real value lies in:
- what was discussed
- what decisions were made
- who is responsible for what

I created MeetSync to automate this process and turn raw meeting audio into actionable meeting minutes that can be shared immediately after a meeting.

## Features

- Upload meeting audio files (WAV / MP3)
- Automatic speech-to-text transcription
- AI-generated structured meeting minutes:
  - Main discussion topics
  - Key decisions
  - Action items with ownership (if present)
- Downloadable meeting summary (TXT)
- Clean, minimal UI optimized for readability
- Secure session-based handling of summaries

---

## How It Works

1. The user uploads a meeting audio file  
2. The audio is transcribed into text  
3. The transcript is processed by an LLM to generate structured meeting minutes  
4. The summary is displayed in the UI and can be downloaded  

---

## Tech Stack

- Backend: Python, Flask  
- Speech-to-Text: Whisper  
- LLM: Google Gemini API  
- Frontend: HTML, CSS  
- Session Management: Flask sessions  

## Project Structure
```
MeetSync/
│
├── app.py # Flask application entry point
├── summarizer.py # Gemini based meeting minutes generation
├── templates/
│ └── index.html # Frontend UI
├── static/ # Static assets (if any)
├── uploads/ # Uploaded audio files
├── .env # Environment variables (not committed)
├── requirements.txt
└── README.md
```
## Screenshot of the final UI -

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Himanshu-2678/MeetSync.git
cd MeetSync
```
2. Create and activate a virtual environment
```bash
python -m venv venv
```
- for Windows
```
venv\Scripts\activate
```
- for macOS / Linux
```
source venv/bin/activate
```
3. Install dependencies
```
pip install -r requirements.txt
```
4. Configure environment variables
Create a .env file in the project root:
```
GEMINI_API_KEY=your_gemini_api_key
FLASK_SECRET_KEY=your_secret_key
```

5. Run the application
```
python app.py
```




