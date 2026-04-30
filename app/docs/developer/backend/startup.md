# Spuštění backendu

Backend se spouští přes soubor `run.py`, který slouží jako hlavní entrypoint aplikace a zajišťuje inicializaci všech komponent systému.

## Instalace závislostí

Před spuštěním je nutné nainstalovat závislosti:

```bash
pip install -r requirements.txt
```

## Spuštění aplikace

Backend lze spustit pomocí:

```bash
python run.py
```

Po spuštění jsou dostupné následující služby:

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
5. Při ukončení aplikace se SSH server korektně zastaví.

## SSH host key

Pro funkčnost SSH CLI rozhraní je vyžadován hostitelský klíč serveru.

Pokud soubor `ssh_host_key` neexistuje, je nutné jej vygenerovat:

```bash
ssh-keygen -t rsa -b 4096 -f ssh_host_key -N ""
```

Tento klíč slouží k identifikaci serveru při navazování SSH spojení.

## Související soubory

| Soubor | Účel |
|---|---|
| `run.py` | hlavní entrypoint aplikace |
| `app.py` | definice FastAPI aplikace |
| `ssh_cli_server.py` | implementace SSH CLI serveru |