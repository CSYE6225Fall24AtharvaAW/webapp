from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User,Image
from app.schemas.userSchemas import UserCreate, UserUpdate, UserResponse
from app.database import get_db
from app.bootstrap import get_s3_client
from passlib.context import CryptContext
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

bucket_name = os.getenv("BUCKET_NAME")

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

    except SQLAlchemyError as e:
        print(str(e))
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

@router.post("/upload-image/{user_id}")
async def upload_image(
    user_id: int,
    credentials: HTTPBasicCredentials = Depends(security),
    session: AsyncSession = Depends(get_db),
    file: UploadFile = File(...)
):
    # Authenticate the user
    authenticated_user = await authenticate_user(credentials, session)

    # Check if the authenticated user is the same as the one uploading the image
    if authenticated_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to upload an image for this user.")

    s3_client = get_s3_client()
    file_extension = file.filename.split(".")[-1]
    if file_extension not in ["png", "jpg", "jpeg"]:
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    object_key = f"{user_id}/{uuid.uuid4()}.{file_extension}"
    try:
        s3_client.upload_fileobj(file.file, bucket_name, object_key)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        
        # Save metadata to the database
        image = Image(user_id=user_id, image_url=image_url, bucket_name=bucket_name, object_key=object_key)
        session.add(image)
        await session.commit()
        return {"message": "Image uploaded successfully", "url": image_url}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail="An error occurred while uploading the image.")

@router.delete("/delete-image/{user_id}/{image_id}")
async def delete_image(
    user_id: int,
    image_id: int,
    credentials: HTTPBasicCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
):
    # Authenticate the user
    authenticated_user = await authenticate_user(credentials, session)

    # Check if the authenticated user is the same as the one deleting the image
    if authenticated_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this image.")

    s3_client = get_s3_client()
    try:
        # Find the image metadata in the database
        result = await session.execute(select(Image).where(Image.id == image_id, Image.user_id == user_id))
        image = result.scalar_one_or_none()
        if not image:
            raise HTTPException(status_code=404, detail="Image not found or you do not have permission to delete this image.")
        
        # Delete from S3
        s3_client.delete_object(Bucket=image.bucket_name, Key=image.object_key)
        
        # Delete metadata from the database
        await session.delete(image)
        await session.commit()
        return {"message": "Image deleted successfully"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred while deleting the image.")
