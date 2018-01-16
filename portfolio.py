from flask import Flask, render_template, request
from forms import ContactForm
import yaml

app = Flask(__name__)

app.secret_key = 'keyforflaskwtf'

PROJECTS = yaml.load( open( 'yamlfiles/projects.yml' ) )

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
        return 'Form posted.'
    return render_template('contact.html', form=form)

@app.route('/learningtospeak')
def learningtospeak():
    return render_template('learningtospeak.html')

if __name__ == '__main__':
    app.run(debug=True)
