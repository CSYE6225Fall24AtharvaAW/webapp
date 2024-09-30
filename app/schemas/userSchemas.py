# app/schemas.py
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str

class UserUpdate(BaseModel):
    first_name: str = None
    last_name: str = None
    password: str = None

class UserResponse(BaseModel):
    email: str
    first_name: str
    last_name: str
    account_created: datetime
    account_updated: Optional[datetime]
