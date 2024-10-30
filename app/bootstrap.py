import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from app.database import Base, engine
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
from statsd import StatsClient

# Initialize StatsD client
statsd_client = StatsClient(host='0.0.0.0', port=8125, prefix='fastapi_app')



load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_default_db_url():
    # Split the URL and remove the database name, using 'postgres' as the default database
    parts = DATABASE_URL.rsplit('/', 1)
    default_db_url = parts[0] + '/postgres'
    return default_db_url

async def create_database():
    db_name = DATABASE_URL.split("/")[-1]  # Extract the database name from DATABASE_URL
    default_db_url = get_default_db_url()

    # Create a temporary engine with AUTOCOMMIT isolation level
    temp_engine = create_async_engine(default_db_url, echo=True, isolation_level="AUTOCOMMIT")
    async with temp_engine.connect() as conn:
        try:
            await conn.execute(text(f"CREATE DATABASE {db_name}"))
            await conn.commit()
        except ProgrammingError as e:
            print(f"Database creation might have failed: {e}")
        finally:
            await conn.close()
    await temp_engine.dispose()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("created")

async def bootstrap_database():
    try:
        await create_database()
    except Exception as e:
        print(f"Error during database creation: {e}")
    await create_tables()

def get_s3_client():
    return boto3.client("s3")  # IAM roles assigned to the EC2 instance will be used for authentication.

