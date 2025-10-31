from fastapi import APIRouter
from app.utils.config_loader import load_config

router = APIRouter()

@router.get("/config")
async def get_config():
    """Retorna a configuração atual do serviço"""
    config = load_config()
    return {
        "server_config": config.get('server', {}),
        "data_collection": config.get('data_collection', {}),
        "logging": config.get('logging', {})
    }