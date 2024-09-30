# app/routes/health.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.user import User

router = APIRouter()

@router.get("/healthz")
async def health_check(session: AsyncSession = Depends(get_db)):
    try:
        # Check database connectivity
        result = await session.execute(select(User).limit(1))
        user_exists = result.scalar_one_or_none() is not None
        if not user_exists:
            raise HTTPException(status_code=500, detail="Database not reachable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database check failed: {str(e)}")

    return {"status": "healthy", "database": "reachable"}
