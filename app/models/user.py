from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Boolean
from app.database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    account_created = Column(DateTime, default=func.now())
    account_updated = Column(DateTime, onupdate=func.now())
    is_verified = Column(Boolean, default=False)

    # Define the images relationship
    images = relationship("Image", back_populates="user")

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_url = Column(String, nullable=False)
    bucket_name = Column(String, nullable=False)
    object_key = Column(String, nullable=False)
    upload_date = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="images")

class Email_logs(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    sent_at = Column(DateTime, default=func.now())
    verification_link = Column(String, nullable=False)
