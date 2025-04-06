# myapp/lists/routes.py
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_

from project.lists.forms import CategoryForm, ItemForm, ListForm
from project.models import CustomList, ListCategory, ListItem, User, db

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
    """Share a list with another user."""
    custom_list = CustomList.query.get_or_404(list_id)
    if custom_list.owner_id != current_user.id:
        flash("You can only share lists you own.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    email = request.form.get("email", 0)
    if not email:
        flash("Please provide an email address.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    user_to_share_with = User.query.filter_by(email=email).first()
    if not user_to_share_with:
        flash(f"No user found with email {email}.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    if user_to_share_with.id == current_user.id:
        flash("You can't share a list with yourself.", "danger")
        return redirect(url_for("lists.view_list", list_id=list_id))

    if user_to_share_with in custom_list.shared_with:
        flash(f"List is already shared with {email}.", "info")
        return redirect(url_for("lists.view_list", list_id=list_id))

    custom_list.shared_with.append(user_to_share_with)
    db.session.commit()
    flash(f"List shared with {email} successfully.", "success")
    return redirect(url_for("lists.view_list", list_id=list_id))


@lists_blueprint.route("/lists/<int:list_id>", methods=["GET", "POST"])
@login_required
def view_list(list_id):
    """View a specific list."""
    custom_list = CustomList.query.get_or_404(list_id)
    # Check if user has access to this list
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    cat_form = CategoryForm()
    item_form = ItemForm()

    # Handle adding a new category.
    if cat_form.validate_on_submit():
        # Get the highest ordering value
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
    # Check if user has access to this list
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    form = ItemForm()
    print("Form data:", form.data)  # Debug print
    print("Form errors:", form.errors)  # Debug print
    print("Request form:", request.form)  # Debug print

    if form.validate_on_submit():
        try:
            # Get the category_id from request.form directly since it might be more reliable
            category_id = int(request.form.get("category_id"))
            print("Category ID:", category_id)  # Debug print

            category = ListCategory.query.filter_by(
                id=category_id, custom_list_id=list_id
            ).first_or_404()

            # Set ordering to one more than the current maximum in the category.
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
        except (ValueError, TypeError) as e:
            print("Error:", str(e))  # Debug print
            flash(f"Invalid category ID: {request.form.get('category_id')}", "danger")
        except Exception as e:
            print("Unexpected error:", str(e))  # Debug print
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
    # Check if user has access to this list
    if (
        item.category.custom_list.owner_id != current_user.id
        and current_user not in item.category.custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    # Flip the completion flag.
    item.completed = not item.completed
    db.session.commit()
    return jsonify({"success": True, "completed": item.completed})


@lists_blueprint.route("/lists/<int:list_id>/reorder_items", methods=["POST"])
@login_required
def reorder_items(list_id):
    """Reorder items in a list."""
    custom_list = CustomList.query.get_or_404(list_id)
    # Check if user has access to this list
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    # Expect a JSON payload: { "items": [ { "id": 1, "ordering": 1, "category_id": 2 }, ... ] }
    data = request.get_json()
    for item_data in data.get("items", []):
        item = ListItem.query.get(item_data["id"])
        if item and item.category.custom_list_id == list_id:  # Extra security check
            item.ordering = item_data.get("ordering", item.ordering)
            new_category_id = item_data.get("category_id")
            if new_category_id:
                # Verify the new category belongs to this list
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
    # Check if user has access to this list
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        return jsonify({"success": False, "error": "Access denied"}), 403
    # Expect a JSON payload: { "categories": [ { "id": 1, "ordering": 1 }, ... ] }
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
    # Check if user has access to this list
    if (
        custom_list.owner_id != current_user.id
        and current_user not in custom_list.shared_with
    ):
        flash("You don't have access to this list.", "danger")
        return redirect(url_for("lists.list_lists"))

    # Get all categories with their items
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
