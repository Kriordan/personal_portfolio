from flask import Flask, render_template
import yaml
app = Flask(__name__)

PROJECTS = yaml.load( open( 'yamlfiles/projects.yml' ) )

@app.route('/')
def home():
    projects = PROJECTS
    return render_template('home.html', projects=projects)

@app.route('/resume')
def resume():
    return render_template('resume.html')

if __name__ == '__main__':
    app.run(debug=True)
