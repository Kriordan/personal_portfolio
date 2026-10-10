import json
import os
from datetime import timedelta

WTF_CSRF_ENABLED = True

SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

db_uri = os.getenv("DATABASE_URL")
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
SQLALCHEMY_DATABASE_URI = db_uri
SQLALCHEMY_TRACK_MODIFICATIONS = True

RATELIMIT_STORAGE_URI = "memory://"

MAILERSEND_API_KEY = os.getenv("MAILERSEND_API_KEY")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL")

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
YOUTUBE_CREDENTIALS_KEY = os.getenv("YOUTUBE_CREDENTIALS_KEY")
YOUTUBE_OAUTH_REDIRECT_URI = os.getenv(
    "YOUTUBE_OAUTH_REDIRECT_URI", "https://www.keithriordan.com/oauth/oauth2callback"
)
