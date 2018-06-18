from flask import Blueprint, render_template


ranch_blueprint = Blueprint('ranch', __name__, template_folder='templates')


@ranch_blueprint.route('/ranch')
def ranch_home():
    return render_template('ranch_base.html')


@ranch_blueprint.route('/ranch/seen')
def ranch_seen():
    return render_template('ranch_seen.html')