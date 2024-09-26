from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
import os
from dotenv import load_dotenv
import logging
from starlette.responses import Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the database engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Create the FastAPI application
app = FastAPI()

# Custom handler for Method Not Allowed (405) exception
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 405:  # Handle 405 specifically
        logger.error(f"Method Not Allowed: {request.method} on {request.url}")
        return Response(status_code=405)  # Return 405 with no body
    # Fallback for other HTTP exceptions
    return Response(status_code=exc.status_code)

@app.get("/healthz")
async def health_check(request: Request):
    # Check for any request payload
    body = await request.body()  # Await the body method
    if body:  # Check if there is any body content
        logger.info(f"Received payload: {body}")
        return Response(status_code=400)  # Return 400 with no body

    async with SessionLocal() as session:
        try:
            # Use the text function to define the SQL query
            await session.execute(text("SELECT 1"))
            logger.info("Database connection successful.")
            return Response(status_code=200)  # Return 200 with no body
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return Response(status_code=503)  # Return 503 with no body
