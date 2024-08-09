"""This file defines the routes for the foyer blueprint."""

import json
from pathlib import Path

import yaml
from flask import Blueprint, current_app, render_template
from flask_login import login_required
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .email_templates import get_contact_email_content
from .forms import ContactForm

foyer_blueprint = Blueprint("foyer", __name__)


@foyer_blueprint.route("/")
def home():
    """Render the home page with a list of projects."""
    path = (
        Path(__file__).resolve().parent.parent / "data" / "yamlfiles" / "projects.yml"
    )
    with open(path, encoding="utf-8") as f:
        projects = yaml.safe_load(f)
    return render_template("home.html", projects=projects)


@foyer_blueprint.route("/resume")
def resume():
    """Render the resume page."""
    path = Path(__file__).resolve().parent.parent / "data" / "yamlfiles" / "jobs.yml"
    with open(path, encoding="utf-8") as f:
        jobs = yaml.safe_load(f)
    return render_template("resume.html", jobs=jobs)


@foyer_blueprint.route("/contact", methods=["GET", "POST"])
def contact():
    """Render the contact page and send an email if the form is submitted."""
    form = ContactForm()

    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        message = form.message.data

        html_content = get_contact_email_content(name, email, message)

        message = Mail(
            from_email="hello@keithriordan.com",
            to_emails="hello@keithriordan.com",
            subject=f"New message from {name} at {email}",
            html_content=html_content,
        )
        try:
            sg = SendGridAPIClient(current_app.config["SENDGRID_API_KEY"])
            sg.send(message)
            return render_template("contact.html", success=True)
        except Exception as err:
            print(f"There was an error sending the contact email: {err}")

    return render_template("contact.html", form=form)


@foyer_blueprint.route("/utilities")
@login_required
def utilities():
    """Render the utilities page"""

    return render_template("utilities.html")


@foyer_blueprint.route("/media")
@login_required
def media():
    """Render the media page with a list of playlists."""
    path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "jsonfiles"
        / "clean-youtube-playlist-data.json"
    )
    with open(path, encoding="utf-8") as json_file:
        playlist_data = json.loads(json_file.read())["playlists"]

    return render_template("media.html", playlist_data=playlist_data)


@foyer_blueprint.route("/learningtospeak")
@login_required
def learningtospeak():
    """Render the learningtospeak page."""
    return render_template("learningtospeak.html")
