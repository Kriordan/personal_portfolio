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

import datetime
from http import HTTPStatus

from dotenv import find_dotenv, load_dotenv
from flask import Flask, render_template

from project.account.views import account_blueprint
from project.foyer.views import foyer_blueprint
from project.jobwizard.views import jobwizard_blueprint
from project.library.views import library_blueprint
from project.oauth.views import oauth_blueprint
from project.wishlist.views import wishlist_blueprint

from .commands import create_user, reset_db, sync_yt_subs
from .csp import csp
from .database import db
from .extensions import login_manager, migrate, scheduler, talisman
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
    register_errorhandlers(app)
    register_tasks()
    register_events()

    return app


def register_extensions(app):
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "account.login"

    @login_manager.user_loader
    def load_user(id):
        return db.session.get(User, int(id))

    migrate.init_app(app, db)
    scheduler.init_app(app)
    talisman.init_app(app, content_security_policy=csp)


def register_blueprints(app):
    app.register_blueprint(account_blueprint)
    app.register_blueprint(foyer_blueprint)
    app.register_blueprint(jobwizard_blueprint)
    app.register_blueprint(library_blueprint)
    app.register_blueprint(oauth_blueprint)
    app.register_blueprint(wishlist_blueprint)


def register_commands(app):
    app.cli.add_command(create_user)
    app.cli.add_command(reset_db)
    app.cli.add_command(sync_yt_subs)


def register_jinja_env(app):
    app.jinja_env.globals.update(
        {
            "now": datetime.datetime.now().strftime("%Y"),
        }
    )


def register_tasks():
    from . import tasks  # noqa

    scheduler.start()


def register_events():
    from . import events


def register_errorhandlers(app):
    """Register error handlers with the Flask application."""

    def render_error(e):
        return render_template("%s.html" % e.code), e.code

    for e in [
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
    ]:
        app.errorhandler(e)(render_error)
