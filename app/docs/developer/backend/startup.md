# Spuštění backendu

Backend se spouští přes soubor `run.py`.

Tento soubor slouží jako hlavní entrypoint aplikace a startuje dvě části systému:

| Služba | Port | Popis |
|---|---:|---|
| FastAPI API | `8000` | HTTP API pro frontend |
| SSH CLI | `8001` | interaktivní příkazové rozhraní přes SSH |

## Startovací flow

Při spuštění aplikace proběhne tento proces:

1. Spustí se SSH CLI server pomocí `start_ssh_server()`.
2. SSH CLI běží na portu `8001`.
3. Spustí se FastAPI aplikace pomocí `start_fastapi()`.
4. FastAPI běží přes Uvicorn na portu `8000`.
5. Při ukončení aplikace se SSH server korektně zavře.

## Související soubory

| Soubor | Účel |
|---|---|
| `run.py` | hlavní entrypoint aplikace |
| `app.py` | definice FastAPI aplikace |
| `ssh_cli_server.py` | implementace SSH CLI serveru |