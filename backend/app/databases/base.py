from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

metadata = MetaData(schema="css")

class Base(DeclarativeBase):
    metadata = metadata