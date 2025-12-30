from flask import Flask, render_template, request
from dotenv import load_dotenv
load_dotenv()
import os
from summarizer import summarize_text
from transcribe import transcribe_audio
import io
from flask import session, send_file

## defining the app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)

@app.route("/", methods = ["GET", "POST"])
def home():
    transcript = None
    summary = None

    if request.method == "POST":
        audio_file = request.files['audio']
        file_path = os.path.join(upload_folder, audio_file.filename)
        audio_file.save(file_path)

        transcript = transcribe_audio(file_path)
        summary = summarize_text(transcript)
        session['summary'] = summary
    return render_template('index.html', transcript=transcript, summary=summary)

@app.route("/download-summary")
def download_summary():
    summary_text = session.get('summary')   
    
    if not summary_text:
        return "No summary available for download.", 400
    buffer = io.BytesIO()
    buffer.write(summary_text.encode('utf-8'))
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="meeting_summary.txt", mimetype='text/plain')

## Driver Code
if __name__ == "__main__":
    app.run(debug=True)