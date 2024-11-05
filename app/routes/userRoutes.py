from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User,Image
from app.schemas.userSchemas import UserCreate, UserUpdate, UserResponse, ImageResponse
from app.database import get_db
from app.bootstrap import get_s3_client
from passlib.context import CryptContext
import uuid
import os
from dotenv import load_dotenv
from app.metrics import statsd_client
from time import time

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


@router.post("/", response_model=UserResponse, status_code=201)
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

@router.get("/{user_id}", response_model=UserResponse, status_code=200)
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

import hashlib

@router.post("/image", status_code=201)
async def upload_image(
    credentials: HTTPBasicCredentials = Depends(security),
    session: AsyncSession = Depends(get_db),
    file: UploadFile = File(...)
):
    # Authenticate the user
    authenticated_user = await authenticate_user(credentials, session)

    s3_client = get_s3_client()
    file_extension = file.filename.split(".")[-1]
    if file_extension not in ["png", "jpg", "jpeg"]:
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    # Calculate the hash of the file to check for duplicates
    file_content = await file.read()  # Read the file content for hashing
    file_hash = hashlib.sha256(file_content).hexdigest()
    await file.seek(0)  # Reset file pointer to beginning for upload

    # Retrieve existing image URLs for the user to check duplicates
    result = await session.execute(select(Image.image_url).where(Image.user_id == authenticated_user.id))
    existing_images = result.scalars().all()

    # Check if any existing image URL matches the hash of the new file content
    for image_url in existing_images:
        # Download the existing image from S3 to calculate its hash
        existing_file_obj = s3_client.get_object(Bucket=bucket_name, Key=image_url.split(f"{bucket_name}/")[-1])
        existing_file_content = existing_file_obj['Body'].read()
        existing_file_hash = hashlib.sha256(existing_file_content).hexdigest()

        if file_hash == existing_file_hash:
            raise HTTPException(status_code=409, detail="Image already exists.")

    # Generate a unique object key for S3
    object_key = f"{authenticated_user.id}/{uuid.uuid4()}.{file_extension}"

    try:
        # Upload to S3
        start_time = time()
        s3_client.upload_fileobj(file.file, bucket_name, object_key)
        duration = time() - start_time
        statsd_client.timing("s3.upload_time", duration * 1000)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"

        # Save metadata to the database
        image = Image(user_id=authenticated_user.id, image_url=image_url, bucket_name=bucket_name, object_key=object_key)
        session.add(image)
        await session.commit()

        return {"message": "Image uploaded successfully", "url": image_url}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=503, detail="An error occurred while uploading the image.")


@router.delete("/image/{image_id}",status_code=204)
async def delete_image(
    image_id: int,
    credentials: HTTPBasicCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
):
    # Authenticate the user
    authenticated_user = await authenticate_user(credentials, session)

    s3_client = get_s3_client()
    try:
        # Find the image metadata in the database
        result = await session.execute(select(Image).where(Image.id == image_id))
        image = result.scalar_one_or_none()
        if image.user_id != authenticated_user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized to delete this image.")
        if not image:
            raise HTTPException(status_code=404, detail="Image not found or you do not have permission to delete this image.")
        
        # Delete from S3
        start_time = time()
        s3_client.delete_object(Bucket=image.bucket_name, Key=image.object_key)
        duration = time() - start_time
        statsd_client.timing("s3.delete_time", duration * 1000)

        # Delete metadata from the database
        await session.delete(image)
        await session.commit()
        return {"message": "Image deleted successfully"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        raise HTTPException(status_code=503, detail="An error occurred while deleting the image.")

@router.get("/image/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: int,
    credentials: HTTPBasicCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
):
    # Authenticate the user
    authenticated_user = await authenticate_user(credentials, session)

    try:
        # Find the image metadata in the database
        result = await session.execute(select(Image).where(Image.id == image_id))
        image = result.scalar_one_or_none()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        
        if image.user_id != authenticated_user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized to access this image.")
        
        # Build the response
        return ImageResponse(
            file_name= image.object_key,
            id= str(image.id),
            url = image.image_url,
            upload_date = image.upload_date.strftime("%Y-%m-%d"),
            user_id = str(image.user_id)
        )

    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        raise HTTPException(status_code=503, detail="An error occurred while retrieving the image.")
