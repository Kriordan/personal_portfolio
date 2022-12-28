from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField
from wtforms.validators import Email, InputRequired, Length


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[InputRequired(), Length(1, 64), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
