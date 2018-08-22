from flask import Blueprint, render_template, request, redirect, url_for
from werkzeug.datastructures import CombinedMultiDict
import datetime

from .forms import AddImageForm
from project import db
from project.models import Image


ranch_blueprint = Blueprint('ranch', __name__, template_folder='templates', url_prefix='/ranch')


@ranch_blueprint.route('/')
def ranch_home():
    return render_template('ranch_home.html')


@ranch_blueprint.route('/seen')
def ranch_seen():
    images = db.session.query(Image)
    return render_template(
        'ranch_images.html',
        form = AddImageForm(CombinedMultiDict((request.files, request.form))),
        images=images
    )


@ranch_blueprint.route('/seen/<image_id>', methods=['GET'])
def get_seen(image_id):
    image = Image.query.filter_by(id=int(image_id)).first()
    return render_template(
        'ranch_image.html',
        image=image
    )


@ranch_blueprint.route('/seen/add', methods=['GET', 'POST'])
def add_seen():
    error = None
    form = AddImageForm(CombinedMultiDict((request.files, request.form)))
    if form.validate_on_submit():
        new_image = Image(
            posted_date = datetime.datetime.utcnow()
        )
        image_data = form.image.data
        new_image.store_image(request.files['image'])
        db.session.add(new_image)
        db.session.commit()

    return redirect(url_for('.ranch_seen'))


@ranch_blueprint.route('/seen/<int:image_id>/delete', methods=('POST',))
def delete_seen(image_id):
    image = Image.query.filter_by(id=image_id).first()
    db.session.delete(image)
    db.session.commit()
    return redirect(url_for('.ranch_seen'))