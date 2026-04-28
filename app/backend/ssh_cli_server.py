import json
import shlex
import asyncssh

from database.database import SessionLocal
from database.models.user_model import User
from services.user_service import UserService
from cli import CliSession

def format_help() -> str:
    return "\n".join([
        "=" * 80,
        "AVAILABLE COMMANDS",
        "=" * 80,
        "",
        "SERVER:",
        "  server list",
        "  server create",
        "  server reconnect <server_id>",
        "",
        "NODE:",
        "  node show <server_id> <node_id>",
        "",
        "VM:",
        "  vm show <server_id> <node_id> <vm_id>",
        "  vm start <server_id> <node_id> <vm_id>",
        "  vm stop <server_id> <node_id> <vm_id>",
        "  vm reboot <server_id> <node_id> <vm_id>",
        "  vm shutdown <server_id> <node_id> <vm_id>",
        "  vm destroy <server_id> <node_id> <vm_id>",
        "  vm create <server_id> <node_id>",
        "",
        "SYSTEM:",
        "  help",
        "  exit",
        "  quit",
    ])

def get_authenticated_user(process):
    db = SessionLocal()
    try:
        username = process.get_extra_info("username")
        user = db.query(User).filter(User.username == username).first()
        return user
    finally:
        db.close()


class MySSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        db = SessionLocal()
        try:
            try:
                UserService.login(username=username, password=password, db=db)
                return True
            except Exception:
                return False
        finally:
            db.close()


async def prompt_input(process, label: str) -> str:
    process.stdout.write(label)
    return (await process.stdin.readline()).strip()


async def prompt_int(process, label: str, required: bool = False):
    value = await prompt_input(process, label)

    if not value:
        if required:
            return {"error": f"{label.strip(': ')} is required"}
        return None

    try:
        return int(value)
    except ValueError:
        return {"error": f"{label.strip(': ')} must be an integer"}


async def prompt_server_create_payload(process):
    process.stdout.write("Interactive server creation\n")
    process.stdout.write("Fill connection details.\n\n")

    server_name = await prompt_input(process, "Server name: ")
    if not server_name:
        return {"error": "Server name is required"}

    platform = await prompt_input(process, "Platform: ")
    if not platform:
        return {"error": "Platform is required"}

    host = await prompt_input(process, "Host: ")
    if not host:
        return {"error": "Host is required"}

    port = await prompt_int(process, "Port: ", required=True)
    if isinstance(port, dict):
        return port

    username = await prompt_input(process, "Username: ")
    if not username:
        return {"error": "Username is required"}

    password = await prompt_input(process, "Platform password: ")
    if not password:
        return {"error": "Platform password is required"}

    return {
        "server_name": server_name,
        "platform": platform,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }


