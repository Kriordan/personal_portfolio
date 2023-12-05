# Python
from faker import Faker
from flask import Blueprint, render_template

fake = Faker()
wishlist = [{"name": fake.name(), "description": fake.text()} for _ in range(5)]
wishlist_blueprint = Blueprint("wishlist", __name__, template_folder="templates")


@wishlist_blueprint.route("/wishlist")
def show():
    # Logic to show wishlist
    return render_template("index.html")


@wishlist_blueprint.route("/wishlist/add", methods=["POST"])
def add():
    # Logic to add item to wishlist
    return "Item added to wishlist"


@wishlist_blueprint.route("/wishlist/remove", methods=["POST"])
def remove():
    # Logic to remove item from wishlist
    return "Item removed from wishlist"
