import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mini_shop")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 100 * 1024 * 1024))
    ALLOWED_VIDEO_EXT = set(os.getenv("ALLOWED_VIDEO_EXT", "mp4,webm,ogg").split(","))
    ALLOWED_FILE_EXT = set(os.getenv("ALLOWED_FILE_EXT", "pdf,zip,docx,txt").split(","))
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
