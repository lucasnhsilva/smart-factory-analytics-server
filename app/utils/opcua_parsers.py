import re
from typing import Dict, Any, Optional

class OPCUAParser:
    """Classe para parsear e converter dados OPC UA para formato legível"""
    
    @staticmethod
    def parse_node_id(node_id_str: str) -> Dict[str, Any]:
        """
        Parseia uma string NodeId para extrair informações úteis
        Exemplo: "NodeId(Identifier=3, NamespaceIndex=2, NodeIdType=\u003CNodeIdType.FourByte: 1\u003E)"
        """
        try:
            # Extrair partes usando regex
            identifier_match = re.search(r'Identifier=([^,]+)', node_id_str)
            namespace_match = re.search(r'NamespaceIndex=([^,]+)', node_id_str)
            node_type_match = re.search(r'NodeIdType=.*?([A-Za-z]+):\s*(\d+)', node_id_str)
            
            identifier = identifier_match.group(1) if identifier_match else "Unknown"
            namespace = int(namespace_match.group(1)) if namespace_match else 0
            node_type = node_type_match.group(1) if node_type_match else "Unknown"
            
            # Criar Node ID formatado
            if node_type == "Numeric":
                formatted_id = f"i={identifier}"
            elif node_type == "String":
                formatted_id = f"s={identifier}"
            else:
                formatted_id = f"ns={namespace};{identifier}"
            
            return {
                "raw": node_id_str,
                "identifier": identifier,
                "namespace": namespace,
                "node_type": node_type,
                "formatted": f"ns={namespace};{formatted_id}",
                "simple": f"ns={namespace};i={identifier}" if node_type == "Numeric" else f"ns={namespace};s={identifier}"
            }
            
        except Exception as e:
            return {
                "raw": node_id_str,
                "formatted": node_id_str,
                "simple": node_id_str,
                "error": str(e)
            }
    
    @staticmethod
    def parse_data_type(data_type_str: str) -> Dict[str, Any]:
        """
        Parseia uma string de data type para extrair informações úteis
        Converte IDs numéricos para nomes legíveis
        """
        # Mapeamento de data types OPC UA comuns
        DATA_TYPE_MAP = {
            "1": "Boolean",
            "2": "SByte",
            "3": "Byte", 
            "4": "Int16",
            "5": "UInt16",
            "6": "Int32",
            "7": "UInt32",
            "8": "Int64",
            "9": "UInt64",
            "10": "Float",
            "11": "Double",
            "12": "String",
            "13": "DateTime",
            "14": "Guid",
            "15": "ByteString",
            "16": "XmlElement",
            "17": "NodeId",
            "18": "ExpandedNodeId",
            "19": "StatusCode",
            "20": "QualifiedName",
            "21": "LocalizedText",
            "22": "ExtensionObject",
            "23": "DataValue",
            "24": "Variant",
            "25": "DiagnosticInfo"
        }
        
        try:
            # Tentar extrair o identifier numérico
            id_match = re.search(r'Identifier=(\d+)', data_type_str)
            if id_match:
                numeric_id = id_match.group(1)
                data_type_name = DATA_TYPE_MAP.get(numeric_id, f"Unknown({numeric_id})")
                
                return {
                    "raw": data_type_str,
                    "numeric_id": numeric_id,
                    "name": data_type_name,
                    "formatted": data_type_name
                }
            else:
                return {
                    "raw": data_type_str,
                    "formatted": data_type_str
                }
                
        except Exception as e:
            return {
                "raw": data_type_str,
                "formatted": data_type_str,
                "error": str(e)
            }
    
    @staticmethod
    def should_include_node(node_info: Dict[str, Any]) -> bool:
        """
        Determina se um nó deve ser incluído nos resultados baseado em sua relevância
        Filtra nós do sistema e mantém apenas dados de aplicação
        """
        # Namespace 0 geralmente contém informações do servidor OPC UA
        namespace = node_info.get('namespace', 0)
        
        # Se for namespace 0, verificar se é uma variável útil
        if namespace == 0:
            browse_name = node_info.get('browse_name', '').lower()
            display_name = node_info.get('display_name', '').lower()
            
            # Manter apenas algumas variáveis úteis do namespace 0
            useful_system_vars = {
                'servername', 'serverstatus', 'currenttime', 'starttime',
                'buildinfo', 'servicelevel'
            }
            
            if browse_name in useful_system_vars or display_name in useful_system_vars:
                return True
            else:
                return False  # Filtrar outras variáveis do namespace 0
        
        # Para namespaces > 0, geralmente são dados de aplicação - manter
        return namespace > 0
    
    @staticmethod
    def enhance_node_info(raw_node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Melhora as informações do nó com dados parseados e formatados
        """
        enhanced = raw_node.copy()
        
        # Parsear Node ID
        if 'node_id' in enhanced:
            node_id_parsed = OPCUAParser.parse_node_id(enhanced['node_id'])
            enhanced['node_id_parsed'] = node_id_parsed
            enhanced['node_id_simple'] = node_id_parsed['simple']
        
        # Parsear Data Type
        if 'data_type' in enhanced:
            data_type_parsed = OPCUAParser.parse_data_type(enhanced['data_type'])
            enhanced['data_type_parsed'] = data_type_parsed
            enhanced['data_type_simple'] = data_type_parsed['formatted']
        
        # Adicionar flag de relevância
        enhanced['is_relevant'] = OPCUAParser.should_include_node(enhanced)
        
        # Adicionar categoria baseada no nome
        browse_name = enhanced.get('browse_name', '').lower()
        if any(term in browse_name for term in ['temp', 'temperature', 'heat']):
            enhanced['category'] = 'temperature'
        elif any(term in browse_name for term in ['pressure', 'press']):
            enhanced['category'] = 'pressure'
        elif any(term in browse_name for term in ['speed', 'rpm', 'velocity']):
            enhanced['category'] = 'speed'
        elif any(term in browse_name for term in ['volt', 'voltage', 'power']):
            enhanced['category'] = 'electrical'
        elif any(term in browse_name for term in ['count', 'production', 'total']):
            enhanced['category'] = 'counter'
        else:
            enhanced['category'] = 'other'
        
        return enhanced