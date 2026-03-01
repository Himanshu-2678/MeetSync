import os
from dotenv import load_dotenv
load_dotenv()

from database.connection import engine
from database.models import Base

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Tables created")

if __name__ == "__main__":
    init_db()