from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User
from app.schemas.userSchemas import UserCreate, UserUpdate, UserResponse
from app.database import get_db
from passlib.context import CryptContext

# Create security object for basic auth
security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

async def authenticate_user(credentials: HTTPBasicCredentials, session: AsyncSession):
    try:
        result = await session.execute(select(User).where(User.email == credentials.username))
        user = result.scalar_one_or_none()
        
        if not user or not pwd_context.verify(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"}
            )
        return user

    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_db)):
    try:
        existing_user = await session.execute(select(User).where(User.email == user.email))
        if existing_user.scalar() is not None:
            raise HTTPException(status_code=400, detail="Email already exists")

        hashed_password = pwd_context.hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_password,
                        first_name=user.first_name, last_name=user.last_name)

        session.add(new_user)
        await session.commit()
        return UserResponse(email=new_user.email, first_name=new_user.first_name,
                            last_name=new_user.last_name,
                            account_created=new_user.account_created,
                            account_updated=new_user.account_updated)

    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, 
                      session: AsyncSession = Depends(get_db), 
                      credentials: HTTPBasicCredentials = Depends(security)):
    try:
        # Authenticate the user
        authenticated_user = await authenticate_user(credentials, session)

        # Check if the authenticated user is trying to update their own data
        if authenticated_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this user's data")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user_update.first_name:
            user.first_name = user_update.first_name
        if user_update.last_name:
            user.last_name = user_update.last_name
        if user_update.password:
            user.hashed_password = pwd_context.hash(user_update.password)

        await session.commit()
        await session.refresh(user)

        return UserResponse(email=user.email, first_name=user.first_name,
                            last_name=user.last_name,
                            account_created=user.account_created,
                            account_updated=user.account_updated)

    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, 
                   session: AsyncSession = Depends(get_db), 
                   credentials: HTTPBasicCredentials = Depends(security)):
    try:
        # Authenticate the user
        authenticated_user = await authenticate_user(credentials, session)

        # Check if the authenticated user is trying to access their own data
        if authenticated_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to access this user's data")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(email=user.email, first_name=user.first_name,
                            last_name=user.last_name,
                            account_created=user.account_created,
                            account_updated=user.account_updated)
    
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
