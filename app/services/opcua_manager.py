import asyncio
import logging
from typing import Dict, List, Optional, Any
from asyncua import Client
from asyncua.common.subscription import Subscription

from app.models.opcua_models import (
    OPCUAConnectionStatus, 
    OPCUAConnectionMetrics
)
from app.utils.config_loader import load_config

logger = logging.getLogger(__name__)

class OPCUAManager:
    def __init__(self):
        self.config = load_config()
        self.clients: Dict[str, Client] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.connection_metrics: Dict[str, OPCUAConnectionMetrics] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._connection_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False
        self._initialized = False  # Flag para indicar se o gerenciador já foi inicializado
        
    async def initialize(self):
        """Inicializa o gerenciador de forma não bloqueante."""
        logger.info("Inicializando OPC UA Manager em background...")
        self._is_running = True
        self._initialized = True
        
        servers = self.config['opcua'].get('servers', [])
        if not servers:
            logger.info("Nenhum servidor OPC UA configurado - nenhuma conexão será estabelecida.")
            return
        
        logger.info(f"Configurado para conectar com {len(servers)} servidor(es) OPC UA.")
        
        # Inicializar métricas
        for server_config in servers:
            self.connection_metrics[server_config['name']] = OPCUAConnectionMetrics(
                server_name=server_config['name'],
                status=OPCUAConnectionStatus.DISCONNECTED,
                active_subscriptions=0,
                messages_received=0
            )
        
        # Iniciar conexões e monitoramento em background
        asyncio.create_task(self._connect_all_servers_background())
        self._monitoring_task = asyncio.create_task(self._monitor_connections())
        
        logger.info("OPC UA Manager inicializado. Conexões serão estabelecidas em background.")
    
    async def _connect_all_servers_background(self):
        """Inicia a conexão com todos os servidores OPC UA em background."""
        servers = self.config['opcua'].get('servers', [])
        if not servers:
            return
        
        logger.info("Iniciando conexões OPC UA em background...")
        
        for server_config in servers:
            task = asyncio.create_task(
                self._connect_to_server_with_retry(server_config)
            )
            self._connection_tasks[server_config['name']] = task
        
        logger.info("Conexões OPC UA executando em background. A API permanece disponível.")
    
    async def _connect_to_server_with_retry(self, server_config: dict):
        """Tenta conectar a um servidor com tentativas automáticas de reconexão."""
        server_name = server_config['name']
        retry_attempts = self.config['opcua'].get('retry_attempts', 3)
        retry_delay = max(self.config['opcua'].get('retry_delay', 2.0), 2.0)
        
        infinite_retry = (retry_attempts == 0)
        attempt = 0
        
        while self._is_running and (infinite_retry or attempt < retry_attempts):
            try:
                if infinite_retry:
                    logger.info(f"Tentando conexão com {server_name} (tentativa {attempt + 1}, modo infinito).")
                else:
                    logger.info(f"Tentativa {attempt + 1}/{retry_attempts} de conexão com {server_name}.")
                
                success = await self._simple_connect(server_config)
                
                if success:
                    logger.info(f"Conexão estabelecida com sucesso com {server_name}.")
                    return True
                else:
                    logger.warning(f"Falha na conexão com {server_name}.")
                    
            except Exception as e:
                logger.error(f"Erro ao conectar com {server_name} (tentativa {attempt + 1}): {e}")
            
            if not infinite_retry:
                attempt += 1
            
            if self._is_running and (infinite_retry or attempt < retry_attempts):
                logger.info(f"Aguardando {retry_delay}s antes da próxima tentativa com {server_name}...")
                await asyncio.sleep(retry_delay)
        
        if not infinite_retry:
            self.connection_metrics[server_name].status = OPCUAConnectionStatus.ERROR
            self.connection_metrics[server_name].last_error = f"Todas as {retry_attempts} tentativas de conexão falharam."
            logger.error(f"Falha definitiva na conexão com {server_name} após {retry_attempts} tentativas.")
        
        return False
    
    async def _simple_connect(self, server_config: dict) -> bool:
        """Estabelece uma conexão simples com o servidor OPC UA."""
        server_name = server_config['name']
        
        try:
            client = Client(server_config['endpoint'])
            
            timeout = self.config['opcua'].get('default_timeout', 10)
            async with asyncio.timeout(timeout):
                await client.connect()
            
            self.clients[server_name] = client
            self.connection_metrics[server_name].status = OPCUAConnectionStatus.CONNECTED
            
            subscription = await client.create_subscription(period=1000, publishing=True, handler=None)
            self.subscriptions[server_name] = subscription
            self.connection_metrics[server_name].active_subscriptions = 1
            
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ao tentar conectar com {server_name}.")
            return False
        except Exception as e:
            logger.error(f"Erro na conexão simples com {server_name}: {e}")
            return False
    
    async def _monitor_connections(self):
        """Monitora periodicamente o estado das conexões OPC UA."""
        while self._is_running:
            try:
                servers = self.config['opcua'].get('servers', [])
                if not servers:
                    await asyncio.sleep(10)
                    continue
                
                for server_name, client in list(self.clients.items()):
                    if not self._is_running:
                        break
                        
                    try:
                        start_time = asyncio.get_event_loop().time()
                        await client.get_root_node().read_browse_name()
                        latency = (asyncio.get_event_loop().time() - start_time) * 1000
                        
                        self.connection_metrics[server_name].latency_ms = latency
                        self.connection_metrics[server_name].status = OPCUAConnectionStatus.CONNECTED
                        
                    except Exception as e:
                        logger.warning(f"Conexão perdida com {server_name}: {e}")
                        self.connection_metrics[server_name].status = OPCUAConnectionStatus.ERROR
                        self.connection_metrics[server_name].last_error = str(e)
                        server_config = next((s for s in servers if s['name'] == server_name), None)
                        print(server_config)
                        if server_config:
                            asyncio.create_task(self._connect_to_server_with_retry(server_config))
                
                await asyncio.sleep(self.config['opcua']['monitoring_interval'])
                
            except Exception as e:
                logger.error(f"Erro no monitoramento das conexões: {e}")
                await asyncio.sleep(10)
    
    async def read_node_value(self, server_name: str, node_id: str) -> Optional[Any]:
        """Lê o valor de um nó específico de um servidor OPC UA."""
        if not self._initialized:
            raise ValueError("OPC UA Manager não foi inicializado.")
            
        servers = self.config['opcua'].get('servers', [])
        if not servers:
            raise ValueError("Nenhum servidor OPC UA configurado.")
            
        if server_name not in self.clients:
            raise ValueError(f"Servidor {server_name} não está conectado.")
        
        try:
            client = self.clients[server_name]
            node = client.get_node(node_id)
            value = await node.read_value()
            
            self.connection_metrics[server_name].messages_received += 1
            return value
            
        except Exception as e:
            logger.error(f"Erro ao ler nó {node_id} do servidor {server_name}: {e}")
            self.connection_metrics[server_name].last_error = str(e)
            raise
    
    def get_connection_metrics(self) -> Dict[str, OPCUAConnectionMetrics]:
        """Retorna as métricas de todas as conexões OPC UA."""
        return self.connection_metrics
    
    def get_active_connections_count(self) -> int:
        """Retorna o número de conexões ativas."""
        return sum(
            1 for metrics in self.connection_metrics.values() 
            if metrics.status == OPCUAConnectionStatus.CONNECTED
        )
    
    def has_configured_servers(self) -> bool:
        """Indica se há servidores configurados."""
        servers = self.config['opcua'].get('servers', [])
        return len(servers) > 0
    
    def is_initialized(self) -> bool:
        """Retorna True se o gerenciador já foi inicializado."""
        return self._initialized
    
    def has_active_connections(self) -> bool:
        """Indica se há conexões ativas."""
        return len(self.clients) > 0
    async def get_server_namespaces(self, server_name: str) -> List[Dict[str, Any]]:
        """Obtém todos os namespaces do servidor"""
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(self)
        return await explorer.get_all_namespaces(server_name)
    
    async def shutdown(self):
        """Desliga o gerenciador e encerra conexões graciosamente."""
        self._is_running = False
        logger.info("Encerrando OPC UA Manager...")
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        for task in self._connection_tasks.values():
            task.cancel()
        
        disconnect_tasks = []
        for server_name, client in self.clients.items():
            try:
                disconnect_tasks.append(client.disconnect())
                self.connection_metrics[server_name].status = OPCUAConnectionStatus.DISCONNECTED
            except Exception as e:
                logger.warning(f"Erro ao desconectar {server_name}: {e}")
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        logger.info("OPC UA Manager desligado com sucesso.")
    async def browse_nodes(self, server_name: str, node_id: str = "i=84") -> List[Dict[str, Any]]:
        """Navega pelos nós do servidor (interface para o explorer)"""
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(self)
        return await explorer.browse_server_nodes(server_name, node_id)
    
    async def get_server_variables(self, server_name: str) -> List[Dict[str, Any]]:
        """Obtém todas as variáveis do servidor"""
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(self)
        return await explorer.get_all_variables(server_name)
    
    async def find_nodes(self, server_name: str, search_term: str) -> List[Dict[str, Any]]:
        """Encontra nós por nome"""
        from app.services.opcua_explorer import OPCUAExplorer
        explorer = OPCUAExplorer(self)
        return await explorer.find_node_by_name(server_name, search_term)

# Instância global do gerenciador
opcua_manager = OPCUAManager()
