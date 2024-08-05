# Python
import os

import boto3
from botocore.exceptions import NoCredentialsError
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from project.database import db
from project.models import Gift

library_blueprint = Blueprint(
    "library", __name__, template_folder="templates", url_prefix="/lib"
)


@library_blueprint.route("/", methods=["GET"])
@login_required
def library_home():
    return render_template("library.html")
