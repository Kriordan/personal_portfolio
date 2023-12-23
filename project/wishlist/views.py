# Python
import os

import boto3
from botocore.exceptions import NoCredentialsError
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from project import db
from project.models import Gift

from .forms import GiftForm

wishlist_blueprint = Blueprint(
    "wishlist", __name__, template_folder="templates", url_prefix="/wishlist"
)


def upload_image_to_s3(file):
    s3 = boto3.client("s3")
    bucket_name = os.environ.get("WISHLIST_S3_BUCKET")

    try:
        s3.upload_fileobj(file, bucket_name, file.filename)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{file.filename}"
        return image_url
    except NoCredentialsError:
        return None


@wishlist_blueprint.route("/", methods=["GET", "POST"])
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

    gifts = db.session.execute(db.select(Gift)).scalars()
    form_title = "Add a gift"

    return render_template(
        "wishlist.html", gifts=gifts, form=form, form_title=form_title
    )


@wishlist_blueprint.route("/gifts", methods=["POST"])
def gift_create():
    return "Item added to wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>", methods=["GET"])
def gift_detail(item_id):
    # Logic to read a single wishlist item
    return "Item read from wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>", methods=["PUT"])
def gift_update(item_id):
    # Logic to update item in wishlist
    return "Item updated in wishlist"


@wishlist_blueprint.route("/gifts/<int:item_id>", methods=["DELETE"])
def gift_delete(item_id):
    # Logic to remove item from wishlist
    return "Item removed from wishlist"
