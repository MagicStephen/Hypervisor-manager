from sqlalchemy.orm import Session
from fastapi import HTTPException

from database.database import SessionLocal
from services.server_service import ServerService
from services.node_service import NodeService
from services.vm_service import VmService


def get_db_session() -> Session:
    return SessionLocal()

def format_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "No data."

    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]

    def make_row(values):
        return "  ".join(
            str(values[i]).ljust(widths[i])
            for i in range(len(values))
        )

    lines = [
        make_row(headers),
        make_row(["-" * width for width in widths]),
    ]

    lines.extend(make_row(row) for row in rows)

    return "\n".join(lines)

def format_server_list(servers: list[dict]) -> str:
    if not servers:
        return "No servers found."

    lines = []

    for server in servers:
        status = "connected" if server.get("connected") else "disconnected"

        lines.append("=" * 80)
        lines.append(
            f"Server {server.get('server_id')} | "
            f"{server.get('name')} | "
            f"{server.get('platform')} | "
            f"{status}"
        )
        lines.append(f"Host: {server.get('host')} | User: {server.get('username')}")
        lines.append("-" * 80)

        clusters = server.get("clusters", [])

        if not clusters:
            lines.append("Topology: not loaded")
            lines.append("")
            continue

        for cluster in clusters:
            lines.append(f"Cluster: {cluster.get('cluster', 'unknown')}")
            lines.append("")

            node_rows = []
            vm_rows = []
            template_rows = []

            for node in cluster.get("nodes", []):
                node_id = str(node.get("id", ""))
                node_name = str(node.get("name", ""))
                node_host = str(node.get("host", ""))
                node_status = "online" if node.get("status") else "offline"

                node_rows.append([
                    node_id,
                    node_name,
                    node_host,
                    node_status,
                ])

                for vm in node.get("vms", []):
                    vm_rows.append([
                        node_name,
                        str(vm.get("id", "")),
                        str(vm.get("name", "")),
                        str(vm.get("status", "")),
                    ])

                for template in node.get("templates", []):
                    template_rows.append([
                        node_name,
                        str(template.get("id", "")),
                        str(template.get("name", "")),
                        str(template.get("status", "")),
                    ])

            lines.append("Nodes:")
            lines.append(format_table(
                ["ID", "NAME", "HOST", "STATUS"],
                node_rows,
            ))

            if vm_rows:
                lines.append("")
                lines.append("VMs:")
                lines.append(format_table(
                    ["NODE", "ID", "NAME", "STATUS"],
                    vm_rows,
                ))

            if template_rows:
                lines.append("")
                lines.append("Templates:")
                lines.append(format_table(
                    ["NODE", "ID", "NAME", "STATUS"],
                    template_rows,
                ))

            lines.append("")

    return "\n".join(lines).strip()

def format_topology(topology: dict) -> str:
    clusters = topology.get("clusters", [])

    if not clusters:
        return "No topology available."

    lines = []

    for cluster in clusters:
        lines.append(f"Cluster: {cluster.get('cluster', 'unknown')}")
        lines.append("")

        node_rows = []
        vm_rows = []
        template_rows = []

        for node in cluster.get("nodes", []):
            node_name = str(node.get("name", ""))

            node_rows.append([
                str(node.get("id", "")),
                node_name,
                str(node.get("host", "")),
                "online" if node.get("status") else "offline",
            ])

            for vm in node.get("vms", []):
                vm_rows.append([
                    node_name,
                    str(vm.get("id", "")),
                    str(vm.get("name", "")),
                    str(vm.get("status", "")),
                ])

            for template in node.get("templates", []):
                template_rows.append([
                    node_name,
                    str(template.get("id", "")),
                    str(template.get("name", "")),
                    str(template.get("status", "")),
                ])

        lines.append("Nodes:")
        lines.append(format_table(["ID", "NAME", "HOST", "STATUS"], node_rows))

        if vm_rows:
            lines.append("")
            lines.append("VMs:")
            lines.append(format_table(["NODE", "ID", "NAME", "STATUS"], vm_rows))

        if template_rows:
            lines.append("")
            lines.append("Templates:")
            lines.append(format_table(["NODE", "ID", "NAME", "STATUS"], template_rows))

        lines.append("")

    return "\n".join(lines).strip()


def format_server_reconnect(result: dict) -> str:
    lines = [
        "=" * 80,
        f"Server {result.get('server_id')} | connected",
        "-" * 80,
        format_topology(result.get("topology", {})),
    ]

    return "\n".join(lines).strip()


