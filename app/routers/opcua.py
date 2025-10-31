from fastapi import APIRouter, HTTPException
from app.services.opcua_manager import opcua_manager
from app.models.opcua_models import OPCUAConnectionMetrics

router = APIRouter()

@router.get("/opcua/connections", response_model=dict[str, OPCUAConnectionMetrics])
async def get_connections_status():
    """Retorna o status de todas as conexões OPC UA"""
    return opcua_manager.get_connection_metrics()

@router.get("/opcua/connections/active")
async def get_active_connections_count():
    """Retorna o número de conexões ativas"""
    return {"active_connections": opcua_manager.get_active_connections_count()}

@router.get("/opcua/read/{server_name}/{node_id}")
async def read_node_value(server_name: str, node_id: str):
    """Lê o valor de um nó OPC UA específico"""
    try:
        value = await opcua_manager.read_node_value(server_name, node_id)
        return {
            "server": server_name,
            "node_id": node_id,
            "value": value,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/opcua/reconnect/{server_name}")
async def reconnect_server(server_name: str):
    """Força a reconexão com um servidor específico"""
    try:
        from app.utils.config_loader import load_config
        config = load_config()
        
        server_config = next(
            (s for s in config['opcua']['servers'] if s['name'] == server_name), 
            None
        )
        
        if not server_config:
            raise HTTPException(status_code=404, detail="Servidor não encontrado")
        
        await opcua_manager._reconnect_server(server_config)
        return {"status": "reconnection_initiated", "server": server_name}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))