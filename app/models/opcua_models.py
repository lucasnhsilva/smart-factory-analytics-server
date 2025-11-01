from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum

class OPCUAConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"

class OPCUAServerConfig(BaseModel):
    name: str
    endpoint: str
    security_policy: str = "Basic256Sha256"
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 10
    retry_attempts: int = 3
    retry_delay: float = 2.0

class OPCUANodeConfig(BaseModel):
    node_id: str
    tag_name: str
    data_type: str
    sampling_interval: float = 1.0

class OPCUAConnectionMetrics(BaseModel):
    server_name: str
    status: OPCUAConnectionStatus
    active_subscriptions: int
    messages_received: int
    last_error: Optional[str] = None
    latency_ms: Optional[float] = None

# NOVO MODELO ADICIONADO
class OPCUANodeInfo(BaseModel):
    """Modelo para informações de um nó OPC UA"""
    node_id: str = Field(..., description="Identificador único do nó")
    browse_name: str = Field(..., description="Nome para navegação")
    display_name: str = Field(..., description="Nome para exibição")
    node_class: str = Field(..., description="Classe do nó (Object, Variable, Method, etc.)")
    namespace: int = Field(..., description="Índice do namespace")
    value: Optional[Any] = Field(None, description="Valor atual (apenas para variáveis)")
    data_type: Optional[str] = Field(None, description="Tipo de dados (apenas para variáveis)")
    description: Optional[str] = Field(None, description="Descrição do nó")
    writable: Optional[bool] = Field(None, description="Se a variável é gravável")

class OPCUABrowseResult(BaseModel):
    """Resultado da navegação em um servidor OPC UA"""
    server: str
    starting_node: str
    nodes_found: int
    nodes: List[OPCUANodeInfo]

class OPCUAVariablesResult(BaseModel):
    """Resultado da listagem de variáveis"""
    server: str
    variables_count: int
    variables: List[OPCUANodeInfo]

class OPCUASearchResult(BaseModel):
    """Resultado da busca por nós"""
    server: str
    search_term: str
    matches_found: int
    nodes: List[OPCUANodeInfo]

class OPCUAReadResult(BaseModel):
    """Resultado da leitura de um nó"""
    server: str
    node_id: str
    value: Any
    status: str