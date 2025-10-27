# SmartFactoryAnalyticsServer

Servidor FastAPI para previsão de falhas de equipamentos em fábricas.

## Configuração

Edite o arquivo `config/settings.yml` para ajustar as configurações.

## Execução

Instale as dependências:

```bash
poetry install
```

Inicie o servidor:

```bash
poetry run uvicorn app.main:app --reload
```