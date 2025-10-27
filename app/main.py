from fastapi import FastAPI
from app.routers import health, data
from app.utils.config import load_config
# Configuration
config = load_config()

# App bootstrapping
app = FastAPI(
    title=config['server']['name'],
    version=config['server']['version'],
    debug=config['server']['debug']
)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(data.router, tags=["data"])

@app.get("/")
async def root():
    return {"message": "SmartFactoryAnalyticsServer is running!"}