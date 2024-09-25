from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
import os
from dotenv import load_dotenv
import logging

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

@app.get("/healthz")
async def health_check(request: Request):
    # Check for any request payload
    body = await request.body()  # Await the body method
    if body:  # Check if there is any body content
        logger.info(f"Received payload: {body}")
        raise HTTPException(status_code=400, detail="Payload not allowed")

    async with SessionLocal() as session:
        try:
            # Use the text function to define the SQL query
            await session.execute(text("SELECT 1"))
            logger.info("Database connection successful.")
            return {"status": "healthy"}
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise HTTPException(status_code=503, detail="Service Unavailable")
