from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class EthernetIPConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    READY = "ready"  # Configurado mas não conectado

class EthernetIPDeviceConfig(BaseModel):
    name: str
    ip_address: str
    slot: int = 0  # Slot do PLC (0 para CompactLogix, etc.)
    timeout: float = 5.0
    retry_attempts: int = 3
    retry_delay: float = 2.0

class EthernetIPTagConfig(BaseModel):
    name: str
    tag_path: str  # Ex: "MyTag", "Program:MainProgram.MyTag"
    data_type: str  # Ex: "DINT", "REAL", "BOOL", "STRING"
    description: Optional[str] = None
    read_interval: float = 1.0  # Segundos

class EthernetIPConnectionMetrics(BaseModel):
    device_name: str
    status: EthernetIPConnectionStatus
    tags_monitored: int
    messages_received: int
    last_error: Optional[str] = None
    latency_ms: Optional[float] = None
    last_success: Optional[datetime] = None

class EthernetIPTagValue(BaseModel):
    device_name: str
    tag_name: str
    tag_path: str
    value: Any
    data_type: str
    timestamp: datetime
    quality: str = "good"  # good, bad, uncertain

class EthernetIPReadRequest(BaseModel):
    device_name: str
    tag_paths: List[str]