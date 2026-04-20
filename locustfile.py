from locust import HttpUser, task, between
import os

class MeetSyncUser(HttpUser):
    host = "http://localhost:5000"
    wait_time = between(1, 2)

    def on_start(self):
        self.file_path = os.path.join(
            os.path.dirname(__file__),
            "uploads",
            "TTS meeting text-to-speech.mp3"
        )

        # preload file into memory
        with open(self.file_path, "rb") as f:
            self.file_data = f.read()

        self.filename = os.path.basename(self.file_path)

    @task
    def upload_meeting(self):
        with self.client.post(
            "/",
            files={"audio": (self.filename, self.file_data, "audio/mpeg")},
            catch_response=True
        ) as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with {response.status_code}")