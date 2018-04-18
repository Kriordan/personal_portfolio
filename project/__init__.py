import datetime
import boto3
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sparkpost import SparkPost
from sparkpost.exceptions import SparkPostAPIException
from dotenv import load_dotenv, find_dotenv


ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)

app.config.from_pyfile('_config.py')

db = SQLAlchemy(app)
sp = SparkPost()
s3 = boto3.resource('s3')

from project.foyer.views import foyer_blueprint
from project.jobwizard.views import jobwizard_blueprint

app.register_blueprint(foyer_blueprint)
app.register_blueprint(jobwizard_blueprint)


@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now().strftime("%Y")}


@app.errorhandler(404)
def not_found(error):
    if app.debug is not True:
        now = datetime.datetime.now()
        r = request.url
        with open('error.log', 'a') as f:
            currrent_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
            f.write("\n404 error at {}: {}".format(current_timestamp, r))
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if app.debug is not True:
        now = datetime.datetime.now()
        r = request.url
        with open('error.log', 'a') as f:
            currrent_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
            f.write("\n500 error at {}: {}".format(current_timestamp, r))
    return render_template('500.html'), 500
