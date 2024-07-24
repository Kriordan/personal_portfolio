from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for database models.
    """

    pass


db = SQLAlchemy(model_class=Base)
