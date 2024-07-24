import click
from flask.cli import with_appcontext

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
