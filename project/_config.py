import os


basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'development'

WTF_CSRF_ENABLED = True

DATABASE = 'portfolio.db'
DATABASE_PATH = os.path.join(basedir, DATABASE)
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_PATH

MAIL_SERVER = 'smtp.sendgrid.net'
MAIL_PORT = 587
MAIL_USERNAME = os.environ.get('SENDGRID_USERNAME')
MAIL_PASSWORD = os.environ.get('SENDGRID_PASSWORD')

DEBUG = True
