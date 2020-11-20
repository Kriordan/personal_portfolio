import os
import yaml

from flask import render_template, request, Blueprint, jsonify
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, Subject, To, From, MimeType

from .forms import ContactForm


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
        message = Mail()
        message.from_email = From(form.email.data, form.name.data)
        message.to = To("keith.riordan@gmail.com", "Keith Riordan", p=0)
        message.subject = Subject(form.subject.data)
        message.content = Content(MimeType.html, form.message.data)
        try:
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            response = sg.send(message)
            print(f'The response status code was: {response.status_code}')
            print(f'The response body was: {response.body}')
            print(f'The response headers were: {response.headers}')
            return render_template('contact.html', success=True)
        except Exception as err:
            print(f'There was an error sending the contact email: {err}')

    return render_template('contact.html', form=form)


@foyer_blueprint.route('/media')
def media():
    return render_template('media.html')


@foyer_blueprint.route('/learningtospeak')
def learningtospeak():
    return render_template('learningtospeak.html')
