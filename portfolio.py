from flask import Flask, render_template, request
from forms import ContactForm
from flask_mail import Message, Mail
from datetime import datetime
import yaml
import os

mail = Mail()
app = Flask(__name__)

app.secret_key = "\xea\x06\x9b'kT\x9b\x1c\x11\x89\xbd{\x11\x93\x8apJ\xa8Y6\xb3\xf6\x94\x88"

PROJECTS = yaml.load( open( 'yamlfiles/projects.yml' ) )

# email configuration
app.config["MAIL_SERVER"] = "smtp.sendgrid.net"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USERNAME"] = os.environ.get('SENDGRID_USERNAME')
app.config["MAIL_PASSWORD"] = os.environ.get('SENDGRID_PASSWORD')

mail.init_app(app)

@app.context_processor
def inject_now():
  return {'now': datetime.utcnow()}

@app.route('/')
def home():
    projects = PROJECTS
    return render_template('home.html', projects=projects)

@app.route('/resume')
def resume():
    return render_template('resume.html')

@app.route('/contact', methods=['GET', 'POST'])
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

@app.route('/learningtospeak')
def learningtospeak():
    return render_template('learningtospeak.html')

if __name__ == '__main__':
    app.run(debug=True)
