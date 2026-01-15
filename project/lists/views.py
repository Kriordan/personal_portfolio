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
from project.models import CustomList, ListCategory, ListInvitation, ListItem, User, db

lists_blueprint = Blueprint("lists", __name__, template_folder="templates")


@lists_blueprint.route("/lists")
@login_required
def list_lists():
    """View all lists owned by the current user."""
    my_lists = CustomList.query.filter_by(owner_id=current_user.id).all()
    shared_lists = current_user.shared_lists.all()
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
        new_list = CustomList(
            title=form.title.data,
            owner=current_user,
        )
        db.session.add(new_list)
        db.session.commit()
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
    custom_list = CustomList.query.get_or_404(list_id)
    if custom_list.owner_id != current_user.id:
        flash("You can only share lists you own.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Please provide an email address.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    if email == current_user.email.lower():
        flash("You can't share a list with yourself.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    user_to_share_with = User.query.filter_by(email=email).first()

    if user_to_share_with:
        if user_to_share_with in custom_list.shared_with:
            flash(f"List is already shared with {email}.", "info")
            return redirect(url_for("lists.view_list", list_id=list_id))

        custom_list.shared_with.append(user_to_share_with)
        db.session.commit()
        flash(f"List shared with {email} successfully.", "success")
    else:
        existing_invitation = (
            ListInvitation.query.filter_by(email=email, list_id=list_id)
            .filter(ListInvitation.accepted_at.is_(None))
            .first()
        )

        if existing_invitation and not existing_invitation.is_expired:
            flash(f"An invitation has already been sent to {email}.", "info")
            return redirect(url_for("lists.view_list", list_id=list_id))

        invitation = ListInvitation.create_invitation(email=email, list_id=list_id)
        db.session.add(invitation)
        db.session.commit()

        try:
            invite_url = url_for(
                "lists.accept_invitation",
                token=invitation.token,
                _external=True,
            )
            send_invitation_email(
                email=email,
                inviter_name=current_user.username,
                list_title=custom_list.title,
                invite_url=invite_url,
            )
            flash(
                f"Invitation sent to {email}. They'll receive an email with instructions.",
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
    invitation = ListInvitation.query.filter_by(token=token).first_or_404()

    if invitation.is_expired:
        flash("This invitation has expired.", "danger")
        return redirect(url_for("foyer.home"))

    if invitation.is_accepted:
        flash("This invitation has already been accepted.", "info")
        if current_user.is_authenticated:
            return redirect(url_for("lists.view_list", list_id=invitation.list_id))
        return redirect(url_for("account.login"))

    if not current_user.is_authenticated:
        from flask import session

        session["pending_invitation_token"] = token
        flash("Please log in or create an account to accept this invitation.", "info")
        return redirect(url_for("account.login"))

    if current_user.email.lower() != invitation.email.lower():
        flash(
            f"This invitation was sent to {invitation.email}. "
            f"Please log in with that email address.",
            "warning",
        )
        return redirect(url_for("account.login"))

    custom_list = invitation.custom_list
    if current_user not in custom_list.shared_with:
        custom_list.shared_with.append(current_user)

    invitation.accept()
    db.session.commit()

    flash(f"You now have access to '{custom_list.title}'!", "success")
    return redirect(url_for("lists.view_list", list_id=invitation.list_id))


@lists_blueprint.route("/lists/<int:list_id>/settings", methods=["POST"])
@login_required
def update_settings(list_id):
    """Update list settings."""
    custom_list = CustomList.query.get_or_404(list_id)

    if custom_list.owner_id != current_user.id:
        flash("Only the list owner can update settings.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    completed_display_mode = request.form.get("completed_display_mode")
    if completed_display_mode in [
        "inline_bottom",
        "category_section",
        "global_section",
    ]:
        custom_list.completed_display_mode = completed_display_mode
        db.session.commit()
        flash("Settings updated successfully.", "success")
    else:
        flash("Invalid display mode.", "danger")

    return redirect(url_for("lists.view_list", list_id=list_id))


@lists_blueprint.route("/lists/<int:list_id>", methods=["GET", "POST"])
@login_required
def view_list(list_id):
    """View a specific list."""
    custom_list = CustomList.query.get_or_404(list_id)
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    cat_form = CategoryForm()
    item_form = ItemForm()

    if cat_form.validate_on_submit():
        max_order = (
            db.session.query(db.func.max(ListCategory.ordering))
            .filter_by(custom_list_id=list_id)
            .scalar()
            or 0
        )

        new_category = ListCategory(
            name=cat_form.name.data, custom_list=custom_list, ordering=max_order + 1
        )
        db.session.add(new_category)
        db.session.commit()
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
    custom_list = CustomList.query.get_or_404(list_id)
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    form = ItemForm()

    if form.validate_on_submit():
        try:
            category_id = int(request.form.get("category_id"))

            category = ListCategory.query.filter_by(
                id=category_id, custom_list_id=list_id
            ).first_or_404()

            max_order = (
                db.session.query(db.func.max(ListItem.ordering))
                .filter_by(category_id=category.id)
                .scalar()
                or 0
            )

            new_item = ListItem(
                name=form.name.data,
                quantity=form.quantity.data,
                notes=form.notes.data,
                category=category,
                ordering=max_order + 1,
            )
            db.session.add(new_item)
            db.session.commit()
            flash("Item added successfully.", "success")
        except (ValueError, TypeError):
            flash(f"Invalid category ID: {request.form.get('category_id')}", "danger")
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
    item = ListItem.query.get_or_404(item_id)
    if (
        item.category.custom_list.owner_id != current_user.id
        and current_user not in item.category.custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    item.completed = not item.completed
    db.session.commit()
    return jsonify({"success": True, "completed": item.completed})


@lists_blueprint.route("/lists/<int:list_id>/reorder_items", methods=["POST"])
@login_required
def reorder_items(list_id):
    """Reorder items in a list."""
    custom_list = CustomList.query.get_or_404(list_id)
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    data = request.get_json()
    for item_data in data.get("items", []):
        item = ListItem.query.get(item_data["id"])
        if item and item.category.custom_list_id == list_id:  # Extra security check
            item.ordering = item_data.get("ordering", item.ordering)
            new_category_id = item_data.get("category_id")
            if new_category_id:
                if ListCategory.query.filter_by(
                    id=new_category_id, custom_list_id=list_id
                ).first():
                    item.category_id = new_category_id
    db.session.commit()
    return jsonify({"success": True})


@lists_blueprint.route("/lists/<int:list_id>/reorder_categories", methods=["POST"])
@login_required
def reorder_categories(list_id):
    """Reorder categories in a list."""
    custom_list = CustomList.query.get_or_404(list_id)
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    data = request.get_json()
    for cat_data in data.get("categories", []):
        category = ListCategory.query.get(cat_data["id"])
        if category and category.custom_list_id == list_id:  # Extra security check
            category.ordering = cat_data.get("ordering", category.ordering)
    db.session.commit()
    return jsonify({"success": True})


@lists_blueprint.route("/lists/<int:list_id>/debug")
@login_required
def debug_list(list_id):
    """Debug view to see list data."""
    custom_list = CustomList.query.get_or_404(list_id)
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    categories = ListCategory.query.filter_by(custom_list_id=list_id).all()

    debug_data = {"list_title": custom_list.title, "categories": []}

    for category in categories:
        cat_data = {
            "id": category.id,
            "name": category.name,
            "ordering": category.ordering,
            "items": [],
        }

        items = ListItem.query.filter_by(category_id=category.id).all()
        for item in items:
            cat_data["items"].append(
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "completed": item.completed,
                    "ordering": item.ordering,
                }
            )

        debug_data["categories"].append(cat_data)

    return jsonify(debug_data)
