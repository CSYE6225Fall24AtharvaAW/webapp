# app/main.py
from fastapi import FastAPI
from app.bootstrap import bootstrap_database
from app.database import get_db
from app.routes.healthRoutes import router as health_router
from app.routes.userRoutes import router as user_router

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await bootstrap_database()

# Include the routes
app.include_router(health_router)
app.include_router(user_router, prefix="/users", tags=["Users"])
