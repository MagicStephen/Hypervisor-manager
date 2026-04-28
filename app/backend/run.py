import asyncio
import uvicorn

from app import app, platform_gateway
from ssh_cli_server import start_ssh_server


async def start_fastapi():
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    ssh_server = await start_ssh_server(
        platform_gateway=platform_gateway,
        host="0.0.0.0",
        port=8001,
        host_key_path="ssh_host_key",
    )
    print("SSH CLI running on port 8001")

    try:
        await start_fastapi()
    finally:
        ssh_server.close()
        await ssh_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())