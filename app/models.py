from sqlalchemy import Column, Integer, String
from app.database import Base

class SampleModel(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
