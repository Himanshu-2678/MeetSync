from celery import Celery
import os
import ssl
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "meetsync",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.broker_transport_options = {
    "ssl_cert_reqs": ssl.CERT_NONE
}
celery_app.conf.redis_backend_use_ssl = {
    "ssl_cert_reqs": ssl.CERT_NONE
}