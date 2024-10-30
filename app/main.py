from fastapi import FastAPI, Request
from time import time
from app.bootstrap import bootstrap_database
from app.metrics import statsd_client
from app.routes.healthRoutes import router as health_router
from app.routes.userRoutes import router as user_router

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    await bootstrap_database()
    print("Database bootstrap completed.")

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    # Start timer
    start_time = time()
    response = await call_next(request)
    duration = time() - start_time

    # Log metrics
    statsd_client.incr(f"{request.url.path}.count")  # Count each API call
    statsd_client.timing(f"{request.url.path}.response_time", duration * 1000)  # API response time in ms

    return response

# Include the routes
app.include_router(health_router, prefix="/v2")
app.include_router(user_router, prefix="/v2/users", tags=["Users"])
