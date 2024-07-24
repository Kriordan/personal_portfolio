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

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import find_dotenv, load_dotenv
from flask import Flask, render_template, request

from project.account.views import account_blueprint
from project.foyer.views import foyer_blueprint
from project.jobwizard.views import jobwizard_blueprint
from project.wishlist.views import wishlist_blueprint

from .commands import create_user
from .database import db
from .extensions import login_manager, migrate, talisman
from .jobs.getyoutubedata import get_yt_playlist_data
from .models import User

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE, override=True)


def create_app(test_config=None):
    app = Flask(__name__)

    if test_config is None:
        app.config.from_pyfile("_config.py")
    else:
        app.config.from_mapping(test_config)

    register_extensions(app)
    register_blueprints(app)
    register_commands(app)
    register_jinja_env(app)
    # register_errorhandlers(app)

    # scheduler = BackgroundScheduler()
    # scheduler.add_job(func=get_yt_playlist_data, trigger="interval", days=1)
    # scheduler.start()
    # atexit.register(lambda: scheduler.shutdown())

    return app


def register_extensions(app):
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "account.login"

    @login_manager.user_loader
    def load_user(id):
        return db.session.get(User, int(id))

    migrate.init_app(app, db)

    csp = {
        "default-src": ["'self'"],
        "style-src": ["'self'", "https://fonts.googleapis.com", "'unsafe-inline'"],
        "script-src": [
            "'self'",
            "https://www.googletagmanager.com",
            "https://*.hotjar.com",
            "https://cdn.jsdelivr.net",  # Add this line for AlpineJS CDN
            "'unsafe-inline'",
        ],
        "img-src": [
            "'self'",
            f'https://{os.getenv("WISHLIST_S3_BUCKET")}.s3.amazonaws.com',
        ],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "connect-src": [
            "'self'",
            "https://*.google-analytics.com",
            "https://stats.g.doubleclick.net",
            "https://*.hotjar.com",
            "https://*.hotjar.io",
            "wss://*.hotjar.com",
        ],
    }
    talisman.init_app(app, content_security_policy=csp)


def register_blueprints(app):
    app.register_blueprint(account_blueprint)
    app.register_blueprint(foyer_blueprint)
    app.register_blueprint(jobwizard_blueprint)
    app.register_blueprint(wishlist_blueprint)


def register_commands(app):
    app.cli.add_command(create_user)


def register_jinja_env(app):
    app.jinja_env.globals.update(
        {
            "now": datetime.datetime.now().strftime("%Y"),
        }
    )


# @app.context_processor
# def inject_now():
#     return {"now": datetime.datetime.now().strftime("%Y")}

# @app.errorhandler(404)
# def not_found(error):
#     if app.debug is not True:
#         now = datetime.datetime.now()
#         r = request.url
#         with open("error.log", "a") as f:
#             current_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
#             f.write("\n404 error at {}: {}".format(current_timestamp, r))
#     return render_template("404.html"), 404

# @app.errorhandler(500)
# def internal_error(error):
#     db.session.rollback()
#     if app.debug is not True:
#         now = datetime.datetime.now()
#         r = request.url
#         with open("error.log", "a") as f:
#             current_timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
#             f.write("\n500 error at {}: {}".format(current_timestamp, r))
#     return render_template("500.html"), 500
