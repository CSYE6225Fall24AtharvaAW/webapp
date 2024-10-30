from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from fastapi import Depends
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from app.metrics import statsd_client
from time import time

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)



@asynccontextmanager
async def session_scope():
    session = AsyncSession(bind=engine)
    try:
        start_time = time()
        yield session
        duration = time() - start_time
        statsd_client.timing("database.query_time", duration * 1000)  # DB query time in ms
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise
    finally:
        await session.close()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
