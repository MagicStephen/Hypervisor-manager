from urllib.parse import quote
from pyVmomi import vim
import requests
from pyVim.task import WaitForTask
import re
import os
from datetime import datetime, timedelta, timezone
from config import BACKUP_ROOT
from platforms.esxi.connection import EsxiConnection


class EsxiNodeApi:
    """
    API wrapper pro práci s ESXi/vSphere uzly.

    Zajišťuje čtení stavu hostů, metrik, storage, storage obsahu,
    sítí, tasků a systémových logů.

    Args:
        connection: Objekt zajišťující komunikaci s ESXi/vSphere API.
    """

    def __init__(self, connection: EsxiConnection):
        """
        Inicializuje API klienta pro práci s ESXi/vSphere uzly.

        Args:
            connection: Připojení k ESXi/vSphere.
        """
        self.conn = connection

    def get_node_status(self, node_id, params: list) -> dict:
        """
        Vrátí vybrané stavové informace o ESXi hostu.

        Args:
            node_id: Identifikátor ESXi hosta.
            params: Seznam požadovaných metrik.

        Returns:
            Slovník obsahující pouze vyžádané metriky.
        """

        host = self.conn.get_entity_by_moid(node_id, vim.HostSystem)
        
        summary = host.summary
        hardware = summary.hardware
        quick = summary.quickStats
        product = host.config.product
        
        disk_total, disk_free, disk_used = self._get_host_storage(host)

        metric_paths = {
            "uptime": host.summary.quickStats.uptime,

            "cpu_usage": int(quick.overallCpuUsage) / (int(hardware.cpuMhz) * int(hardware.numCpuCores)),
            "cpu_num": hardware.numCpuThreads,
            "cpu_model": hardware.cpuModel,
            "cpu_cores": hardware.numCpuCores,
            "cpu_sockets": hardware.numCpuPkgs,

            "memory_total": hardware.memorySize,
            "memory_free": int(hardware.memorySize) - (int(quick.overallMemoryUsage) * 1024 * 1024),
            "memory_used": int(quick.overallMemoryUsage * 1024 * 1024),

            "disk_total": disk_total,
            "disk_free": disk_free,
            "disk_used": disk_used,

            "swap_total": None,
            "swap_used": None, 

            "sysname": product.name,
            "release": product.version,
            "version": product.build
        }

        res = {}

        for param in params:
            val = metric_paths.get(param, None)

            if not val:
                continue
            
            res.update({param: val})

        return res
    
    def get_node_time_metrics(
        self,
        entity_id: str,
        interval: str = "hour",
        cf: str = "AVERAGE",
        metrics: list | None = None
    ) -> list[dict]:
        """
        Vrátí časovou řadu metrik ESXi hosta z vSphere performance manageru.

        Args:
            entity_id: Identifikátor ESXi hosta.
            interval: Časový interval (hour, day, week, month, year).
            cf: Konsolidační funkce (AVERAGE, MIN, MAX).
            metrics: Seznam požadovaných metrik.

        Returns:
            Seznam bodů časové řady.
        """

        entity = self.conn.get_entity_by_moid(entity_id, vim.HostSystem)
        if not entity:
            raise ValueError(f"Node '{entity_id}' not found")

        perf_manager = self.conn.content.perfManager

        metric_map = {
            "cpu_usage": "cpu.usagemhz",
            "memory_used": "mem.consumed",
            "net_in": "net.received",
            "net_out": "net.transmitted",
            "swap_used": "mem.swapused",
        }

        cf_map = {
            "AVERAGE": "average",
            "MIN": "minimum",
            "MAX": "maximum",
        }

        intervals = {
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31536000,
        }

        cf_small = cf_map.get(cf.upper())
        if not cf_small:
            raise ValueError(f"Unsupported cf: {cf}")

        seconds = intervals.get(interval)
        if not seconds:
            raise ValueError(f"Unsupported interval: {interval}")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(seconds=seconds)

        provider = perf_manager.QueryPerfProviderSummary(entity=entity)

        if interval == "hour":
            interval_id = provider.refreshRate
        else:
            historical = list(getattr(perf_manager, "historicalInterval", []) or [])
            if not historical:
                return []

            target_map = {
                "day": 300,
                "week": 1800,
                "month": 7200,
                "year": 86400,
            }

            target = target_map[interval]
            interval_id = min(
                historical,
                key=lambda x: abs(x.samplingPeriod - target)
            ).samplingPeriod

        metrics = metrics or list(metric_map.keys())

        counter_lookup = {
            f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType}": c
            for c in perf_manager.perfCounter
        }

        metric_ids = []
        reverse_map = {}

        for alias in metrics:
            base_name = metric_map.get(alias)
            if base_name is None:
                continue

            full_name = f"{base_name}.{cf_small}"
            counter = counter_lookup.get(full_name)
            if not counter:
                continue

            metric_ids.append(
                vim.PerformanceManager.MetricId(
                    counterId=counter.key,
                    instance=""
                )
            )
            reverse_map[counter.key] = alias

        if not metric_ids:
            return []

        query = vim.PerformanceManager.QuerySpec(
            entity=entity,
            metricId=metric_ids,
            intervalId=interval_id,
            startTime=start_time,
            endTime=end_time,
        )

        results = perf_manager.QueryPerf(querySpec=[query])
        if not results:
            return []

        result = results[0]

        data = {}
        for sample in result.sampleInfo:
            ts = int(sample.timestamp.timestamp())
            data[ts] = {"time": ts}

        hardware = entity.summary.hardware
        cpu_capacity = int(hardware.cpuMhz) * int(hardware.numCpuCores)

        for value in result.value:
            alias = reverse_map.get(value.id.counterId)
            if not alias:
                continue

            for i, v in enumerate(value.value):
                ts = int(result.sampleInfo[i].timestamp.timestamp())

                if v is None:
                    data[ts][alias] = None
                    continue

                if alias in ["memory_used", "net_in", "net_out", "swap_used"]:
                    data[ts][alias] = int(v) * 1024
                elif alias == "cpu_usage":
                    data[ts][alias] = float(v) / cpu_capacity if cpu_capacity else float(v)
                else:
                    data[ts][alias] = v

        return [data[ts] for ts in sorted(data.keys())]

    def get_node_storage(self, node_id) -> dict:
        """
        Vrátí seznam datastore/storage dostupných na ESXi hostu.

        Args:
            node_id: Identifikátor ESXi hosta.

        Returns:
            Seznam storage s kapacitou, stavem a podporovanými typy obsahu.
        """

        host = self.conn.get_entity_by_moid(node_id, vim.HostSystem)

        storages = []

        for ds in host.datastore:
            summary = ds.summary

            total = int(summary.capacity or 0)
            avail = int(summary.freeSpace or 0)
            used = max(total - avail, 0)

            accessible = bool(summary.accessible)
            shared = int(bool(summary.multipleHostAccess))

            ds_type = (summary.type or "unknown").lower()
            content = ds_type.lower()
            allowed_upload = []

            if ds_type in {"vmfs", "vsan", "nfs", "nfs41"}:
                content = ["iso", "images"]
                allowed_upload = ["iso", "images"]
            else:
                content = ds_type

            storages.append({
                "storage_id": ds._moId,
                "active": int(accessible),
                "shared": shared,
                "type": ds_type,
                "used_fraction": (used / total) if total else 0,
                "storage": summary.name,
                "total": total,
                "avail": avail,
                "used": used,
                "enabled": int(accessible),
                "content": content,
                "upload_allowed": allowed_upload
            })

        backup_dir = os.path.join(BACKUP_ROOT, "esxi")
        if os.path.isdir(backup_dir):
            total = 0
            for entry in os.scandir(backup_dir):
                if entry.is_file():
                    total += entry.stat().st_size

            storages.append({
                "storage_id": "esxi-local-backups",
                "storage": "Local Backups",
                "type": "dir",
                "total": total,
                "used": total,
                "used_fraction": 1 if total else 0,
                "avail": 0,
                "active": 1,
                "enabled": 1,
                "shared": 0,
                "content": ["backup"],
                "upload_allowed": [],
            })

        return storages

    def get_node_storage_content(self, node_id, storage_id) -> dict:
        """
        Vrátí obsah zvoleného datastore nebo lokálního backup úložiště.

        Args:
            node_id: Identifikátor ESXi hosta.
            storage_id: Identifikátor datastore nebo speciální storage pro zálohy.

        Returns:
            Seznam položek dostupných ve storage.
        """

        host = self.conn.get_entity_by_moid(node_id, vim.HostSystem)

        def _map_content(file_obj) -> str | None:
            name = (getattr(file_obj, "path", "") or "").lower()

            if name.endswith(".iso"):
                return "iso"

            if name.endswith((".vmem", ".vmsn")) or re.search(r"-\d{6}\.vmdk$", name):
                return "backup"

            if name.endswith((".vmdk", ".vswp", ".nvram", ".vmsd", ".vmx", ".lck")):
                return "images"

            if name.endswith((".yaml", ".yml", ".json", ".xml", ".txt", ".cfg", ".conf", ".ps1", ".sh", ".py")):
                return "snippets"

            return None
        
        if storage_id == "esxi-local-backups":
            backup_dir = BACKUP_ROOT

            if not os.path.isdir(backup_dir):
                return []

            items = []

            for vm_id in os.listdir(backup_dir):
                vm_path = os.path.join(backup_dir, vm_id)

                if not os.path.isdir(vm_path):
                    continue

                for backup_name in os.listdir(vm_path):
                    full_path = os.path.join(vm_path, backup_name)

                    # ignoruj nedokončené backupy
                    if backup_name.endswith(".part"):
                        continue

                    if not os.path.isdir(full_path):
                        continue

                    stat = os.stat(full_path)
                    rel_path = os.path.relpath(full_path, backup_dir)

                    items.append({
                        "volid": rel_path,
                        "name": backup_name,
                        "content": "backup",
                        "size": 0,  # složka → size neřeš
                        "mtime": int(stat.st_mtime),
                        "format": "esxi-folder",
                        "path": rel_path,   # důležité → RELATIVE path
                    })

            items.sort(key=lambda x: x["mtime"], reverse=True)
            return items

        for ds in host.datastore:
            if ds._moId != storage_id:
                continue

            browser = ds.browser

            spec = vim.host.DatastoreBrowser.SearchSpec()
            spec.matchPattern = ["*"]

            details = vim.host.DatastoreBrowser.FileInfo.Details()
            details.fileSize = True
            details.modification = True
            details.fileType = True
            details.fileOwner = True
            spec.details = details

            datastore_path = f"[{ds.name}]"

            task = browser.SearchDatastoreSubFolders_Task(
                datastorePath=datastore_path,
                searchSpec=spec
            )

            WaitForTask(task)
            results = task.info.result or []

            items = []

            for folder_result in results:
                raw_folder_path = getattr(folder_result, "folderPath", "") or ""

                prefix = f"[{storage_id}] "
                folder_path = raw_folder_path[len(prefix):] if raw_folder_path.startswith(prefix) else raw_folder_path
                folder_path = folder_path.strip()

                if folder_path.rstrip("/").endswith(".sdd.sf"):
                    continue

                vm_folder = folder_path.rstrip("/")
                vm_name = vm_folder.split("/")[-1] if vm_folder else None
                vm_cache = {}
                    
                if vm_name:
                    vm_cache[vm_name] = self.conn.get_entity_by_name(vm_name, vim.VirtualMachine)

                vm = vm_cache[vm_name]

                for f in getattr(folder_result, "file", []) or []:
                    content = _map_content(f)
                    if content is None:
                        continue

                    name = f.path
                    volid = None

                    if storage_id in folder_path:
                        volid = f"{folder_path}/{name}"
                    else:
                        volid = f"[{storage_id}] {folder_path}/{name}"

                    item = {
                        "volid": volid,
                        "name": name,
                        "ctime": getattr(f, "modification", None),
                        "size": getattr(f, "fileSize", 0),
                        "content": content,
                    }

                    if content in ("images", "backup") and vm:
                        item["vmid"] = vm._moId

                    items.append(item)

            return items

        return []
    
    def upload_node_storage_file(self, node_id, storage_id, content_type, file) -> dict:
        """
        Nahraje soubor do vybraného ESXi datastore.

        Args:
            node_id: Identifikátor ESXi hosta.
            storage_id: Identifikátor datastore.
            content_type: MIME typ uploadovaného souboru.
            file: Uploadovaný soubor.

        Returns:
            Výsledek uploadu obsahující název datastore a souboru.

        Raises:
            ValueError: Pokud host, storage nebo session cookie nejsou dostupné.
        """

        host = self.conn.get_entity_by_moid(node_id, vim.HostSystem)
        if not host:
            raise ValueError(f"Host {node_id} not found")

        target_ds = None
        for ds in host.datastore:
            if ds._moId == storage_id:
                target_ds = ds
                break

        if not target_ds:
            raise ValueError(f"Storage {storage_id} is not available for {node_id}")

        datastore_name = target_ds.summary.name
        dc_path = "ha-datacenter"
        remote_name = file.filename

        url = (
            f"https://{self.conn.host}/folder/{quote(remote_name)}"
            f"?dsName={quote(datastore_name)}"
            f"&dcPath={quote(dc_path)}"
        )

        raw_cookie = self.conn.si._stub.cookie or ""
        m = re.search(r'vmware_soap_session="?([^";]+)"?', raw_cookie)
        if not m:
            raise ValueError(f"Cannot parse vmware_soap_session from stub cookie: {raw_cookie!r}")

        session_id = m.group(1)

        file.file.seek(0)
        payload = file.file.read()

        headers = {
            "Cookie": f'vmware_soap_session="{session_id}"',
            "Content-Type": content_type or "application/octet-stream",
            "Content-Length": str(len(payload)),
        }

        try:
            res = requests.put(
                url,
                data=payload,
                headers=headers,
                verify=False,
                timeout=600,
            )
        except requests.exceptions.SSLError as e:
            raise ValueError(
                f"SSL upload failed for URL {url} with datastore '{datastore_name}': {e}"
            ) from e

        if not res.ok:
            raise ValueError(f"Upload failed: HTTP {res.status_code} - {res.text}")

        return {
            "uploaded": True,
            "storage": datastore_name,
            "filename": remote_name,
        }

    def delete_node_storage_content(self, node_id, storage_id, vol_id) -> dict:
        """
        Smaže soubor z datastore.

        Args:
            node_id: Identifikátor ESXi hosta.
            storage_id: Identifikátor datastore.
            vol_id: Cesta k souboru ve vSphere datastore formátu.

        Raises:
            ValueError: Pokud storage nebo soubor neexistuje.
            RuntimeError: Pokud je soubor zamčený nebo jej nelze smazat.
        """

        host = self.conn.get_entity_by_moid(node_id, vim.HostSystem)
        
        target_ds = None

        for ds in host.datastore:
            if ds.summary.name != storage_id:
                continue

            target_ds = ds
            break

        if not target_ds:
            raise ValueError(f"Storage {storage_id} is not available for {node_id}")

        try:
            task = self.conn.content.fileManager.DeleteDatastoreFile_Task(
                name=vol_id
            )

            WaitForTask(task)

        except vim.fault.FileNotFound:
            raise ValueError(f"File {vol_id} does not exist")

        except vim.fault.FileLocked:
            raise RuntimeError(f"File {vol_id} is in use or locked")

        except vim.fault.CannotDeleteFile:
            raise RuntimeError(f"File {vol_id} cannot be deleted")
        
    def get_node_networks(self, node: str):
        """
        Vrátí sítě dostupné na ESXi hostu.

        Args:
            node: Identifikátor ESXi hosta.

        Returns:
            Seznam standardních a distribuovaných sítí použitelných pro VM.
        """

        host = self.conn.get_entity_by_moid(node, vim.HostSystem)
        if not host:
            raise ValueError(f"Host '{node}' not found")

        networks = []

        for net in getattr(host, "network", []):
            name = getattr(net, "name", None)
            if not name:
                continue

            if isinstance(net, vim.Network):
                networks.append({
                    "id": name,
                    "name": name,
                    "active": True,
                    "type": "standard",
                    "default": name == "VM Network",
                })
            elif isinstance(net, vim.dvs.DistributedVirtualPortgroup):
                networks.append({
                    "id": name,
                    "name": name,
                    "active": True,
                    "type": "distributed",
                    "default": False,
                })

        return networks

    def get_task_status(self, node: str, task_id: str) -> dict:
        """
        Vrátí detailní stav úlohy z vSphere recent tasks.

        Args:
            node: Identifikátor ESXi hosta.
            task_id: Identifikátor tasku.

        Returns:
            Stav a metadata úlohy.
        """

        host = self.conn.get_entity_by_moid(node, vim.HostSystem)
        if not host:
            raise ValueError(f"Host '{node}' not found")

        task_manager = self.conn.si.content.taskManager
        recent_tasks = list(getattr(task_manager, "recentTask", []) or [])

        task = next(
            (t for t in recent_tasks if getattr(t, "_moId", None) == task_id),
            None
        )

        if not task:
            return {
                "task_id": task_id,
                "node": node,
                "status": "unknown",
                "exitstatus": "Task not found in recentTask",
                "starttime": None,
                "endtime": None,
                "type": None,
                "id": None,
                "user": None,
                "upid": None,
                "progress": None,
            }

        info = task.info

        state_map = {
            vim.TaskInfo.State.queued: "queued",
            vim.TaskInfo.State.running: "running",
            vim.TaskInfo.State.success: "stopped",
            vim.TaskInfo.State.error: "error",
        }

        error_msg = None
        if info.state == vim.TaskInfo.State.error and getattr(info, "error", None):
            error_msg = getattr(info.error, "localizedMessage", None) or str(info.error)

        task_type = None
        if getattr(info, "descriptionId", None):
            task_type = info.descriptionId
        elif getattr(info, "name", None):
            task_type = str(info.name)

        user = None
        reason = getattr(info, "reason", None)
        if reason and hasattr(reason, "userName"):
            user = reason.userName

        return {
            "task_id": task_id,
            "node": node,
            "status": state_map.get(info.state, "unknown"),
            "exitstatus": error_msg,
            "starttime": int(info.startTime.timestamp()) if getattr(info, "startTime", None) else None,
            "endtime": int(info.completeTime.timestamp()) if getattr(info, "completeTime", None) else None,
            "type": task_type,
            "id": getattr(info, "key", None),
            "user": user,
            "upid": getattr(task, "_moId", None),
            "progress": getattr(info, "progress", None),
        }

    def get_node_logs(self, node, limit: int = 100) -> dict:
        """
        Vrátí systémové logy ESXi hosta z diagnostic manageru.

        Args:
            node: Identifikátor ESXi hosta.
            limit: Maximální počet vrácených řádků.

        Returns:
            Slovník obsahující seznam log řádků.
        """

        if not self.conn.content:
            raise ConnectionError("Not connected to vSphere")

        diag = self.conn.content.diagnosticManager
        api_type = getattr(getattr(self.conn.content, "about", None), "apiType", None)

        if api_type == "HostAgent":
            result = diag.BrowseDiagnosticLog(
                key="hostd",
                start=None,
                lines=limit,
            )
        else:
            host_obj = self.conn.get_entity_by_moid(node, vim.HostSystem)

            if not host_obj:
                raise ValueError(f"Host '{node}' not found")

            result = diag.BrowseDiagnosticLog(
                host=host_obj,
                key="hostd",
                start=None,
                lines=limit,
            )

        return {
            "lines": [line.rstrip("\n") for line in (result.lineText or [])]
        }
    
    def _get_host_storage(self, host):
        """
        Spočítá celkovou, volnou a použitou kapacitu datastore hosta.

        Args:
            host: Objekt typu vim.HostSystem.

        Returns:
            Trojice hodnot: celkem, volné místo, použité místo v bajtech.
        """

        total = 0
        free = 0

        for ds in host.datastore:
            try:
                summary = ds.summary
                if not summary or not summary.accessible:
                    continue

                total += int(summary.capacity or 0)
                free += int(summary.freeSpace or 0)
            except Exception:
                continue

        used = total - free
        return total, free, used