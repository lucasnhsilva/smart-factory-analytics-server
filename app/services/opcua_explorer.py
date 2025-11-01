import logging
from typing import List, Dict, Any
from asyncua import Client
from app.models.opcua_models import OPCUANodeInfo  # Agora vai funcionar!
from app.utils.opcua_parsers import OPCUAParser

logger = logging.getLogger(__name__)

class OPCUAExplorer:
    def __init__(self, opcua_manager):
        self.manager = opcua_manager
    
    async def browse_server_nodes(self, server_name: str, node_id: str = "i=84") -> List[OPCUANodeInfo]:
        """
        Navega pelos nós do servidor OPC UA começando do nó raiz
        i=84 é o ObjectsFolder, que geralmente contém a estrutura principal
        """
        if server_name not in self.manager.clients:
            raise ValueError(f"Servidor {server_name} não conectado")
        
        client = self.manager.clients[server_name]
        nodes_info = []
        
        # Mapeamento de node_class numérico para string
        NODE_CLASS_MAP = {
            1: "Object",
            2: "Variable", 
            4: "Method",
            8: "ObjectType",
            16: "VariableType",
            32: "ReferenceType",
            64: "DataType"
        }
        
        try:
            # Pegar o nó a ser navegado
            node = client.get_node(node_id)
            
            # Navegar pelos nós filhos
            children = await node.get_children()
            
            for child in children:
                try:
                    # Obter informações do nó
                    browse_name = await child.read_browse_name()
                    display_name = await child.read_display_name()
                    node_class_num = await child.read_node_class()
                    
                    # CONVERTER node_class numérico para string
                    node_class_str = NODE_CLASS_MAP.get(node_class_num, f"Unknown({node_class_num})")
                    
                    # Criar objeto OPCUANodeInfo
                    node_info = OPCUANodeInfo(
                        node_id=str(child.nodeid),
                        browse_name=browse_name.Name,
                        display_name=display_name.Text,
                        node_class=node_class_str,  # Usar string convertida
                        namespace=child.nodeid.NamespaceIndex
                    )
                    
                    # Tentar ler o valor se for uma variável
                    if node_class_str == "Variable":
                        try:
                            value = await child.read_value()
                            node_info.value = value
                            node_info.data_type = str(await child.read_data_type())
                            
                            # Verificar se é gravável
                            try:
                                attributes = await child.read_attributes()
                                node_info.writable = any(attr.Value.Value for attr in attributes if attr.Value is not None)
                            except:
                                node_info.writable = None
                                
                        except Exception as e:
                            node_info.value = f"Erro ao ler: {e}"
                            node_info.data_type = "Unknown"
                    
                    nodes_info.append(node_info)
                    
                except Exception as e:
                    logger.warning(f"Erro ao processar nó: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erro ao navegar servidor {server_name}: {e}")
            raise
        
        return nodes_info
    
    async def get_all_variables(self, server_name: str) -> List[OPCUANodeInfo]:
        """Obtém todas as variáveis do servidor"""
        all_nodes = await self.browse_server_nodes(server_name)
        return [node for node in all_nodes if node.node_class == "Variable"]
    
    async def find_node_by_name(self, server_name: str, name: str) -> List[OPCUANodeInfo]:
        """Encontra nós pelo nome"""
        all_nodes = await self.browse_server_nodes(server_name)
        return [node for node in all_nodes if name.lower() in node.browse_name.lower() or 
                                          name.lower() in node.display_name.lower()]
    async def get_all_namespaces(self, server_name: str) -> List[Dict[str, Any]]:
        """Obtém todos os namespaces do servidor"""
        if server_name not in self.manager.clients:
            raise ValueError(f"Servidor {server_name} não conectado")

        client = self.manager.clients[server_name]
        try:
            # Obter o servidor para acessar a tabela de namespaces
            server_node = client.get_node("i=2253")  # Server node
            namespace_array_node = client.get_node("i=2255")  # NamespaceArray

            namespaces = await namespace_array_node.read_value()

            namespace_list = []
            for idx, uri in enumerate(namespaces):
                namespace_list.append({
                    "index": idx,
                    "uri": uri,
                    "node_id_example": f"ns={idx};s=SomeVariable"
                })

            return namespace_list

        except Exception as e:
            logger.error(f"Erro ao obter namespaces: {e}")
            raise
    async def recursive_browse(self, server_name: str, node_id: str = "i=84", max_depth: int = 3) -> List[Dict[str, Any]]:
        """Navega recursivamente por toda a estrutura do servidor"""
        if server_name not in self.manager.clients:
            raise ValueError(f"Servidor {server_name} não conectado")
        
        client = self.manager.clients[server_name]
        all_nodes = []
        
        # Mapeamento de node_class numérico para string
        NODE_CLASS_MAP = {
            1: "Object",
            2: "Variable", 
            4: "Method",
            8: "ObjectType",
            16: "VariableType",
            32: "ReferenceType",
            64: "DataType"
        }
        
        async def browse_recursive(current_node, current_depth):
            if current_depth > max_depth:
                return
            
            try:
                children = await current_node.get_children()
                
                for child in children:
                    try:
                        browse_name = await child.read_browse_name()
                        display_name = await child.read_display_name()
                        node_class_num = await child.read_node_class()
                        
                        # Converter node_class numérico para string
                        node_class_str = NODE_CLASS_MAP.get(node_class_num, f"Unknown({node_class_num})")
                        
                        node_info = {
                            "node_id": str(child.nodeid),
                            "browse_name": browse_name.Name,
                            "display_name": display_name.Text,
                            "node_class": node_class_str,
                            "namespace": child.nodeid.NamespaceIndex,
                            "depth": current_depth
                        }
                        
                        # Para variáveis, tentar ler o valor
                        if node_class_str == "Variable":
                            try:
                                value = await child.read_value()
                                node_info["value"] = value
                                node_info["data_type"] = str(await child.read_data_type())
                            except Exception as e:
                                node_info["value"] = f"Erro: {e}"
                        
                        # APLICAR PARSER PARA MELHORAR AS INFORMAÇÕES
                        enhanced_info = OPCUAParser.enhance_node_info(node_info)
                        all_nodes.append(enhanced_info)
                        
                        # Se for objeto, navegar recursivamente
                        if node_class_str == "Object" and current_depth < max_depth:
                            await browse_recursive(child, current_depth + 1)
                            
                    except Exception as e:
                        logger.debug(f"Erro ao processar nó filho: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Erro na navegação recursiva: {e}")
        
        try:
            start_node = client.get_node(node_id)
            await browse_recursive(start_node, 0)
            return all_nodes
        except Exception as e:
            logger.error(f"Erro ao iniciar navegação recursiva: {e}")
            raise
    
    async def get_relevant_variables(self, server_name: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Obtém apenas as variáveis relevantes (filtra informações do sistema)
        """
        all_nodes = await self.recursive_browse(server_name, "i=84", max_depth)
        
        # Filtrar apenas variáveis relevantes
        relevant_variables = [
            node for node in all_nodes 
            if node.get("node_class") == "Variable" and node.get("is_relevant", True)
        ]
        
        return relevant_variables