def format_vm_show(vm: dict, server_id: int, node_id: str, vm_id: int) -> str:
    if not vm:
        return "VM data unavailable."

    rows = [
        ["Server ID", str(server_id)],
        ["Node ID", node_id],
        ["VM ID", str(vm_id)],
    ]

    for key, value in vm.items():
        rows.append([str(key), str(value)])

    return "\n".join([
        "=" * 80,
        f"VM {vm_id} | detail",
        "-" * 80,
        format_table(["FIELD", "VALUE"], rows),
    ])


def format_vm_action(result: dict, server_id: int, node_id: str, vm_id: int, action: str) -> str:
    return "\n".join([
        "=" * 80,
        f"VM {vm_id} | {action}",
        "-" * 80,
        format_table(
            ["FIELD", "VALUE"],
            [
                ["Server ID", str(server_id)],
                ["Node ID", node_id],
                ["VM ID", str(vm_id)],
                ["Action", action],
                ["Result", result.get("message", "Action completed")],
            ],
        ),
    ])


def format_vm_destroy(server_id: int, node_id: str, vm_id: int) -> str:
    return "\n".join([
        "=" * 80,
        f"VM {vm_id} | destroy",
        "-" * 80,
        format_table(
            ["FIELD", "VALUE"],
            [
                ["Server ID", str(server_id)],
                ["Node ID", node_id],
                ["VM ID", str(vm_id)],
                ["Result", "VM destroyed successfully"],
            ],
        ),
    ])


def format_vm_create(result: dict, server_id: int, node_id: str) -> str:
    rows = [
        ["Server ID", str(server_id)],
        ["Node ID", node_id],
        ["Result", "VM created successfully"],
    ]

    if isinstance(result, dict):
        for key, value in result.items():
            rows.append([str(key), str(value)])

    return "\n".join([
        "=" * 80,
        "VM create",
        "-" * 80,
        format_table(["FIELD", "VALUE"], rows),
    ])

class CliSession:
    def __init__(self, platform_gateway, user=None):
        self.platform_gateway = platform_gateway
        self.state = {
            "user": user,
        }

    def _require_user(self):
        user = self.state.get("user")
        if not user:
            return None, {"error": "Not logged in"}
        return user, None

    def server_list(self):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            servers = ServerService.get_user_servers(
                user_id=user["id"],
                platform_gw=self.platform_gateway,
                db=db,
            )

            return format_server_list(servers)

        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def server_create(self, server_name: str, platform: str, host: str, port: int, username: str, password: str):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            topology = ServerService.connect(
                server_name=server_name,
                platform=platform,
                host=host,
                port=port,
                username=username,
                password=password,
                user_id=user["id"],
                platform_gw=self.platform_gateway,
                db=db,
            )

            return {
                "message": "Server connected successfully",
                "topology": topology,
            }
        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def server_open(self, server_id: int, password: str):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            topology = ServerService.reconnect(
                server_id=server_id,
                user_id=user["id"],
                password=password,
                platform_gw=self.platform_gateway,
                db=db,
            )

            result = {
                "message": "Server connected successfully",
                "server_id": server_id,
                "topology": topology,
            }

            return format_server_reconnect(result)

        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def node_show(self, server_id: int, node_id: str):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            return NodeService.get_node_summary(
                server_id=server_id,
                node_id=node_id,
                fields=[],
                user_id=user["id"],
                platform_gw=self.platform_gateway,
                db=db,
            )
        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def vm_show(self, server_id: int, node_id: str, vm_id: int):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            return VmService.get_vm_status(
                server_id=server_id,
                node_id=node_id,
                vm_id=str(vm_id),
                user_id=user["id"],
                params=[],
                platform_gw=self.platform_gateway,
                db=db,
            )
        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def vm_action(self, server_id: int, node_id: str, vm_id: int, action: str):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            result = VmService.set_vm_status(
                server_id=server_id,
                node_id=node_id,
                vm_id=str(vm_id),
                status=action,
                user_id=user["id"],
                platform_gw=self.platform_gateway,
                db=db,
            )

            return format_vm_action(result, server_id, node_id, vm_id, action)

        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def vm_destroy(self, server_id: int, node_id: str, vm_id: int):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            VmService.destroy_vm(
                server_id=server_id,
                node_id=node_id,
                vm_id=str(vm_id),
                user_id=user["id"],
                platform_gw=self.platform_gateway,
                db=db,
            )

            return format_vm_destroy(server_id, node_id, vm_id)

        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()

    def vm_create(self, server_id: int, node_id: str, payload: dict):
        user, err = self._require_user()
        if err:
            return err

        db = get_db_session()
        try:
            result = VmService.create_vm(
                server_id=server_id,
                node_id=node_id,
                user_id=user["id"],
                opt_parameters=payload,
                platform_gw=self.platform_gateway,
                db=db,
            )

            return format_vm_create(result, server_id, node_id)

        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            db.close()