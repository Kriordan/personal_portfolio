"""This file defines the routes for the foyer blueprint."""
import json
import os
from pathlib import Path

import yaml
from flask import Blueprint, render_template
from python_http_client import exceptions
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail, MimeType, Subject, To

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
        message = Mail()
        message.from_email = From(form.email.data, form.name.data)
        message.to = To("keith.riordan@gmail.com", "Keith Riordan", p=0)
        message.subject = Subject(form.subject.data)
        message.content = Content(MimeType.html, form.message.data)
        try:
            sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
            response = sg.send(message)
            print(f"The response status code was: {response.status_code}")
            print(f"The response body was: {response.body}")
            print(f"The response headers were: {response.headers}")
            return render_template("contact.html", success=True)
        except exceptions.BadRequestsError as err:
            print(f"There was an error sending the contact email: {err}")

    return render_template("contact.html", form=form)


@foyer_blueprint.route("/media")
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
def learningtospeak():
    """Render the learningtospeak page."""
    return render_template("learningtospeak.html")
