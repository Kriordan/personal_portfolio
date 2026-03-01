import json
import os

WTF_CSRF_ENABLED = True

SECRET_KEY = os.getenv("SECRET_KEY")

db_uri = os.getenv("DATABASE_URL")
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
SQLALCHEMY_DATABASE_URI = db_uri
SQLALCHEMY_TRACK_MODIFICATIONS = True

MAILERSEND_API_KEY = os.getenv("MAILERSEND_API_KEY")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL")

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")
