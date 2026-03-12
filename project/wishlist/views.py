# Python
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from project.services import wishlist_service

from .forms import GiftForm

wishlist_blueprint = Blueprint(
    "wishlist", __name__, template_folder="templates", url_prefix="/wishlist"
)

@wishlist_blueprint.route("/", methods=["GET", "POST"])
@login_required
def wishlist_home():
    form = GiftForm()
    if form.validate_on_submit():
        wishlist_service.create_gift_for_user(
            user=current_user,
            title=form.title.data or "",
            body=form.body.data or "",
            image_file=form.image.data,
        )
        return redirect(url_for("wishlist.wishlist_home"))

    gifts = wishlist_service.list_gifts_for_user(current_user.id)
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
    gift = wishlist_service.get_gift_for_user(user_id=current_user.id, gift_id=item_id)
    if gift is None:
        abort(404)

    if request.method == "POST":
        wishlist_service.delete_gift(gift)
        return redirect(url_for("wishlist.wishlist_home"))

    return render_template("gift_delete_confirm.html", gift=gift)
