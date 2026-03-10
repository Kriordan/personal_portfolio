# myapp/lists/routes.py
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from mailersend import EmailBuilder, MailerSendClient

from project.foyer.email_templates import get_list_invitation_email_content
from project.lists.forms import CategoryForm, ItemForm, ListForm
from project.models import db
from project.services import lists_service

lists_blueprint = Blueprint("lists", __name__, template_folder="templates")


@lists_blueprint.route("/lists")
@login_required
def list_lists():
    """View all lists owned by the current user."""
    my_lists, shared_lists = lists_service.get_user_lists(current_user)
    form = ListForm()
    return render_template(
        "lists.html",
        my_lists=my_lists,
        shared_lists=shared_lists,
        form=form,
    )


@lists_blueprint.route("/lists/create", methods=["POST"])
@login_required
def create_list():
    """Create a new list."""
    form = ListForm()
    if not form.validate_on_submit():
        flash(f"Form validation failed. Errors: {form.errors}", "danger")
        return redirect(url_for("lists.list_lists"))

    try:
        new_list = lists_service.create_list(owner=current_user, title=form.title.data)
        flash("List created successfully.", "success")
        return redirect(url_for("lists.view_list", list_id=new_list.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating list: {str(e)}", "danger")
        return redirect(url_for("lists.list_lists"))


@lists_blueprint.route("/lists/<int:list_id>/share", methods=["POST"])
@login_required
def share_list(list_id):
    """Share a list with another user or send an invitation."""
    custom_list = lists_service.get_list_or_404(list_id)
    email = request.form.get("email", "")
    try:
        result = lists_service.share_list_with_email(
            custom_list=custom_list,
            owner=current_user,
            email=email,
        )
    except PermissionError as err:
        flash(str(err), "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))
    except ValueError as err:
        flash(str(err), "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))
    except Exception as err:
        db.session.rollback()
        flash(f"Error sharing list: {str(err)}", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    status = result["status"]
    shared_email = result["email"]
    if status == "already_shared":
        flash(f"List is already shared with {shared_email}.", "info")
    elif status == "shared_existing_user":
        flash(f"List shared with {shared_email} successfully.", "success")
    elif status == "invitation_exists":
        flash(f"An invitation has already been sent to {shared_email}.", "info")
    elif status == "invitation_created":
        invitation = result["invitation"]
        try:
            invite_url = url_for(
                "lists.accept_invitation",
                token=invitation.token,
                _external=True,
            )
            send_invitation_email(
                email=shared_email,
                inviter_name=current_user.username,
                list_title=custom_list.title,
                invite_url=invite_url,
            )
            flash(
                f"Invitation sent to {shared_email}. They'll receive an email with instructions.",
                "success",
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to send invitation email: {str(e)}", "danger")

    return redirect(url_for("lists.view_list", list_id=list_id))


def send_invitation_email(email, inviter_name, list_title, invite_url):
    """Send an invitation email to share a list."""
    html_content = get_list_invitation_email_content(
        inviter_name, list_title, invite_url
    )

    ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
    email_message = (
        EmailBuilder()
        .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
        .to_many([{"email": email, "name": email.split("@")[0]}])
        .subject(f"{inviter_name} invited you to collaborate on a list")
        .html(html_content)
        .build()
    )
    ms.emails.send(email_message)


@lists_blueprint.route("/lists/invitation/<token>")
def accept_invitation(token):
    """Accept a list sharing invitation."""
    invitation = lists_service.get_invitation_or_404(token)

    if invitation.is_expired:
        flash("This invitation has expired.", "danger")
        return redirect(url_for("foyer.home"))

    if invitation.is_accepted:
        flash("This invitation has already been accepted.", "info")
        if current_user.is_authenticated:
            return redirect(url_for("lists.view_list", list_id=invitation.list_id))
        return redirect(url_for("account.login"))

    if not current_user.is_authenticated:
        flash("Please create an account to accept this invitation.", "info")
        return redirect(url_for("account.signup", token=token))

    if current_user.email.lower() != invitation.email.lower():
        flash(
            f"This invitation was sent to {invitation.email}. "
            f"Please log in with that email address.",
            "warning",
        )
        return redirect(url_for("account.login"))

    custom_list = lists_service.accept_invitation_for_user(invitation, current_user)

    flash(f"You now have access to '{custom_list.title}'!", "success")
    return redirect(url_for("lists.view_list", list_id=invitation.list_id))


@lists_blueprint.route("/lists/<int:list_id>/settings", methods=["POST"])
@login_required
def update_settings(list_id):
    """Update list settings."""
    custom_list = lists_service.get_list_or_404(list_id)
    try:
        lists_service.ensure_list_owner(custom_list, current_user)
    except PermissionError:
        flash("Only the list owner can update settings.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    completed_display_mode = request.form.get("completed_display_mode")
    try:
        lists_service.update_completed_display_mode(
            custom_list=custom_list,
            completed_display_mode=completed_display_mode,
        )
        flash("Settings updated successfully.", "success")
    except ValueError:
        flash("Invalid display mode.", "danger")

    return redirect(url_for("lists.view_list", list_id=list_id))


@lists_blueprint.route("/lists/<int:list_id>", methods=["GET", "POST"])
@login_required
def view_list(list_id):
    """View a specific list."""
    custom_list = lists_service.get_list_or_404(list_id)
    try:
        lists_service.ensure_list_access(custom_list, current_user)
    except PermissionError:
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    cat_form = CategoryForm()
    item_form = ItemForm()

    if cat_form.validate_on_submit():
        lists_service.add_category(custom_list=custom_list, name=cat_form.name.data)
        flash("Category added successfully.", "success")
        return redirect(url_for("lists.view_list", list_id=list_id))

    return render_template(
        "list_view.html",
        custom_list=custom_list,
        cat_form=cat_form,
        item_form=item_form,
    )


@lists_blueprint.route("/lists/<int:list_id>/add_item", methods=["POST"])
@login_required
def add_item(list_id):
    """Add an item to a list."""
    custom_list = lists_service.get_list_or_404(list_id)
    try:
        lists_service.ensure_list_access(custom_list, current_user)
    except PermissionError:
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    form = ItemForm()

    if form.validate_on_submit():
        try:
            lists_service.add_item(
                custom_list_id=list_id,
                name=form.name.data,
                quantity=form.quantity.data,
                notes=form.notes.data,
                category_id_raw=request.form.get("category_id"),
            )
            flash("Item added successfully.", "success")
        except ValueError as err:
            flash(str(err), "danger")
        except Exception:
            flash("Error adding item.", "danger")
            db.session.rollback()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("lists.view_list", list_id=list_id))


@lists_blueprint.route(
    "/lists/<int:list_id>/toggle_item/<int:item_id>", methods=["POST"]
)
@login_required
def toggle_item(list_id, item_id):
    """Toggle an item's completed status."""
    item = lists_service.get_list_item_or_404(item_id)
    try:
        completed = lists_service.toggle_item_completion(item=item, user=current_user)
    except PermissionError:
        return jsonify({"success": False, "error": "Access denied"}), 403
    return jsonify({"success": True, "completed": completed})


@lists_blueprint.route("/lists/<int:list_id>/reorder_items", methods=["POST"])
@login_required
def reorder_items(list_id):
    """Reorder items in a list."""
    custom_list = lists_service.get_list_or_404(list_id)
    data = request.get_json() or {}
    try:
        lists_service.reorder_items(
            custom_list=custom_list,
            user=current_user,
            items_payload=data.get("items", []),
        )
    except PermissionError:
        return jsonify({"success": False, "error": "Access denied"}), 403
    return jsonify({"success": True})


@lists_blueprint.route("/lists/<int:list_id>/reorder_categories", methods=["POST"])
@login_required
def reorder_categories(list_id):
    """Reorder categories in a list."""
    custom_list = lists_service.get_list_or_404(list_id)
    data = request.get_json() or {}
    try:
        lists_service.reorder_categories(
            custom_list=custom_list,
            user=current_user,
            categories_payload=data.get("categories", []),
        )
    except PermissionError:
        return jsonify({"success": False, "error": "Access denied"}), 403
    return jsonify({"success": True})


@lists_blueprint.route("/lists/<int:list_id>/debug")
@login_required
def debug_list(list_id):
    """Debug view to see list data."""
    custom_list = lists_service.get_list_or_404(list_id)
    try:
        debug_data = lists_service.get_list_debug_payload(
            custom_list=custom_list,
            user=current_user,
        )
    except PermissionError:
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    return jsonify(debug_data)
