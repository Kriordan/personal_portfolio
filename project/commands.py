import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import upgrade

from project.library.jobs import sync_playlists_and_videos

from .database import db
from .models import User


@click.command(name="create-user")
@click.option("--email", prompt=True, help="The email of the user")
@click.option("--username", prompt=True, help="The username of the user")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="The password of the user",
)
@with_appcontext
def create_user(email, username, password):
    """Create a new user"""
    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"User {username} created successfully")


@click.command(name="reset-db")
@with_appcontext
def reset_db():
    """Drop and recreate the database."""
    db.drop_all()
    db.create_all()
    upgrade()
    click.echo("Database has been reset and recreated successfully.")


@click.command(name="sync-yt-subs")
def sync_yt_subs():
    """Sync YouTube subscriptions and playlists"""
    with current_app.app_context():
        sync_playlists_and_videos()
        click.echo("YouTube playlists and subs synced successfully.")
