from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine
from app.models.user import Base

async def bootstrap_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  

