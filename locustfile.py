from locust import HttpUser, task
import os

class MeetSyncUser(HttpUser):
    host = "http://localhost:5000"

    def on_start(self):
        self.has_run = False

        file_path = os.path.join(
            os.path.dirname(__file__),
            "uploads",
            "TTS meeting text-to-speech.mp3"
        )

        with open(file_path, "rb") as f:
            self.file_data = f.read()

        self.filename = os.path.basename(file_path)

    @task
    def upload_once(self):
        if self.has_run:
            return

        self.has_run = True

        self.client.post(
            "/",
            files={"audio": (self.filename, self.file_data, "audio/mpeg")}
        )