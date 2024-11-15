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
import json
import boto3
import logging
import hashlib
from dotenv import load_dotenv
from app.metrics import statsd_client
from time import time
from itsdangerous import URLSafeTimedSerializer
import secrets

load_dotenv()

bucket_name = os.getenv("BUCKET_NAME")

# Create security object for basic auth
security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate required environment variables
required_env_vars = ["AWS_REGION", "BASE_URL", "SNS_TOPIC_ARN", "SECRET_KEY", "TOKEN_MAX_AGE"]
for var in required_env_vars:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
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
        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account not verified. Please complete email verification.",
            )
        return user
    except SQLAlchemyError as e:
        logger.error(f"Database error during authentication: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")

@router.get("/verify")
async def verify_user(user: str, token: str, session: AsyncSession = Depends(get_db)):
    try:
        
        # Decode the token
        token_max_age = int(os.getenv("TOKEN_MAX_AGE", "120"))  # Default to 120 seconds if not set
        data = serializer.loads(token, salt="email-verification-salt", max_age=token_max_age)

        if data["email"] != user:
            raise HTTPException(status_code=400, detail="Invalid token or user mismatch")

        # Fetch the user from the database
        result = await session.execute(select(User).where(User.email == user))
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update the user's verification status
        db_user.is_verified = True
        await session.commit()

        return {"message": "Email successfully verified"}

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=400, detail="Verification failed")


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_db)):
    try:
        # Check if the email already exists
        existing_user = await session.execute(select(User).where(User.email == user.email))
        if existing_user.scalar() is not None:
            raise HTTPException(status_code=400, detail="Email already exists")

        # Hash the password
        hashed_password = pwd_context.hash(user.password)

        # Create a new user
        new_user = User(
            email=user.email,
            hashed_password=hashed_password,
            first_name=user.first_name,
            last_name=user.last_name,
            is_verified=False,
        )

        session.add(new_user)
        await session.commit()

        # Generate the token for email verification
        token = serializer.dumps({"email": new_user.email}, salt="email-verification-salt")
        verification_link = f"https://{os.getenv('BASE_URL')}/verify?user={new_user.email}&token={token}"

        # Configure the SNS client
        sns_client = boto3.client("sns", region_name=os.getenv("AWS_REGION"))

        sns_message = {
            "email": new_user.email,
            "verification_link": verification_link,
        }

        # Publish the verification message
        try:
            sns_client.publish(
                TopicArn=os.getenv("SNS_TOPIC_ARN"),
                Message=json.dumps(sns_message),
                Subject="Email Verification Required"
            )
        except boto3.exceptions.Boto3Error as e:
            logger.error(f"Failed to publish SNS message: {e}")
            raise HTTPException(status_code=500, detail="Could not send verification email")

        return UserResponse(
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            account_created=new_user.account_created,
            account_updated=new_user.account_updated,
        )

    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        raise HTTPException(status_code=503, detail="Database error occurred")
    finally:
        await session.close()

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

    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
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
    
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        raise HTTPException(status_code=503, detail="Database error occurred")

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

    # Retrieve existing object keys for the user to check duplicates
    result = await session.execute(select(Image.object_key).where(Image.user_id == authenticated_user.id))
    existing_object_keys = result.scalars().all()

    # Check each existing image in S3 to see if it matches the uploaded file's hash
    for object_key in existing_object_keys:
        try:
            # Fetch the existing file from S3
            existing_file_obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            existing_file_content = existing_file_obj['Body'].read()
            existing_file_hash = hashlib.sha256(existing_file_content).hexdigest()

            if file_hash == existing_file_hash:
                raise HTTPException(status_code=409, detail="Image already exists.")
        except s3_client.exceptions.NoSuchKey:
            # Skip if the object does not exist in S3
            continue

    # Generate a new unique object key for the new upload
    new_object_key = f"{authenticated_user.id}/{uuid.uuid4()}.{file_extension}"

    try:
        # Upload to S3
        start_time = time()
        s3_client.upload_fileobj(file.file, bucket_name, new_object_key)
        duration = time() - start_time
        statsd_client.timing("s3.upload_time", duration * 1000)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{new_object_key}"

        # Save metadata to the database
        image = Image(user_id=authenticated_user.id, image_url=image_url, bucket_name=bucket_name, object_key=new_object_key)
        session.add(image)
        await session.commit()
        await session.refresh(image)  # Refresh the instance to get the auto-generated ID

        return {"message": "Image uploaded successfully", "id": image.id, "url": image_url}
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        logger.error(f"An error occurred while uploading the image: {e}")
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
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        logger.error(f"An error occurred while deleting the image: {e}")
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

    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        raise HTTPException(status_code=503, detail="Database error occurred")
    except Exception as e:
        logger.error(f"An error occurred while retrieving the image: {e}")
        raise HTTPException(status_code=503, detail="An error occurred while retrieving the image.")
