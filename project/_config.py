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

# Practice sessions stay off until explicitly enabled; migrations run on deploy regardless.
LEARNING_PRACTICE_ENABLED = os.getenv("LEARNING_PRACTICE_ENABLED") == "1"
LEARNING_EXPORT_MAX_BYTES = int(os.getenv("LEARNING_EXPORT_MAX_BYTES", str(32 * 1024 * 1024)))
# AI replies in practice sessions: off until enabled, and only for the one verified account named here.
# The provider key (LEARNING_OPENAI_API_KEY) is read from the environment at call time, never from config.
LEARNING_AI_ENABLED = os.getenv("LEARNING_AI_ENABLED") == "1"
LEARNING_AI_OWNER_EMAIL = os.getenv("LEARNING_AI_OWNER_EMAIL")
LEARNING_AI_PROVIDER = os.getenv("LEARNING_AI_PROVIDER", "openai")
LEARNING_AI_MODEL = os.getenv("LEARNING_AI_MODEL")
LEARNING_AI_SELECTOR_MODEL = os.getenv("LEARNING_AI_SELECTOR_MODEL")
# Sent with both calls; set it with the model, since the evaluation measures the pair.
LEARNING_AI_REASONING_EFFORT = os.getenv("LEARNING_AI_REASONING_EFFORT")
LEARNING_AI_FEEDBACK_MODEL = os.getenv("LEARNING_AI_FEEDBACK_MODEL")
LEARNING_AI_FEEDBACK_REASONING_EFFORT = os.getenv("LEARNING_AI_FEEDBACK_REASONING_EFFORT")
LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS = int(os.getenv("LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS", "4000"))
LEARNING_AI_SERVICE_TIER = os.getenv("LEARNING_AI_SERVICE_TIER", "default")
LEARNING_AI_MONTHLY_CAP_USD = float(os.getenv("LEARNING_AI_MONTHLY_CAP_USD", "50"))
LEARNING_AI_WARN_USD = float(os.getenv("LEARNING_AI_WARN_USD", "40"))

# Only this operator-generated policy enables the private hosted pilot. It pins
# exact drafts, the one verified owner, and the original cross-month allowance.
from project.learning.hosted_pilot import settings as _hosted_settings
globals().update(_hosted_settings(os.environ))

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
