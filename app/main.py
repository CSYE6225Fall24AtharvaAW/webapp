from fastapi import FastAPI
from app.bootstrap import bootstrap_database
from app.routes.healthRoutes import router as health_router
from app.routes.userRoutes import router as user_router

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    await bootstrap_database()
    print("Database bootstrap completed.")

# Include the routes
app.include_router(health_router, prefix="/v2")
app.include_router(user_router, prefix="/v2/users", tags=["Users"])
