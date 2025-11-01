from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.services.opcua_manager import opcua_manager
from app.models.opcua_models import (  # Importar os novos modelos
    OPCUABrowseResult,
    OPCUAVariablesResult,
    OPCUASearchResult,
    OPCUAReadResult
)

router = APIRouter()

@router.get("/opcua/explore/{server_name}", response_model=OPCUABrowseResult)
async def explore_server(
    server_name: str,
    node_id: str = Query("i=84", description="Node ID para começar a navegação (padrão: i=84 - ObjectsFolder)")
):
    """Navega pela estrutura do servidor OPC UA"""
    try:
        nodes = await opcua_manager.browse_nodes(server_name, node_id)
        return OPCUABrowseResult(
            server=server_name,
            starting_node=node_id,
            nodes_found=len(nodes),
            nodes=nodes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opcua/variables/{server_name}", response_model=OPCUAVariablesResult)
async def get_server_variables(server_name: str):
    """Lista todas as variáveis do servidor OPC UA"""
    try:
        variables = await opcua_manager.get_server_variables(server_name)
        return OPCUAVariablesResult(
            server=server_name,
            variables_count=len(variables),
            variables=variables
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opcua/search/{server_name}", response_model=OPCUASearchResult)
async def search_nodes(
    server_name: str,
    search_term: str = Query(..., description="Termo para buscar em browse_name ou display_name")
):
    """Busca nós por nome"""
    try:
        nodes = await opcua_manager.find_nodes(server_name, search_term)
        return OPCUASearchResult(
            server=server_name,
            search_term=search_term,
            matches_found=len(nodes),
            nodes=nodes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opcua/read/{server_name}", response_model=OPCUAReadResult)
async def read_node_by_id(
    server_name: str,
    node_id: str = Query(..., description="Node ID completo (ex: ns=2;s=MyVariable)")
):
    """Lê o valor de um nó específico usando Node ID completo"""
    try:
        value = await opcua_manager.read_node_value(server_name, node_id)
        return OPCUAReadResult(
            server=server_name,
            node_id=node_id,
            value=value,
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/opcua/namespaces/{server_name}")
async def get_namespaces(server_name: str):
    """Lista todos os namespaces disponíveis no servidor"""
    try:
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(opcua_manager)
        namespaces = await explorer.get_all_namespaces(server_name)
        return {
            "server": server_name,
            "namespaces": namespaces
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opcua/explore-full/{server_name}")
async def explore_full_server(
    server_name: str,
    max_depth: int = Query(3, description="Profundidade máxima de navegação")
):
    """Navega por toda a estrutura do servidor OPC UA recursivamente"""
    try:
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(opcua_manager)
        nodes = await explorer.recursive_browse(server_name, "i=84", max_depth)
        
        # Filtrar apenas variáveis
        variables = [node for node in nodes if node.get("node_class") == "Variable"]
        
        return {
            "server": server_name,
            "total_nodes_found": len(nodes),
            "variables_found": len(variables),
            "max_depth": max_depth,
            "all_nodes": nodes,
            "variables": variables
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/opcua/variables-enhanced/{server_name}")
async def get_enhanced_variables(server_name: str):
    """Lista variáveis com informações parseadas e formatadas"""
    try:
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(opcua_manager)
        variables = await explorer.get_relevant_variables(server_name)
        
        # Separar por categoria
        categorized = {}
        for var in variables:
            category = var.get('category', 'other')
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(var)
        
        return {
            "server": server_name,
            "total_variables": len(variables),
            "categorized": categorized,
            "variables": variables
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opcua/parse-node/{server_name}")
async def parse_specific_node(
    server_name: str,
    node_id: str = Query(..., description="Node ID para parsear")
):
    """Parseia um Node ID específico para formato legível"""
    try:
        from app.utils.opcua_parsers import OPCUAParser
        parsed = OPCUAParser.parse_node_id(node_id)
        
        # Se o servidor estiver conectado, tentar ler o valor
        value = None
        if server_name in opcua_manager.clients:
            try:
                value = await opcua_manager.read_node_value(server_name, node_id)
            except:
                pass
        
        return {
            "original_node_id": node_id,
            "parsed": parsed,
            "current_value": value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))