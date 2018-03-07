from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import InputRequired, Email

class ContactForm(FlaskForm):
  name = StringField("Name", validators=[InputRequired("Please enter your name.")])
  email = StringField("Email", validators=[InputRequired("Please enter your email."), Email("Please enter a valid email.")])
  subject = StringField("Subject", validators=[InputRequired("Please enter a subject.")])
  message = TextAreaField("Message", validators=[InputRequired("Please enter a message.")])
  submit = SubmitField("Send")


class PdfForm(FlaskForm):
    url = StringField("URL", validators=[InputRequired("Enter a valid url")])
    submit = SubmitField("Create PDF")
