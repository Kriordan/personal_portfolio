from flask import render_template, request, Blueprint
from flask_mail import Message
import os
import yaml

from .forms import ContactForm, PdfForm
from project import mail


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
        msg = Message(form.subject.data, sender='app42252860@heroku.com', recipients=['keith.riordan@gmail.com'])
        msg.body = """
        From: %s <%s>
        %s
        """ % (form.name.data, form.email.data, form.message.data)
        mail.send(msg)
        return render_template('contact.html', success=True)

    return render_template('contact.html', form=form)

