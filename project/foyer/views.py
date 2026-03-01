"""This file defines the routes for the foyer blueprint."""

import json
from pathlib import Path

import requests
import yaml
from flask import Blueprint, current_app, render_template, request
from flask_login import login_required
from mailersend import EmailBuilder, MailerSendClient

from project.extensions import limiter

from .email_templates import get_contact_email_content
from .forms import ContactForm

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

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
@limiter.limit("5/hour", methods=["POST"])
def contact():
    """Render the contact page and send an email if the form is submitted."""
    form = ContactForm()
    site_key = current_app.config.get("TURNSTILE_SITE_KEY", "")

    if form.validate_on_submit():
        if form.website.data:
            return render_template("contact.html", success=True)

        turnstile_token = form.cf_turnstile_response.data or request.form.get(
            "cf-turnstile-response", ""
        )
        if not _verify_turnstile(turnstile_token):
            return render_template(
                "contact.html",
                form=form,
                turnstile_site_key=site_key,
                turnstile_error="Human verification failed. Please try again.",
            )

        name = form.name.data
        email = form.email.data
        message_content = form.message.data

        html_content = get_contact_email_content(name, email, message_content)
        contact_email = current_app.config["CONTACT_EMAIL"]

        try:
            ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
            email_message = (
                EmailBuilder()
                .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
                .to_many([{"email": contact_email, "name": "Keith"}])
                .reply_to(email, name)
                .subject(f"[Portfolio Contact] New message from {name}")
                .html(html_content)
                .build()
            )
            ms.emails.send(email_message)
            return render_template("contact.html", success=True)
        except Exception as err:
            print(f"There was an error sending the contact email: {err}")

    return render_template(
        "contact.html", form=form, turnstile_site_key=site_key
    )


def _verify_turnstile(token: str) -> bool:
    """Validate a Cloudflare Turnstile response token. Returns True when
    verification succeeds or when Turnstile is not configured (missing secret)."""
    secret = current_app.config.get("TURNSTILE_SECRET_KEY")
    if not secret:
        return True

    try:
        resp = requests.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret, "response": token},
            timeout=5,
        )
        return resp.ok and resp.json().get("success", False)
    except requests.RequestException:
        return False


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
