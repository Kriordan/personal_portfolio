# Python
from faker import Faker
from flask import Blueprint, render_template

from .forms import GiftForm

fake = Faker()
gifts = [{"name": fake.name(), "description": fake.text()} for _ in range(5)]
wishlist_blueprint = Blueprint(
    "wishlist", __name__, template_folder="templates", url_prefix="/wishlist"
)


@wishlist_blueprint.route("/")
def wishlist_home():
    form = GiftForm()
    return render_template("wishlist.html", gifts=gifts, form=form)


@wishlist_blueprint.route("/gifts", methods=["POST"])
def gift_create():
    # Logic to add item to wishlist
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