async def prompt_vm_create_payload(process) -> dict:
    payload = {}

    process.stdout.write("Interactive VM creation\n\n")

    # VMID
    process.stdout.write("VM ID (optional): ")
    value = (await process.stdin.readline()).strip()
    if value:
        try:
            payload["vmid"] = int(value)
        except ValueError:
            return {"error": "vmid must be integer"}

    # NAME
    process.stdout.write("VM name (optional): ")
    value = (await process.stdin.readline()).strip()
    if value:
        payload["name"] = value

    # MEMORY
    process.stdout.write("Memory in MB (optional): ")
    value = (await process.stdin.readline()).strip()
    if value:
        try:
            payload["memory_mb"] = int(value)
        except ValueError:
            return {"error": "memory_mb must be integer"}

    # CPU
    cpu = {}

    process.stdout.write("CPU cores (optional): ")
    value = (await process.stdin.readline()).strip()
    if value:
        try:
            cpu["cores"] = int(value)
        except ValueError:
            return {"error": "cores must be integer"}

    process.stdout.write("CPU sockets (optional): ")
    value = (await process.stdin.readline()).strip()
    if value:
        try:
            cpu["sockets"] = int(value)
        except ValueError:
            return {"error": "sockets must be integer"}

    process.stdout.write("CPU type (optional, e.g. host): ")
    value = (await process.stdin.readline()).strip()
    if value:
        cpu["type"] = value

    if cpu:
        payload["cpu"] = cpu

    # GUEST
    process.stdout.write("Guest OS (optional, e.g. linux/windows): ")
    value = (await process.stdin.readline()).strip()
    if value:
        payload["guest"] = value

    # SOURCE
    process.stdout.write("Source type (optional: iso/template/backup): ")
    value = (await process.stdin.readline()).strip().lower()

    if value:
        source = {"type": value}

        if value == "iso":
            process.stdout.write("ISO storage_id: ")
            storage = (await process.stdin.readline()).strip()

            process.stdout.write("ISO path: ")
            path = (await process.stdin.readline()).strip()

            if not storage or not path:
                return {"error": "ISO requires storage_id and path"}

            source["storage_id"] = storage
            source["path"] = path

        elif value == "template":
            process.stdout.write("Template VMID: ")
            vmid = (await process.stdin.readline()).strip()

            if not vmid.isdigit():
                return {"error": "Template vmid must be integer"}

            source["vmid"] = int(vmid)

        elif value == "backup":
            process.stdout.write("Backup storage_id: ")
            storage = (await process.stdin.readline()).strip()

            process.stdout.write("Backup path: ")
            path = (await process.stdin.readline()).strip()

            if not storage or not path:
                return {"error": "Backup requires storage_id and path"}

            source["storage_id"] = storage
            source["path"] = path

        else:
            return {"error": f"Unsupported source type: {value}"}

        payload["source"] = source

    # DISKS
    disks = []

    while True:
        process.stdout.write("Add disk? (y/N): ")
        value = (await process.stdin.readline()).strip().lower()

        if value != "y":
            break

        process.stdout.write("  Disk slot (e.g. scsi0): ")
        slot = (await process.stdin.readline()).strip()

        process.stdout.write("  Storage ID: ")
        storage = (await process.stdin.readline()).strip()

        if not slot or not storage:
            return {"error": "Disk requires slot and storage_id"}

        disk = {
            "slot": slot,
            "storage_id": storage,
        }

        process.stdout.write("  Disk size GB: ")
        size = (await process.stdin.readline()).strip()

        if not size.isdigit():
            return {"error": "Disk size must be integer"}

        disk["size_gb"] = int(size)

        disks.append(disk)

    if disks:
        payload["disks"] = disks

    # NETWORKS
    networks = []

    while True:
        process.stdout.write("Add network? (y/N): ")
        value = (await process.stdin.readline()).strip().lower()

        if value != "y":
            break

        process.stdout.write("  Slot (e.g. net0): ")
        slot = (await process.stdin.readline()).strip()

        process.stdout.write("  Bridge (e.g. vmbr0): ")
        bridge = (await process.stdin.readline()).strip()

        if not slot or not bridge:
            return {"error": "Network requires slot and bridge"}

        networks.append({
            "slot": slot,
            "network_id": bridge,
            "connected": True
        })

    if networks:
        payload["networks"] = networks

    # OPTIONS
    options = {}

    process.stdout.write("Autostart? (y/N): ")
    value = (await process.stdin.readline()).strip().lower()
    options["autostart"] = value == "y"

    process.stdout.write("Start after create? (y/N): ")
    value = (await process.stdin.readline()).strip().lower()
    options["start_after_create"] = value == "y"

    if options:
        payload["options"] = options

    return payload


