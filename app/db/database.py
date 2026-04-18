import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv, find_dotenv

# Load .env searching from the current file's directory upwards
load_dotenv(find_dotenv())

user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "fodes5")
host = os.getenv("DB_HOST", "127.0.0.1")
port = os.getenv("DB_PORT", "3307")
database = os.getenv("DB_NAME", "FODES2")

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://{0}:{1}@{2}:{3}/{4}".format(
    user, password, host, port, database
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,   # verifica la conexión antes de usarla
    pool_recycle=1800,    # recicla conexiones cada 30 min (antes del wait_timeout de MySQL)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        print("Connected to database")
        yield db
    finally:
        print("Disconnected from database")
        db.close()
