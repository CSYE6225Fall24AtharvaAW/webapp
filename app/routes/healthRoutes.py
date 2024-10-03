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
        result = await session.execute(select(1))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database check failed: {str(e)}")

    return {"status": "healthy", "database": "reachable"}
