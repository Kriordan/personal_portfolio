import os


WTF_CSRF_ENABLED = True

SECRET_KEY = os.getenv('SECRET_KEY')

db_uri = os.getenv("DATABASE_URL")
if db_uri.startswith("postgres://"):
    print("Replacing postgres URI scheme with postgresql")
    db_uri.replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URI = db_uri
SQLALCHEMY_TRACK_MODIFICATIONS = True

DEBUG = False
