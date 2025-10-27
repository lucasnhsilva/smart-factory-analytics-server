# SmartFactoryAnalyticsServer

Servidor de analytics para previsão de falhas e eficiência de equipamentos em fábricas, com comunicação vendor-agnostic via OPC UA.

## Objetivos

- Coletar dados de CLPs via OPC UA.
- Enviar dados para o servidor principal.
- Integrar com Historian para criar análise de dados históricos.
- Configuração via arquivo YAML.

## Roadmap

### Mês 1: Fundamentos e Coleta de Dados

1. Configuração do repositório e ambiente.
2. Servidor FastAPI e configuração YAML.
3. Cliente OPC UA.
4. Armazenamento local.

### Mês 2: Analytics e Integração com Historian

5. Endpoints de analytics.
6. Modelo de machine learning.
7. Integração do modelo na API.
8. Integração com Historian.

### Mês 3: Refinamento e Tolerância a Falhas

9. Tolerância a falhas no cliente OPC UA.
10. Envio de dados para host de coleta.
11. Testes e validação.
12. Documentação e deploy.

## Como usar

(Instruções a serem preenchidas ao longo do projeto)

## Configuração

Edite o arquivo `config/config.yml`:

```yaml
taxa_de_envio: 60 # em segundos
endpoint: "http://localhost:8000" # endpoint do sistema de coleta
apiKey: "chave-secreta"
```

Para Historian, edite o arquivo `config/external/historian.config.yml`

```yaml
host: "historianlocation"
user: "historian-user"
password: "historian-password"
```
