from celery import Celery
import os
from dotenv import load_dotenv
load_dotenv()

celery_app = Celery(
    "meetsync",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["tasks"]  # 👈 this tells Celery where to find tasks
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)