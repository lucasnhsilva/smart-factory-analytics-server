import yaml
import os
from pathlib import Path

def load_config():
    """Carrega configurações do arquivo YAML"""
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.yml"
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        return {
            'server': {
                'name': 'SmartFactoryAnalyticsServer',
                'version': '1.0.0',
                'debug': True
            }
        }