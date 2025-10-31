from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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