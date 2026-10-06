from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import RequestEntityTooLarge

from project.database import db
from project.services import wishlist_service

from .forms import GiftForm

wishlist_blueprint = Blueprint(
    "wishlist", __name__, template_folder="templates", url_prefix="/wishlist"
)


@wishlist_blueprint.before_request
def limit_request_size():
    request.max_content_length = wishlist_service.MAX_REQUEST_BYTES


@wishlist_blueprint.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return "Photo requests must be 6 MiB or less. Go back and choose a smaller photo.", 413


@wishlist_blueprint.route("/", methods=["GET", "POST"])
@login_required
def wishlist_home():
    form = GiftForm()
    save_error = None
    if form.validate_on_submit():
        try:
            wishlist_service.create_gift_for_user(
                user=current_user,
                title=form.title.data or "",
                body=form.body.data or "",
                image_file=form.image.data,
            )
            return redirect(url_for("wishlist.wishlist_home"))
        except wishlist_service.ValidationError as error:
            save_error = wishlist_service.validation_message(error)
        except wishlist_service.UploadError:
            current_app.logger.exception("Wishlist website upload failed")
            save_error = wishlist_service.UPLOAD_MESSAGE
        except Exception:
            current_app.logger.exception("Wishlist website save failed")
            save_error = "Couldn’t save the gift. Try again."
        db.session.rollback()

    gifts = wishlist_service.list_gifts_for_user(current_user.id)
    form_title = "Add a gift"

    return render_template(
        "wishlist.html", gifts=gifts, form=form, form_title=form_title,
        save_error=save_error, show_form=request.method == "POST",
    )


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
