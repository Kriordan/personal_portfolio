from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class ListForm(FlaskForm):
    title = StringField("List Title", validators=[DataRequired()])
    submit = SubmitField("Create List")


class CategoryForm(FlaskForm):
    name = StringField("Category", validators=[DataRequired()])
    submit = SubmitField("Add Category")


class ItemForm(FlaskForm):
    name = StringField("Item", validators=[DataRequired()])
    quantity = StringField("Quantity")
    notes = TextAreaField("Notes")
    category_id = HiddenField("Category ID")  # Set this via the template.
    submit = SubmitField("Add Item")
