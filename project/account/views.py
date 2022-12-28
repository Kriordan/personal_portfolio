from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user

from project import db
from ..models import User
from .forms import LoginForm

account_blueprint = Blueprint("account", __name__)


@account_blueprint.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).filter_by(email=form.email.data)
        ).scalar()
        if (
            user is not None
            and user.password_hash is not None
            and user.verify_password(form.password.data)
        ):
            login_user(user)
            flash("You are now logged in.", "success")
            return redirect(request.args.get("next") or url_for("foyer.home"))
        else:
            flash("Invalid email or password", "error")
            print("tis wrong")
    return render_template("account/login.html", form=form)
