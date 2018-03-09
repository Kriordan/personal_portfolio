from flask import render_template, request, Blueprint
import os
import yaml

from .forms import ContactForm
from project import sp


foyer_blueprint = Blueprint('foyer', __name__)

foyerdir = os.path.abspath(os.path.dirname(__file__))
PROJECTS = yaml.load( open( os.path.join(foyerdir, 'yamlfiles/projects.yml' )))


@foyer_blueprint.route('/')
def home():
    projects = PROJECTS
    return render_template('home.html', projects=projects)


@foyer_blueprint.route('/resume')
def resume():
    return render_template('resume.html')


@foyer_blueprint.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        try:
            sp.transmissions.send(
                recipients=['keith.riordan@gmail.com'],
                html=f'''
                <p>{form.name.data}</p>
                <p>{form.email.data}</p>
                <p>{form.message.data}</p>
                ''',
                from_email='inquiry@keithriordan.com',
                subject=form.subject.data
            )
            return render_template('contact.html', success=True)
        except SparkPostAPIException as err:
            return "<br>".join(err.errors)

    return render_template('contact.html', form=form)


@foyer_blueprint.route('/learningtospeak')
def learningtospeak():
    return render_template('learningtospeak.html')
