"""
This module initializes the Flask application and its configurations.

It sets up the database connection using SQLAlchemy, configures the S3 client 
for AWS, and schedules a background job to fetch YouTube playlist data every day.

It also registers blueprints for the 'foyer' and 'jobwizard' modules, and 
defines error handlers for 404 and 500 status codes.

Functions:
    inject_now: Injects the current year into the context for templates.
    not_found: Handles 404 errors.
    internal_error: Handles 500 errors.
"""

import atexit
import datetime
import os

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import find_dotenv, load_dotenv
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from .jobs.getyoutubedata import get_yt_playlist_data

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE, override=True)

app = Flask(__name__)

app.config.from_pyfile("_config.py")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

if os.getenv("ENV") == "development":
    session = boto3.Session(profile_name="personalportfolio")
    s3 = session.client("s3")
else:
    s3 = boto3.client("s3")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "account.login"

scheduler = BackgroundScheduler()
scheduler.add_job(func=get_yt_playlist_data, trigger="interval", days=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

from project.account.views import account_blueprint
from project.foyer.views import foyer_blueprint
from project.jobwizard.views import jobwizard_blueprint
from project.wishlist.views import wishlist_blueprint

app.register_blueprint(account_blueprint)
app.register_blueprint(foyer_blueprint)
app.register_blueprint(jobwizard_blueprint)
app.register_blueprint(wishlist_blueprint)


@app.context_processor
def inject_now():
    return {"now": datetime.datetime.now().strftime("%Y")}


@app.errorhandler(404)
def not_found(error):
    if app.debug is not True:
        now = datetime.datetime.now()
        r = request.url
        with open("error.log", "a") as f:
            current_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
            f.write("\n404 error at {}: {}".format(current_timestamp, r))
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if app.debug is not True:
        now = datetime.datetime.now()
        r = request.url
        with open("error.log", "a") as f:
            current_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
            f.write("\n500 error at {}: {}".format(current_timestamp, r))
    return render_template("500.html"), 500
