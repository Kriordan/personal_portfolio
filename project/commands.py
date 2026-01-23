import click
from flask.cli import with_appcontext
from flask_migrate import upgrade

from project.library.jobs import sync_playlists_and_videos

from .database import db
from .models import User
from .learning.evaluation import evaluate_scheduler


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


@click.command(name="reset-password")
@click.option("--email", prompt=True, help="The email of the user")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="The new password for the user",
)
@with_appcontext
def reset_password(email, password):
    """Reset password for an existing user"""
    user = db.session.query(User).filter_by(email=email).first()
    if user is None:
        click.echo(f"Error: User with email {email} not found", err=True)
        return
    user.set_password(password)
    db.session.commit()
    click.echo(f"Password reset successfully for user {user.username}")


@click.command(name="reset-db")
@with_appcontext
def reset_db():
    """Drop and recreate the database."""
    db.drop_all()
    db.create_all()
    upgrade()
    click.echo("Database has been reset and recreated successfully.")


@click.command(name="sync-yt-subs")
@with_appcontext
def sync_yt_subs():
    """Sync YouTube subscriptions and playlists"""
    sync_playlists_and_videos()
    click.echo("YouTube playlists and subs synced successfully.")


@click.command(name="eval-scheduler")
@click.option("--user-id", required=True, type=int)
@click.option("--days", default=30, type=int)
@with_appcontext
def eval_scheduler(user_id, days):
    """Evaluate scheduler performance."""
    results = evaluate_scheduler(user_id, days)
    click.echo(f"Success rate: {results['success_rate']:.2%}")
    click.echo(f"Lapse rate: {results['lapse_rate']:.2%}")
    click.echo(f"Reviews per day: {results['reviews_per_day']:.2f}")
    click.echo(f"Avg half-life growth: {results['avg_half_life_growth']:.2f}")

    if results["by_scheduler"]:
        click.echo("\nBy scheduler version:")
        for version, metrics in results["by_scheduler"].items():
            click.echo(f"- {version}")
            click.echo(f"  Success rate: {metrics['success_rate']:.2%}")
            click.echo(f"  Lapse rate: {metrics['lapse_rate']:.2%}")
            click.echo(
                f"  Avg half-life growth: {metrics['avg_half_life_growth']:.2f}"
            )
