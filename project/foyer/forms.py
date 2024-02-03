from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import Email, InputRequired


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[InputRequired("Please enter your name.")])
    email = StringField(
        "Email",
        validators=[
            InputRequired("Please enter your email."),
            Email("Please enter a valid email."),
        ],
    )
    subject = StringField(
        "Subject", validators=[InputRequired("Please enter a subject.")]
    )
    message = TextAreaField(
        "Message", validators=[InputRequired("Please enter a message.")]
    )
