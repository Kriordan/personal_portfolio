import os


BASEDIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'development'

WTF_CSRF_ENABLED = True

DATABASE = 'portfolio.db'
DATABASE_PATH = os.path.join(BASEDIR, DATABASE)
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_PATH
SQLALCHEMY_TRACK_MODIFICATIONS = True

S3_BUCKET = 'jobwizard-test'
S3_LOCATION = 'http://{}.s3.amazonaws.com/'.format(S3_BUCKET)

DEBUG = True
