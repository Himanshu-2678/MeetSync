from flask import Flask, render_template, request
import os
from summarizer import summarize_text
from transcribe import transcribe_audio

## defining the app
app = Flask(__name__)

upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)

@app.route("/")
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    audio_file = request.files['audio']
    file_path = os.path.join(upload_folder, audio_file.filename)
    audio_file.save(file_path)

    transcript = transcribe_audio(file_path)
    summary = summarize_text(transcript)

    return summary

## Driver Code
if __name__ == "__main__":
    app.run(debug=True)