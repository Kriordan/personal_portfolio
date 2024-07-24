"""This file defines the routes for the account blueprint."""

from urllib.parse import urlsplit

import sqlalchemy as sa
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from project.account.forms import LoginForm
from project.database import db
from project.models import User

account_blueprint = Blueprint("account", __name__, template_folder="templates")


@account_blueprint.route("/login", methods=["GET", "POST"])
def login():
    """
    The login route.
    """
    if current_user.is_authenticated:
        return redirect(url_for("foyer.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if (
            user is None
            or not user.check_password(form.password.data)
            or not user.is_active
        ):
            flash("Invalid username or password")
            return redirect(url_for("account.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("foyer.home")
        return redirect(next_page)
    return render_template("login.html", title="Sign In", form=form)


@account_blueprint.route("/logout")
def logout():
    """
    The logout route.
    """
    logout_user()
    return redirect(url_for("foyer.home"))
