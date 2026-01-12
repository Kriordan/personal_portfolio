from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired("Please enter your email."),
            Email("Please enter a valid email."),
        ],
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class ForgotPasswordForm(FlaskForm):
    """Form for requesting a password reset email."""

    email = StringField(
        "Email",
        validators=[
            DataRequired("Please enter your email."),
            Email("Please enter a valid email."),
        ],
    )
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    """Form for setting a new password."""

    password = PasswordField(
        "New Password",
        validators=[
            DataRequired("Please enter a new password."),
            Length(min=8, message="Password must be at least 8 characters."),
        ],
    )
    password_confirm = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired("Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Reset Password")
