from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import health, config as config_router, opcua, opcua_explorer  # Renomear para evitar conflito
from app.utils.config_loader import load_config
from app.services.opcua_manager import opcua_manager


config = load_config()
apiprefix = "/api/v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Inicializando SmartFactoryAnalyticsServer...")
    await opcua_manager.initialize()
    yield
    # Shutdown
    print("Desligando SmartFactoryAnalyticsServer...")
    await opcua_manager.shutdown()

app = FastAPI(
    title=config['server']['name'],
    version=config['server']['version'],
    debug=config['server']['debug'],
    lifespan=lifespan
)

app.include_router(health.router, prefix=apiprefix, tags=["health"])
app.include_router(config_router.router, prefix=apiprefix, tags=["config"])
app.include_router(opcua.router, prefix=apiprefix, tags=["opcua"])
app.include_router(opcua_explorer.router, prefix=apiprefix, tags=["opcua_explorer"])


@app.get("/")
async def root():
    return {
        "message": "SmartFactoryAnalyticsServer está rodando!",
        "version": config['server']['version'],
        "active_opcua_connections": opcua_manager.get_active_connections_count()
    }