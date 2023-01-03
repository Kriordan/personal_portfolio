from datetime import timedelta, datetime
from flask import Blueprint, render_template
from flask_login import login_required

from project import db
from ..models import Contact

crm_blueprint = Blueprint("crm", __name__, template_folder="templates")


@crm_blueprint.route("/crm/")
@login_required
def crm_home():
    filter_before = datetime.today() - timedelta(days=30)
    # contacts = db.session.execute(
    #     db.select(Contact).filter(Contact.last_contact == None)
    # ).scalars()
    contacts = db.session.execute(
        db.select(Contact).filter(
            (Contact.last_contact <= filter_before) | (Contact.last_contact == None)
        )
    ).scalars()
    return render_template("crm-home.html", contacts=contacts)
