import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from app.models.ethernet_ip_models import (
    EthernetIPConnectionStatus,
    EthernetIPDeviceConfig, 
    EthernetIPTagConfig,
    EthernetIPConnectionMetrics,
    EthernetIPTagValue
)
from app.utils.config_loader import load_config

logger = logging.getLogger(__name__)

class EthernetIPManager:
    """
    Gerenciador para comunicação Ethernet/IP com PLCs
    Usa ThreadPoolExecutor para operações bloqueantes não interferirem no asyncio
    """
    
    def __init__(self):
        self.config = load_config()
        self.connections: Dict[str, Any] = {}  # Conexões com dispositivos
        self.tag_configs: Dict[str, List[EthernetIPTagConfig]] = {}
        self.connection_metrics: Dict[str, EthernetIPConnectionMetrics] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._read_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False
        self._initialized = False
        
        # Thread pool para operações bloqueantes
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self.config.get('ethernet_ip', {}).get('max_workers', 5),
            thread_name_prefix="ethip_"
        )
        
        # Cache de valores de tags
        self._tag_values: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Inicializa o gerenciador de forma NÃO-BLOQUEANTE"""
        logger.info("🚀 Inicializando Ethernet/IP Manager em background...")
        self._is_running = True
        self._initialized = True
        
        # Verificar se há dispositivos configurados
        devices = self.config.get('ethernet_ip', {}).get('devices', [])
        if not devices:
            logger.info("📝 Lista de dispositivos Ethernet/IP está vazia")
            return
        
        logger.info(f"🎯 Configurado para conectar com {len(devices)} dispositivo(s) Ethernet/IP")
        
        # Inicializar métricas e configs
        for device_config in devices:
            device_name = device_config['name']
            
            self.connection_metrics[device_name] = EthernetIPConnectionMetrics(
                device_name=device_name,
                status=EthernetIPConnectionStatus.READY,
                tags_monitored=0,
                messages_received=0
            )
            
            # Configurações de tags para este dispositivo
            self.tag_configs[device_name] = [
                EthernetIPTagConfig(**tag_config) 
                for tag_config in device_config.get('tags', [])
            ]
            
            self._tag_values[device_name] = {}
        
        # Iniciar conexões em background
        asyncio.create_task(self._connect_all_devices_background())
        
        logger.info("✅ Ethernet/IP Manager inicializado (operações em background)")
    
    async def _connect_all_devices_background(self):
        """Conecta a todos os dispositivos em background"""
        devices = self.config.get('ethernet_ip', {}).get('devices', [])
        if not devices:
            return
            
        logger.info("🔄 Iniciando conexões Ethernet/IP em background...")
        
        for device_config in devices:
            # Criar task de conexão para cada dispositivo
            task = asyncio.create_task(
                self._connect_device_with_retry(device_config)
            )
            self._monitoring_tasks[device_config['name']] = task
        
        logger.info("🎯 Conexões Ethernet/IP em background - API respondendo!")
    
    async def _connect_device_with_retry(self, device_config: dict):
        """Tenta conectar a um dispositivo com retry em background"""
        device_name = device_config['name']
        retry_attempts = self.config.get('ethernet_ip', {}).get('retry_attempts', 3)
        retry_delay = max(self.config.get('ethernet_ip', {}).get('retry_delay', 2.0), 2.0)
        
        infinite_retry = (retry_attempts == 0)
        attempt = 0
        
        while self._is_running and (infinite_retry or attempt < retry_attempts):
            try:
                if infinite_retry:
                    logger.info(f"🔄 Tentativa de conexão infinita com {device_name} (tentativa {attempt + 1})")
                else:
                    logger.info(f"🔄 Tentativa {attempt + 1}/{retry_attempts} com {device_name}")
                
                success = await self._connect_single_device(device_config)
                
                if success:
                    logger.info(f"✅ Conexão Ethernet/IP bem-sucedida com {device_name}")
                    
                    # Iniciar monitoramento de tags
                    await self._start_tag_monitoring(device_name)
                    return True
                else:
                    logger.warning(f"❌ Falha na conexão com {device_name}")
                    
            except Exception as e:
                logger.error(f"💥 Erro na conexão com {device_name} (tentativa {attempt + 1}): {e}")
                self.connection_metrics[device_name].last_error = str(e)
            
            # Incrementar tentativa se não for infinito
            if not infinite_retry:
                attempt += 1
            
            # Aguardar antes da próxima tentativa
            if self._is_running and (infinite_retry or attempt < retry_attempts):
                logger.info(f"⏳ Aguardando {retry_delay}s antes da próxima tentativa com {device_name}...")
                await asyncio.sleep(retry_delay)
        
        # Se falhou todas as tentativas
        if not infinite_retry:
            self.connection_metrics[device_name].status = EthernetIPConnectionStatus.ERROR
            self.connection_metrics[device_name].last_error = f"Todas as {retry_attempts} tentativas falharam"
            logger.error(f"💥 Falha definitiva na conexão com {device_name}")
        
        return False
    
    async def _connect_single_device(self, device_config: dict) -> bool:
        """Conecta a um único dispositivo (executado em thread separada)"""
        device_name = device_config['name']
        
        try:
            # Executar em thread para não bloquear
            success = await asyncio.get_event_loop().run_in_executor(
                self._thread_pool,
                self._blocking_connect,
                device_config
            )
            
            if success:
                self.connection_metrics[device_name].status = EthernetIPConnectionStatus.CONNECTED
                self.connection_metrics[device_name].last_success = datetime.now()
                return True
            else:
                self.connection_metrics[device_name].status = EthernetIPConnectionStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro na conexão com {device_name}: {e}")
            self.connection_metrics[device_name].status = EthernetIPConnectionStatus.ERROR
            self.connection_metrics[device_name].last_error = str(e)
            return False
    
    def _blocking_connect(self, device_config: dict) -> bool:
        """
        Método bloqueante para conectar com dispositivo Ethernet/IP
        Executado em thread separada
        """
        device_name = device_config['name']
        ip_address = device_config['ip_address']
        slot = device_config.get('slot', 0)
        
        try:
            # Tentar importar pycomm3
            try:
                from pycomm3 import LogixDriver
            except ImportError:
                logger.error("❌ pycomm3 não instalado. Execute: poetry add pycomm3")
                return False
            
            # Criar conexão
            connection = LogixDriver(ip_address, slot)
            
            # Tentar conexão
            if connection.open():
                self.connections[device_name] = connection
                logger.info(f"🔌 Conexão Ethernet/IP estabelecida com {device_name} ({ip_address})")
                return True
            else:
                logger.error(f"❌ Falha ao abrir conexão com {device_name}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Erro na conexão bloqueante com {device_name}: {e}")
            return False
    
    async def _start_tag_monitoring(self, device_name: str):
        """Inicia monitoramento de tags para um dispositivo"""
        if device_name not in self.tag_configs:
            return
        
        tag_configs = self.tag_configs[device_name]
        if not tag_configs:
            return
        
        # Atualizar métricas
        self.connection_metrics[device_name].tags_monitored = len(tag_configs)
        
        # Criar task de monitoramento
        task = asyncio.create_task(
            self._monitor_tags_loop(device_name, tag_configs)
        )
        self._read_tasks[device_name] = task
        
        logger.info(f"📊 Iniciando monitoramento de {len(tag_configs)} tags em {device_name}")
    
    async def _monitor_tags_loop(self, device_name: str, tag_configs: List[EthernetIPTagConfig]):
        """Loop de monitoramento de tags em background"""
        while self._is_running and device_name in self.connections:
            try:
                # Ler todas as tags de uma vez
                tag_paths = [tag.tag_path for tag in tag_configs]
                values = await self.read_multiple_tags(device_name, tag_paths)
                
                if values:
                    # Atualizar cache
                    for tag_value in values:
                        self._tag_values[device_name][tag_value.tag_name] = tag_value
                    
                    # Atualizar métricas
                    self.connection_metrics[device_name].messages_received += len(values)
                    self.connection_metrics[device_name].last_success = datetime.now()
                
                # Aguardar intervalo
                interval = min(tag.read_interval for tag in tag_configs)
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"❌ Erro no monitoramento de {device_name}: {e}")
                self.connection_metrics[device_name].last_error = str(e)
                await asyncio.sleep(5)  # Backoff em caso de erro
    
    async def read_tag(self, device_name: str, tag_path: str) -> Optional[EthernetIPTagValue]:
        """Lê o valor de uma tag específica"""
        if not self._initialized:
            raise ValueError("Ethernet/IP Manager não inicializado")
        
        if device_name not in self.connections:
            raise ValueError(f"Dispositivo {device_name} não conectado")
        
        try:
            # Executar em thread separada
            result = await asyncio.get_event_loop().run_in_executor(
                self._thread_pool,
                self._blocking_read_tag,
                device_name,
                tag_path
            )
            
            if result:
                self.connection_metrics[device_name].messages_received += 1
                self.connection_metrics[device_name].last_success = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao ler tag {tag_path} de {device_name}: {e}")
            self.connection_metrics[device_name].last_error = str(e)
            raise
    
    def _blocking_read_tag(self, device_name: str, tag_path: str) -> Optional[EthernetIPTagValue]:
        """Leitura bloqueante de tag (executada em thread)"""
        try:
            connection = self.connections[device_name]
            
            # Ler tag
            result = connection.read(tag_path)
            
            if result:
                return EthernetIPTagValue(
                    device_name=device_name,
                    tag_name=tag_path.split(':')[-1] if ':' in tag_path else tag_path,
                    tag_path=tag_path,
                    value=result.value,
                    data_type=str(result.type),
                    timestamp=datetime.now(),
                    quality="good" if result.error is None else "bad"
                )
            else:
                return None
                
        except Exception as e:
            logger.error(f"💥 Erro na leitura bloqueante de {tag_path}: {e}")
            return None
    
    async def read_multiple_tags(self, device_name: str, tag_paths: List[str]) -> List[EthernetIPTagValue]:
        """Lê múltiplas tags de uma vez (mais eficiente)"""
        if not self._initialized:
            raise ValueError("Ethernet/IP Manager não inicializado")
        
        if device_name not in self.connections:
            raise ValueError(f"Dispositivo {device_name} não conectado")
        
        try:
            # Executar em thread separada
            results = await asyncio.get_event_loop().run_in_executor(
                self._thread_pool,
                self._blocking_read_multiple_tags,
                device_name,
                tag_paths
            )
            
            if results:
                self.connection_metrics[device_name].messages_received += len(results)
                self.connection_metrics[device_name].last_success = datetime.now()
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro ao ler múltiplas tags de {device_name}: {e}")
            self.connection_metrics[device_name].last_error = str(e)
            raise
    
    def _blocking_read_multiple_tags(self, device_name: str, tag_paths: List[str]) -> List[EthernetIPTagValue]:
        """Leitura bloqueante de múltiplas tags"""
        try:
            connection = self.connections[device_name]
            results = []
            
            # Ler todas as tags
            read_results = connection.read(*tag_paths)
            
            for tag_path, result in zip(tag_paths, read_results):
                if result:
                    tag_value = EthernetIPTagValue(
                        device_name=device_name,
                        tag_name=tag_path.split(':')[-1] if ':' in tag_path else tag_path,
                        tag_path=tag_path,
                        value=result.value,
                        data_type=str(result.type),
                        timestamp=datetime.now(),
                        quality="good" if result.error is None else "bad"
                    )
                    results.append(tag_value)
            
            return results
            
        except Exception as e:
            logger.error(f"💥 Erro na leitura múltipla bloqueante: {e}")
            return []
    
    def get_cached_tag_value(self, device_name: str, tag_name: str) -> Optional[EthernetIPTagValue]:
        """Obtém valor de tag do cache (sem I/O - muito rápido)"""
        return self._tag_values.get(device_name, {}).get(tag_name)
    
    def get_connection_metrics(self) -> Dict[str, EthernetIPConnectionMetrics]:
        """Retorna métricas de todas as conexões"""
        return self.connection_metrics
    
    def get_active_connections_count(self) -> int:
        """Retorna número de conexões ativas"""
        return sum(
            1 for metrics in self.connection_metrics.values() 
            if metrics.status == EthernetIPConnectionStatus.CONNECTED
        )
    
    def has_configured_devices(self) -> bool:
        """Verifica se há dispositivos configurados"""
        devices = self.config.get('ethernet_ip', {}).get('devices', [])
        return len(devices) > 0
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    async def shutdown(self):
        """Desliga o gerenciador graciosamente"""
        self._is_running = False
        logger.info("🛑 Desligando Ethernet/IP Manager...")
        
        # Cancelar tasks
        for task in list(self._monitoring_tasks.values()) + list(self._read_tasks.values()):
            task.cancel()
        
        # Fechar conexões
        for device_name, connection in self.connections.items():
            try:
                await asyncio.get_event_loop().run_in_executor(
                    self._thread_pool,
                    connection.close
                )
                self.connection_metrics[device_name].status = EthernetIPConnectionStatus.DISCONNECTED
            except Exception as e:
                logger.warning(f"⚠️ Erro ao fechar conexão {device_name}: {e}")
        
        # Parar thread pool
        self._thread_pool.shutdown(wait=True)
        
        logger.info("✅ Ethernet/IP Manager desligado graciosamente")

# Instância global
ethernet_ip_manager = EthernetIPManager()