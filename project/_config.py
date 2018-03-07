import os


basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'development'

WTF_CSRF_ENABLED = True

DATABASE = 'portfolio.db'
DATABASE_PATH = os.path.join(basedir, DATABASE)
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_PATH

DEBUG = True
