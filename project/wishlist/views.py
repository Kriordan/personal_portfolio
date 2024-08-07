# Python
import os

import boto3
from botocore.exceptions import NoCredentialsError
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from project.database import db
from project.models import Gift

from .forms import GiftForm

wishlist_blueprint = Blueprint(
    "wishlist", __name__, template_folder="templates", url_prefix="/wishlist"
)


def upload_image_to_s3(file):
    s3 = boto3.client("s3")
    bucket_name = os.getenv("WISHLIST_S3_BUCKET")

    try:
        s3.upload_fileobj(file, bucket_name, file.filename)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{file.filename}"
        return image_url
    except NoCredentialsError:
        return None


@wishlist_blueprint.route("/", methods=["GET", "POST"])
@login_required
def wishlist_home():
    form = GiftForm()
    if form.validate_on_submit():
        title = form.title.data
        body = form.body.data

        gift = Gift(title=title, body=body, author=current_user)
        if form.image.data:
            image_url = upload_image_to_s3(form.image.data)
            if image_url:
                gift.image_url = image_url

        db.session.add(gift)
        db.session.commit()

        return redirect(url_for("wishlist.wishlist_home"))

    gifts = db.session.execute(
        db.select(Gift).filter_by(user_id=current_user.id)
    ).scalars()
    form_title = "Add a gift"

    return render_template(
        "wishlist.html", gifts=gifts, form=form, form_title=form_title
    )


@wishlist_blueprint.route("/gifts", methods=["POST"])
@login_required
def gift_create():
    return "Item added to wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>", methods=["GET"])
@login_required
def gift_detail(item_id):
    # Logic to read a single wishlist item
    return "Item read from wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>", methods=["PUT"])
@login_required
def gift_update(item_id):
    # Logic to update item in wishlist
    return "Item updated in wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>/delete", methods=["GET", "POST"])
@login_required
def gift_delete(item_id):
    gift = db.get_or_404(Gift, item_id)

    if request.method == "POST":
        db.session.delete(gift)
        db.session.commit()
        return redirect(url_for("wishlist.wishlist_home"))

    return render_template("gift_delete_confirm.html", gift=gift)