async def handle_server_command(process, session: CliSession, parts: list[str]):
    if len(parts) < 2:
        return {"error": "Missing server subcommand"}

    subcommand = parts[1]

    if subcommand == "list":
        return session.server_list()

    if subcommand == "create":
        payload = await prompt_server_create_payload(process)
        if isinstance(payload, dict) and payload.get("error"):
            return payload

        return session.server_create(
            server_name=payload["server_name"],
            platform=payload["platform"],
            host=payload["host"],
            port=payload["port"],
            username=payload["username"],
            password=payload["password"],
        )

    if subcommand == "reconnect":
        if len(parts) < 3:
            return {"error": "Usage: server reconnect <server_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        password = await prompt_input(process, "Platform password: ")
        return session.server_open(server_id, password)

    return {"error": f"Unknown server subcommand: {subcommand}"}


async def handle_node_command(process, session: CliSession, parts: list[str]):
    if len(parts) < 2:
        return {"error": "Missing node subcommand"}

    subcommand = parts[1]

    if subcommand == "show":
        if len(parts) < 4:
            return {"error": "Usage: node show <server_id> <node_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        node_id = parts[3]
        return session.node_show(server_id, node_id)

    return {"error": f"Unknown node subcommand: {subcommand}"}


async def handle_vm_command(process, session: CliSession, parts: list[str]):
    if len(parts) < 2:
        return {"error": "Missing vm subcommand"}

    subcommand = parts[1]

    if subcommand == "show":
        if len(parts) < 5:
            return {"error": "Usage: vm show <server_id> <node_id> <vm_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        node_id = parts[3]

        try:
            vm_id = int(parts[4])
        except ValueError:
            return {"error": "vm_id must be an integer"}

        return session.vm_show(server_id, node_id, vm_id)

    if subcommand in {"start", "stop", "reboot", "shutdown"}:
        if len(parts) < 5:
            return {"error": f"Usage: vm {subcommand} <server_id> <node_id> <vm_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        node_id = parts[3]

        try:
            vm_id = int(parts[4])
        except ValueError:
            return {"error": "vm_id must be an integer"}

        return session.vm_action(
            server_id=server_id,
            node_id=node_id,
            vm_id=vm_id,
            action=subcommand,
        )

    if subcommand == "destroy":
        if len(parts) < 5:
            return {"error": "Usage: vm destroy <server_id> <node_id> <vm_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        node_id = parts[3]

        try:
            vm_id = int(parts[4])
        except ValueError:
            return {"error": "vm_id must be an integer"}

        return session.vm_destroy(
            server_id=server_id,
            node_id=node_id,
            vm_id=vm_id,
        )

    if subcommand == "create":
        if len(parts) < 4:
            return {"error": "Usage: vm create <server_id> <node_id>"}

        try:
            server_id = int(parts[2])
        except ValueError:
            return {"error": "server_id must be an integer"}

        node_id = parts[3]

        payload = await prompt_vm_create_payload(process)
        if isinstance(payload, dict) and payload.get("error"):
            return payload

        return session.vm_create(
            server_id=server_id,
            node_id=node_id,
            payload=payload,
        )

    return {"error": f"Unknown vm subcommand: {subcommand}"}


async def dispatch_command(process, session: CliSession, line: str):
    parts = shlex.split(line)

    if not parts:
        return None

    command = parts[0]

    if command == "help":
        return format_help()

    if command == "server":
        return await handle_server_command(process, session, parts)

    if command == "node":
        return await handle_node_command(process, session, parts)

    if command == "vm":
        return await handle_vm_command(process, session, parts)

    return {"error": f"Unknown command: {command}"}


def create_process_factory(platform_gateway):
    async def handle_client(process):
        user = get_authenticated_user(process)

        if not user:
            process.stdout.write("Authenticated user not found in database.\n")
            process.exit(1)
            return

        session = CliSession(
            platform_gateway=platform_gateway,
            user={
                "id": user.id,
                "username": user.username,
            },
        )

        process.stdout.write(f"CLI started over SSH as {user.username}\n")
        process.stdout.write("Type 'help' to see available commands.\n\n")

        while True:
            process.stdout.write("VPM (CLI)> ")
            line = await process.stdin.readline()

            if not line:
                break

            line = line.strip()
            if not line:
                continue

            if line in {"exit", "quit"}:
                process.stdout.write("Bye\n")
                break

            try:
                result = await dispatch_command(process, session, line)
                if result is not None:
                    if isinstance(result, str):
                        process.stdout.write(result + "\n")
                    else:
                        process.stdout.write(
                            json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n"
                        )
            except Exception as exc:
                process.stdout.write(
                    json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False, default=str) + "\n"
                )

    return handle_client


async def start_ssh_server(platform_gateway, host="0.0.0.0", port=8001, host_key_path="ssh_host_key"):
    return await asyncssh.create_server(
        MySSHServer,
        host,
        port,
        server_host_keys=[host_key_path],
        process_factory=create_process_factory(platform_gateway),
    )