from fastapi import UploadFile
from platforms.base.node import BaseNodeApi
from platforms.proxmox.connection import ProxmoxConnection

class ProxmoxNodeApi(BaseNodeApi):
    """
    API wrapper pro práci s Proxmox uzly.

    Args:
        connection: Objekt zajišťující HTTP komunikaci s Proxmox API.
    """

    def __init__(self, connection: ProxmoxConnection):

        self.conn = connection

        self.SHORT_PERIOD_METRICS = {
            "uptime": ["uptime"],
            "cpu_usage": ["cpu"],
            "cpu_num": ["cpuinfo", "cpus"],
            "cpu_model": ["cpuinfo", "model"],
            "cpu_cores": ["cpuinfo", "cores"],
            "cpu_sockets": ["cpuinfo", "sockets"],
            "memory_total": ["memory", "total"],
            "memory_free": ["memory", "free"],
            "memory_used": ["memory", "used"],
            "disk_total": ["rootfs", "total"],
            "disk_free": ["rootfs", "free"],
            "disk_used": ["rootfs", "used"],
            "swap_total": ["swap", "total"],
            "swap_used": ["swap", "used"],
            "pve_version": ["pveversion"],
            "sysname": ["current-kernel", "sysname"],
            "release": ["current-kernel", "release"],
            "version": ["current-kernel", "version"],
            "boot_mode": ["boot-info", "mode"],
        }

        self.RRD_METRICS = {
            "cpu_usage": "cpu",
            "load_avg": "loadavg",
            "memory_used": "memused",
            "net_in": "netin",
            "net_out": "netout",
            "io_wait": "iowait",
        }

    def get_nodes(self) -> list[dict]:
        """
        Vrátí seznam uzlů v clusteru.

        Kombinuje data z endpointů:
        
        - /cluster/status
        - /cluster/resources?type=node

        Returns:
            Seznam uzlů s jejich základními informacemi.
        """
        status_res = self.conn.request(
            method="GET",
            url=f"https://{self.conn.host}/api2/json/cluster/status",
        )

        resources_res = self.conn.request(
            method="GET",
            url=f"https://{self.conn.host}/api2/json/cluster/resources",
            params={"type": "node"},
        )

        status_items = status_res.get("data", [])
        resource_items = resources_res.get("data", [])

        cluster_name = None
        status_by_node = {}

        for item in status_items:
            if item.get("type") == "cluster":
                cluster_name = item.get("name")
                continue

            if item.get("type") != "node":
                continue

            node_name = item.get("name")
            if not node_name:
                continue

            status_by_node[node_name] = item

        nodes = []

        # Složení výsledku z resource dat a doplnění IP adresy
        for item in resource_items:
            name = item.get("node") or item.get("name")
            if not name:
                continue

            status_item = status_by_node.get(name, {})

            nodes.append(
                {
                    "id": name,
                    "name": name,
                    "status": item.get("status"),
                    "uptime": item.get("uptime"),
                    "ip": status_item.get("ip"),
                    "cluster": cluster_name,
                }
            )

        return nodes

    def get_node_status(self, node_id: str, params: list[str]) -> dict:
        """
        Vrátí vybrané stavové informace o uzlu.

        Args:
            node_id: Identifikátor uzlu.
            params: Seznam požadovaných metrik a informaci (cpu cores, cpu sockets, total memory...).

        Returns:
            Slovník obsahující pouze vyžádané metriky.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/status"
        result = self.conn.request(method="GET", url=url)["data"]

        res = {}

        # Mapování požadovaných parametrů na strukturu Proxmox odpovědi
        for param in params:
            param_map = self.SHORT_PERIOD_METRICS.get(param)

            if not param_map:
                continue

            parent = result.get(param_map[0])
            if parent is None:
                continue

            if len(param_map) == 1:
                res[param] = parent
                continue

            res[param] = parent.get(param_map[1])

        return res

    def get_node_time_metrics(
        self,
        node_id: str,
        interval: str = "hour",
        cf: str = "AVERAGE",
        metrics: list[str] | None = None,
    ) -> list[dict]:
        """
        Vrátí časovou řadu metrik uzlu z RRD databáze.

        Args:
            node_id: Identifikátor uzlu.
            interval: Časový interval (např. "hour", "day", "week").
            cf: Konsolidační funkce (např. "AVERAGE", "MAX").
            metrics: Seznam požadovaných metrik.

        Returns:
            Seznam bodů časové řady.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/rrddata"

        params = {
            "timeframe": interval,
            "cf": cf,
        }

        result = self.conn.request(method="GET", url=url, params=params)["data"]

        parsed_metrics = []

        # Převod Proxmox klíčů na interní názvy metrik
        for row_data in result:
            row = {"time": row_data.get("time")}

            for metric in metrics or []:
                metric_key = self.RRD_METRICS.get(metric)
                if not metric_key:
                    continue

                row[metric] = row_data.get(metric_key)

            parsed_metrics.append(row)

        return parsed_metrics

    def get_node_storage(self, node_id: str) -> dict:
        """
        Vrátí seznam storage dostupných na uzlu.

        Args:
            node_id: Identifikátor uzlu.

        Returns:
            Seznam storage s rozšířenými informacemi o podporovaném uploadu.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/storage"
        data = self.conn.request(method="GET", url=url)["data"]

        # Normalizace content položek a doplnění upload capabilities
        for storage in data:
            content = storage.get("content", "")
            storage["content"] = [
                item.strip() for item in content.split(",") if item.strip()
            ]

            storage["upload_allowed"] = []

            if "iso" in storage["content"]:
                storage["upload_allowed"].append("iso")

            if "vztmpl" in storage["content"]:
                storage["upload_allowed"].append("vztmpl")

            storage["storage_id"] = storage.get("storage")

        return data

    def get_node_storage_content(self, node_id: str, storage_id: str) -> dict:
        """
        Vrátí obsah zvoleného storage.

        Args:
            node_id: Identifikátor uzlu.
            storage_id: Identifikátor storage.

        Returns:
            Seznam položek dostupných ve storage.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/storage/{storage_id}/content"
        data = self.conn.request(method="GET", url=url)["data"]

        # Doplnění čitelného názvu souboru/volume z volid
        for item in data:
            volid = item.get("volid", "")
            name = volid.split("/")[-1] if "/" in volid else volid
            item["name"] = name

        return data

    def delete_node_storage_content(
        self, node_id: str, storage_id: str, vol_id: str
    ) -> dict:
        """
        Smaže položku ze storage.

        Args:
            node_id: Identifikátor uzlu.
            storage_id: Identifikátor storage.
            vol_id: Identifikátor volume.

        Returns:
            Výsledek operace vrácený Proxmox API.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/storage/{storage_id}/content/{vol_id}"
        return self.conn.request(method="DELETE", url=url)

    def upload_node_storage_file(
        self,
        node_id: str,
        storage_id: str,
        content_type: str,
        file: UploadFile,
    ) -> dict:
        """
        Nahraje soubor do storage.

        Args:
            node_id: Identifikátor uzlu.
            storage_id: Identifikátor storage.
            content_type: Typ obsahu (např. "iso", "vztmpl", "import").
            file: Uploadovaný soubor.

        Returns:
            Výsledek uploadu vrácený Proxmox API.

        Raises:
            ValueError: Pokud je předán nepodporovaný content type.
        """
        allowed_content_types = ("iso", "vztmpl", "import")

        if content_type not in allowed_content_types:
            raise ValueError(f"Unsupported content type: {content_type}")

        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/storage/{storage_id}/upload"

        files = {
            "filename": (file.filename, file.file, "application/octet-stream")
        }

        params = {
            "content": content_type,
            "filename": file.filename,
        }

        return self.conn.request(method="POST", url=url, params=params, files=files)

    def get_task_status(self, node_id: str, task_id: str) -> dict:
        """
        Vrátí detailní stav úlohy na uzlu.

        Args:
            node_id: Identifikátor uzlu.
            task_id: Identifikátor úlohy.

        Returns:
            Stav a metadata úlohy.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/tasks/{task_id}/status"
        result = self.conn.request(method="GET", url=url).get("data", {})

        return {
            "task_id": task_id,
            "node": node_id,
            "status": result.get("status"),
            "exitstatus": result.get("exitstatus"),
            "starttime": result.get("starttime"),
            "endtime": result.get("endtime"),
            "type": result.get("type"),
            "id": result.get("id"),
            "user": result.get("user"),
            "upid": result.get("upid"),
        }

    def get_node_networks(self, node_id: str) -> list[dict]:
        """
        Vrátí síťová rozhraní typu bridge dostupná na uzlu.

        Args:
            node_id: Identifikátor uzlu.

        Returns:
            Seznam network rozhraní.
        """
        res = self.conn.request(
            method="GET",
            url=f"https://{self.conn.host}/api2/json/nodes/{node_id}/network",
        )

        items = res.get("data", [])
        networks = []

        # Filtrace pouze bridge rozhraní použitelných pro VM
        for item in items:
            if item.get("type") != "bridge":
                continue

            iface = item.get("iface")
            if not iface:
                continue

            networks.append(
                {
                    "id": iface,
                    "name": iface,
                    "active": item.get("active") == 1,
                    "type": item.get("type"),
                    "default": iface == "vmbr0",
                }
            )

        return networks

    def get_node_logs(self, node_id: str, limit: int = 100) -> dict:
        """
        Vrátí systémové logy uzlu.

        Args:
            node_id: Identifikátor uzlu.
            limit: Maximální počet vrácených log řádků.

        Returns:
            Seznam logů limitovaný na hodnotu v argumentu (`limit`).
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_id}/syslog"
        logs = self.conn.request(method="GET", url=url, params={"limit": limit})

        log_lines = [item.get("t", "").rstrip("\n") for item in logs.get("data", [])]

        return {"lines": log_lines}