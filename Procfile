release: PYTHON_DOTENV_DISABLED=1 python scripts/release.py
web: PYTHON_DOTENV_DISABLED=1 gunicorn --config gunicorn.conf.py 'project:create_app()'
