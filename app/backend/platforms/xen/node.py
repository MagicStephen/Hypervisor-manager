from platforms.base.node import BaseNodeApi
from collections import deque
import os
import time
import requests
from fastapi import UploadFile
from config import LOG_ROOT
from config import BACKUP_ROOT
from platforms.xen.connection import XenConnection
from urllib.parse import urlencode

class XenNodeApi(BaseNodeApi):
    """
    API wrapper pro práci s Xen uzly.

    Args:
        connection: Objekt zajišťující komunikaci s Xen API.
    """
    def __init__(self, connection: XenConnection):
        self.conn = connection
    
    def get_node_status(self, node_id: str, params: list[str]) -> dict:
        """
            Vrátí vybrané stavové informace o uzlu.

            Podle požadovaných parametrů kombinuje data z:

            - host record
            - RRD metrik
            - storage record

            Args:
                node_id: UUID uzlu.
                params: Seznam požadovaných metrik a informací.

            Returns:
                Slovník obsahující pouze vyžádané hodnoty.
        """
         
        params_set = set(params)

        rrd_required = {"cpu_usage", "memory_total", "memory_free", "memory_used", "load_avg", "io_wait"}
        disk_required = {"disk_total", "disk_used", "disk_free"}
        host_required = {
            "uptime", "cpu_model", "cpu_num", "cpu_cores", "cpu_sockets",
            "sysname", "release", "version", "boot_mode"
        }

        host_ref = None
        host = None

        if params_set & host_required:
            host_ref, host = self._get_node(node_id)
        elif params_set & disk_required:
            host_ref = self.conn.request(
                "POST",
                "host.get_by_uuid",
                [self.conn.session, node_id]
            )

        rrd_metrics = {}

        if params_set & rrd_required:
            rrd_rows = self.get_node_time_metrics(
                node_id=node_id,
                interval="current",
                ds=list(params_set & rrd_required)
            )

            rrd_metrics = rrd_rows[0] if rrd_rows else {}

        disk_metrics = {}
        if params_set & disk_required and host_ref:
            disk_metrics = self._get_node_storage_record(host_ref) or {}

        uptime_seconds = None
        if "uptime" in params_set and host:
            boot_time_str = host.get("other_config", {}).get("boot_time")
            uptime_seconds = int(time.time()) - int(float(boot_time_str)) if boot_time_str else 0

        cpu_info = host.get("cpu_info", {}) if host else {}
        cpu_count = int(cpu_info.get("cpu_count", 0) or 0) if cpu_info else None
        socket_count = int(cpu_info.get("socket_count", 0) or 0) if cpu_info else None
        threads_per_core = int(cpu_info.get("threads_per_core", 0) or 0) if cpu_info else None
        cpu_cores = (
            cpu_count // max(socket_count * threads_per_core, 1)
            if cpu_count is not None and socket_count is not None and threads_per_core is not None
            else None
        )

        memory_total = memory_free = memory_used = None
        if params_set & {"memory_total", "memory_free", "memory_used"}:
            memory_total = int(float(rrd_metrics.get("memory_total", 0) or 0)) 
            memory_free = int(float(rrd_metrics.get("memory_free", 0) or 0))
            memory_used = int(float(rrd_metrics.get("memory_used", 0) or 0))

        disk_total = disk_used = disk_free = None
        if params_set & disk_required:
            disk_total = int(disk_metrics.get("physical_size", 0) or 0)
            disk_used = int(disk_metrics.get("physical_utilisation", 0) or 0)
            disk_free = disk_total - disk_used

        software_version = host.get("software_version", {}) if host else {}
        supported_bootloaders = host.get("supported_bootloaders", []) if host else []

        values = {
            "uptime": uptime_seconds,
            "cpu_usage": float(rrd_metrics.get('cpu_usage', 0)),
            "load_avg": rrd_metrics.get("load_avg"),
            "io_wait": rrd_metrics.get("io_wait"),
            "cpu_model": cpu_info.get("modelname") if cpu_info else None,
            "cpu_num": cpu_count,
            "cpu_cores": cpu_cores,
            "cpu_sockets": socket_count,
            "memory_total": memory_total,
            "memory_free": memory_free,
            "memory_used": memory_used,
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_free": disk_free,
            "sysname": "Linux" if host else None,
            "release": software_version.get("linux") if software_version else None,
            "version": software_version.get("xen") if software_version else None,
            "boot_mode": "EFI" if "eliloader" in supported_bootloaders else ("BIOS" if host else None),
        }

        return {param: values.get(param) for param in params}
    

    def get_node_time_metrics(self, node_id: str, interval: str, cf: str = "AVERAGE", ds: list = None) -> list[dict]:
        """
        Vrátí časovou řadu metrik uzlu z Xen RRD endpointu.

        Args:
            node_id: UUID uzlu.
            interval: Časový interval (např. "current", "hour", "day").
            cf: Konsolidační funkce (např. "AVERAGE", "MAX").
            ds: Seznam požadovaných metrik.

        Returns:
            Seznam bodů časové řady obsahující pouze požadované metriky.
        """
        ds = ds or []
        params_set = set(ds)

        rrd_required = {
            "cpu_usage",
            "load_avg",
            "memory_used",
            "memory_total",
            "memory_free",
            "net_in",
            "net_out",
            "io_wait",
        }

        filtered_ds = list(params_set & rrd_required)

        if not filtered_ds:
            return []

        params = {
            "start": str(int(time.time()) - self.conn.TIMEFRAME_TO_SECONDS[interval]),
            "cf": cf,
            "host": "true",
        }

        r = requests.get(
            f"https://{self.conn.host}/rrd_updates",
            cookies={"session_id": self.conn.session},
            verify=False,
            headers={**self.conn.headers, "Accept": "application/json"},
            params=params,
        )

        r.raise_for_status()
        data = r.json()

        legends = data.get("meta", {}).get("legend", [])
        rows = data.get("data", [])

        metric_map = {
            "cpu_usage": {
                "patterns": ["cpu_avg"],
                "type": "single",
            },
            "load_avg": {
                "patterns": ["loadavg"],
                "type": "single",
            },
            "net_in": {
                "patterns": ["pif_aggr_rx"],
                "type": "single",
            },
            "net_out": {
                "patterns": ["pif_aggr_tx"],
                "type": "single",
            },
            "io_wait": {
                "patterns": ["iowait"],
                "type": "single",
            },
            "memory_used": {
                "patterns": ["memory_total_kib", "memory_free_kib"],
                "type": "memory",
            },
            "memory_total": {
                "patterns": ["memory_total_kib"],
                "type": "single",
            },
            "memory_free": {
                "patterns": ["memory_free_kib"],
                "type": "single",
            },
        }

        for metric in filtered_ds:
            config = metric_map.get(metric)
            if not config:
                continue

            metric_type = config["type"]
            patterns = config["patterns"]

            if metric_type == "memory":
                total_idx = None
                free_idx = None

                for i, legend in enumerate(legends):
                    legend_last = legend.split(":")[-1]

                    if legend_last == patterns[0]:
                        total_idx = i
                    elif legend_last == patterns[1]:
                        free_idx = i

                config["indexes"] = {
                    "total": total_idx,
                    "free": free_idx,
                }

            else:
                found_idx = None

                for i, legend in enumerate(legends):
                    legend_last = legend.split(":")[-1]

                    if legend_last == patterns[0] or patterns[0] in legend_last:
                        found_idx = i
                        break

                config["indexes"] = found_idx

        result = []

        for record in rows:
            ts = int(record["t"])
            values = record["values"]

            row = {
                "time": ts
            }

            for metric in filtered_ds:
                metric_conf = metric_map.get(metric)
                if not metric_conf:
                    continue

                metric_type = metric_conf.get("type")
                metric_index = metric_conf.get("indexes")

                if metric_type == "memory":
                    if not isinstance(metric_index, dict):
                        row[metric] = None
                        continue

                    total_idx = metric_index.get("total")
                    free_idx = metric_index.get("free")

                    mem_total = values[total_idx] if total_idx is not None and total_idx < len(values) else None
                    mem_free = values[free_idx] if free_idx is not None and free_idx < len(values) else None

                    if mem_total is None or mem_free is None:
                        row[metric] = None
                        continue

                    mem_total = float(mem_total)
                    mem_free = float(mem_free)

                    used = (mem_total - mem_free) * 1024  
                    row[metric] = used if used >= 0 else 0

                else:
                    idx = metric_index
                    if idx is None or idx >= len(values):
                        row[metric] = None
                        continue

                    value = values[idx]
                    if value is None:
                        row[metric] = None
                        continue

                    value = float(value)

                    if metric in ("memory_total", "memory_free"):
                        row[metric] = value * 1024  # KiB -> Bytes
                    else:
                        row[metric] = value

            result.append(row)

        if interval == "current":
            print(result[-1])
            return [result[-1]] if result else []

        return result


    def get_node_storage(self, node_id: str) -> dict:
        """
        Vrátí seznam storage dostupných na uzlu.

        Zahrnuje:

        - Xen SR storage připojené přes PBD k hostu
        - lokální backup adresář, pokud existuje

        Args:
            node_id: UUID uzlu.

        Returns:
            Seznam storage 
        """

        host_ref = self.conn.request(
            "POST",
            "host.get_by_uuid",
            [self.conn.session, node_id]
        )

        sr_records = self.conn.request(
            "POST",
            "SR.get_all_records",
            [self.conn.session]
        )

        pbd_records = self.conn.request(
            "POST",
            "PBD.get_all_records",
            [self.conn.session]
        )

        storages = []

        for sr_ref, sr in sr_records.items():
            matched_pbd = None

            for pbd_ref in sr.get("PBDs", []):
                pbd = pbd_records.get(pbd_ref)
                if not pbd:
                    continue

                if pbd.get("host") == host_ref:
                    matched_pbd = pbd
                    break

            if not matched_pbd:
                continue

            content_type = sr.get("content_type")
            sr_type = sr.get("type")

            if sr.get("content_type") not in ("user", "iso") or sr.get("type") == "udev" or sr.get("physical_size", 0) <= 0:
                continue

            total = int(sr.get("physical_size", 0) or 0)
            used = int(sr.get("physical_utilisation", 0) or 0)
            avail = max(total - used, 0)

            if content_type == "user":
                content = ["images"]
                upload_allowed = ["images"]
            elif content_type == "iso":
                content = ["iso"]
                upload_allowed = ["iso"]
            else:
                content = []
                upload_allowed = []

            storages.append({
                "storage_id": sr.get("uuid"),
                "storage": sr.get("name_label"),
                "type": sr.get("type"),

                "total": total,
                "used": used,
                "used_fraction": (used / total) if total else 0,
                "avail": avail, 

                "active": int(bool(matched_pbd.get("currently_attached"))),
                "enabled": int(bool(matched_pbd.get("currently_attached"))),
                "shared": int(bool(sr.get("shared"))),

                "content": content,
                "upload_allowed": upload_allowed,
            })

        backup_dir = os.path.join(BACKUP_ROOT, "xen")
        if os.path.isdir(backup_dir):
            total = 0
            for entry in os.scandir(backup_dir):
                if entry.is_file():
                    total += entry.stat().st_size

            storages.append({
                "storage_id": "xen-local-backups",
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


    def get_node_storage_content(self, node_id: str, storage_id: str) -> dict:
        """
        Vrátí obsah zvoleného storage.

        Podporuje:
        
        - Xen SR storage
        - lokální backup pseudo-storage

        Args:
            node_id: UUID uzlu.
            storage_id: UUID storage nebo interní identifikátor backup storage.

        Returns:
            Seznam položek dostupných ve storage.
        """

        if storage_id == "xen-local-backups":
            backup_dir = os.path.join(BACKUP_ROOT, "xen")

            if not os.path.isdir(backup_dir):
                return []

            items = []

            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    if not file.lower().endswith(".xva"):
                        continue

                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, backup_dir)
                    stat = os.stat(full_path)

                    items.append({
                        "volid": rel_path,
                        "name": rel_path,   # důležité: ne jen file
                        "path": rel_path,   # doporučuju explicitně přidat
                        "content": "backup",
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime),
                        "format": "xva",
                    })

            items.sort(key=lambda x: x["mtime"], reverse=True)
            return items

        host_ref = self.conn.request(
            "POST",
            "host.get_by_uuid",
            [self.conn.session, node_id]
        )

        sr_ref = self.conn.request(
            "POST",
            "SR.get_by_uuid",
            [self.conn.session, storage_id]
        )

        pbd_records = self.conn.request(
            "POST",
            "PBD.get_all_records",
            [self.conn.session]
        )

        sr_records = self.conn.request(
            "POST",
            "SR.get_all_records",
            [self.conn.session]
        )

        vdi_records = self.conn.request(
            "POST",
            "VDI.get_all_records",
            [self.conn.session]
        )

        attached_srs = set()

        for pbd_ref, pbd in pbd_records.items():
            if pbd.get("host") == host_ref:
                attached_srs.add(pbd.get("SR"))

        if sr_ref not in attached_srs:
            raise Exception("Storage not attached to this node")

        sr_record = sr_records.get(sr_ref)
        if not sr_record:
            raise Exception("Storage record not found")

        sr_name = sr_record.get("name_label", storage_id)
        sr_content_type = sr_record.get("content_type")

        content = []

        for vdi_ref, vdi in vdi_records.items():
            if vdi.get("SR") != sr_ref:
                continue

            vdi_type = vdi.get("type")

            vdi_name = vdi.get("name_label")
            vdi_uuid = vdi.get("uuid")
            virtual_size = int(vdi.get("virtual_size", 0) or 0)
            used = int(vdi.get("physical_utilisation", 0) or 0)

            if sr_content_type == "user":
                item_content = "images"
                fmt = vdi_type or "vdi"
            elif sr_content_type == "iso":
                item_content = "iso"
                fmt = "iso"
            else:
                item_content = sr_content_type or "unknown"
                fmt = vdi_type or "raw"

            content.append({
                "volid": vdi_uuid,
                "name": vdi_name,
                "type": vdi_type,
                "size": used,
                "content": item_content,
                "format": fmt,
            })

        return content
    
    def upload_node_storage_file(self, node_id: str, storage_id: str, content_type: str, file: UploadFile) -> dict:
        """
        Nahraje soubor do Xen storage.

        Podporuje:

        - upload ISO do ISO storage
        - upload disk image do user storage

        Args:
            node_id: UUID uzlu.
            storage_id: UUID storage.
            content_type: Typ obsahu ("iso" nebo "images").
            file: Uploadovaný soubor.

        Returns:
            Metadata o nahraném souboru a HTTP status uploadu.

        Raises:
            ValueError: Pokud storage není dostupný, soubor je prázdný nebo content/type neodpovídá storage.
        """

        vdi_ref = None
        task_ref = None

        host_ref = self.conn.request(
            "POST",
            "host.get_by_uuid",
            [self.conn.session, node_id]
        )

        sr_ref = self.conn.request(
            "POST",
            "SR.get_by_uuid",
            [self.conn.session, storage_id]
        )

        pbd_records = self.conn.request(
            "POST",
            "PBD.get_all_records",
            [self.conn.session]
        )

        sr_record = self.conn.request(
            "POST",
            "SR.get_record",
            [self.conn.session, sr_ref]
        )

        attached_srs = set()

        for pbd_ref, pbd in pbd_records.items():
            if pbd.get("host") == host_ref:
                attached_srs.add(pbd.get("SR"))

        if sr_ref not in attached_srs:
            raise ValueError(f"Storage {storage_id} není dostupný na nodu {node_id}")

        sr_content_type = sr_record.get("content_type")
        file_name = file.filename or "upload"
        file_ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size <= 0:
            raise ValueError("Soubor je prázdný")

        if sr_content_type == "iso":
            if content_type != "iso":
                raise ValueError("Do ISO storage lze nahrávat pouze ISO obsah")

            if file_ext != "iso":
                raise ValueError("Do ISO storage lze nahrát pouze .iso soubor")

            vdi_type = "user"
            import_format = "raw"

        elif sr_content_type == "user":
            if content_type != "images":
                raise ValueError("Do user storage lze nahrávat pouze disk images")

            if file_ext == "vhd":
                import_format = "vhd"
            else:
                import_format = "raw"

            vdi_type = "user"

        else:
            raise ValueError(f"Nepodporovaný content_type storage: {sr_content_type}")
        
        try:

            vdi_ref = self.conn.request(
                "POST",
                "VDI.create",
                [self.conn.session, {
                    "name_label": file_name,
                    "name_description": "",
                    "SR": sr_ref,
                    "virtual_size": str(size),
                    "type": vdi_type,
                    "sharable": False,
                    "read_only": False,
                    "other_config": {},
                    "sm_config": {},
                }]
            )

            task_ref = self.conn.request(
                "POST",
                "task.create",
                [self.conn.session, f"upload-{file_name}", f"Uploading {file_name}"]
            )

            params = urlencode({
                "session_id": self.conn.session,
                "task_id": task_ref,
                "vdi": vdi_ref,
                "format": import_format,
            })

            url = f"https://{self.conn.host}/import_raw_vdi?{params}"

            res = requests.put(
                url,
                data=file.file,
                headers={
                    "Connection": "close",
                    "Content-Type": "application/octet-stream",
                },
                verify=False,
                timeout=3600,
            )

            if not res.ok:
                raise RuntimeError(
                    f"XAPI upload failed: HTTP {res.status_code}: {res.text[:2000]}"
                )
            
            if sr_content_type == "iso":
                self.conn.request("POST", "SR.scan", [self.conn.session, sr_ref])

            return {
                "vdi_ref": vdi_ref,
                "name": file_name,
                "storage": storage_id,
                "content": content_type,
                "status_code": res.status_code,
            }
        
        except Exception:
            if vdi_ref:
                try:
                    self.conn.request("POST", "VDI.destroy", [self.conn.session, vdi_ref])
                except Exception:
                    pass
            raise

    def delete_node_storage_content(self, node_id: str, storage_id: str, vdi_id: str) -> dict:
        """
        Smaže položku ze storage.

        Args:
            node_id: UUID uzlu.
            storage_id: UUID storage.
            vdi_id: UUID VDI.

        Returns:
            Prázdný slovník po úspěšném smazání.

        Raises:
            ValueError: Pokud storage není dostupné nebo VDI neexistuje / nepatří do storage.
            RuntimeError: Pokud je VDI připojené k VM.
        """
        host_ref = self.conn.request(
            "POST",
            "host.get_by_uuid",
            [self.conn.session, node_id]
        )

        sr_ref = self.conn.request(
            "POST",
            "SR.get_by_uuid",
            [self.conn.session, storage_id]
        )

        pbd_records = self.conn.request(
            "POST",
            "PBD.get_all_records",
            [self.conn.session]
        )

        attached_srs = set()

        for pbd_ref, pbd in pbd_records.items():
            if pbd.get("host") == host_ref:
                attached_srs.add(pbd.get("SR"))

        if sr_ref not in attached_srs:
            raise ValueError(f"Storage {storage_id} není dostupný na nodu {node_id}")

        vdi_ref = self.conn.request(
            "POST",
            "VDI.get_by_uuid",
            [self.conn.session, vdi_id]
        )

        if not vdi_ref:
            raise ValueError(f"VDI {vdi_id} nenalezeno")
      

        vdi_record = self.conn.request(
            "POST",
            "VDI.get_record",
            [self.conn.session, vdi_ref]
        )

        if vdi_record.get("SR") != sr_ref:
            raise ValueError(f"VDI {vdi_id} nepatří do storage {storage_id}")

        vbd_refs = self.conn.request(
            "POST",
            "VDI.get_VBDs",
            [self.conn.session, vdi_ref]
        )

        if vbd_refs:
            raise RuntimeError(f"VDI {vdi_id} je připojené k VM, nelze smazat")

        try:
            self.conn.request(
                "POST",
                "VDI.destroy",
                [self.conn.session, vdi_ref]
            )
        except Exception as e:
            if "VDI_NOT_MANAGED" in str(e):
                self.conn.request(
                    "POST",
                    "VDI.forget",
                    [self.conn.session, vdi_ref]
                )
            else:
                raise

        return {
            "deleted": True,
            "vdi_id": vdi_id,
            "storage": storage_id,
        }

    def get_task_status(self, node_id: str, task_id: str) -> dict:
        """
        Vrátí detailní stav Xen tasku.

        Args:
            node_id: UUID nebo identifikátor uzlu.
            task_id: Referenční ID tasku.

        Returns:
            Stav tasku převedený do interního formátu.
        """
        task_ref = task_id

        res = self.conn.request(
            "POST",
            "task.get_record",
            [self.conn.session, task_ref]
        )

        record = res.get("Value", {}) if isinstance(res, dict) else {}

        status = record.get("status")
        progress = record.get("progress")
        error_info = record.get("error_info", [])
        result = record.get("result")
        created = record.get("created")
        finished = record.get("finished")
        name_label = record.get("name_label")
        name_description = record.get("name_description")
        resident_on = record.get("resident_on")

        exitstatus = None
        if status == "success":
            exitstatus = "OK"
        elif status == "failure":
            exitstatus = "ERROR"

        return {
            "task_id": task_id,
            "node": node_id,
            "status": status,
            "exitstatus": exitstatus,
            "progress": progress,
            "result": result,
            "error_info": error_info,
            "starttime": created,
            "endtime": finished,
            "type": name_label,
            "id": task_ref,
            "user": None,
            "upid": None,
            "description": name_description,
            "resident_on": resident_on,
        }

    def get_node_networks(self, node_id: str) -> list[dict]:
        """
        Vrátí seznam sítí dostupných na uzlu.

        Síť je odvozena z PIF rozhraní a navázaných network objektů.

        Args:
            node_id: UUID uzlu.

        Returns:
            Seznam sítí na daném uzlu.
        """
        _, host = self._get_node(node_id)

        pif_refs = host.get("PIFs", [])
        networks = []
        seen = set()

        for pif_ref in pif_refs:

            pif = self.conn.request(
                "POST",
                "PIF.get_record",
                [self.conn.session, pif_ref]
            )

            network_ref = pif.get("network")

            if not network_ref or network_ref in seen:
                continue

            net_res = self.conn.request(
                "POST",
                "network.get_record",
                [self.conn.session, network_ref]
            )

            net = net_res

            seen.add(network_ref)

            networks.append({
                "id": net.get("uuid"),
                "name": net.get("name_label") or pif.get("device"),
                "active": bool(pif.get("currently_attached")),
                "type": "bridge" if net.get("bridge") else "network",
                "default": bool(pif.get("management")),
            })

        return networks

    def get_node_logs(self, node_id, limit) -> dict:
        """
        Vrátí systémové logy uzlu ze staženého lokálního log souboru.

        Args:
            node_id: Identifikátor uzlu.
            limit: Maximální počet vrácených řádků.

        Returns:
            Slovník s log řádky v poli `lines`.

        Raises:
            FileNotFoundError: Pokud neexistuje log adresář nebo log soubor.
        """

        ip = self.conn.host

        if ':' in ip:
            ip = ip.split(":")[0]

        log_file = os.path.join(LOG_ROOT, ip, "syslog.log")

        if not os.path.isdir(LOG_ROOT):
            raise FileNotFoundError(f"Log directory not found: {LOG_ROOT}")

        if not os.path.isfile(log_file):
            raise FileNotFoundError(f"Log file not found: {log_file}")
                
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            log_lines = list(deque(f, limit))

        return {
            "lines": [line.rstrip("\n") for line in log_lines]
        }
    

    def _get_node(self, node_id: str):
        """
        Vrátí Xen host reference a kompletní host record.

        Args:
            node_id: UUID uzlu.

        Returns:
            Dvojice (host_ref, host_record).
        """
        host_ref = self.conn.request(
            "POST",
            "host.get_by_uuid",
            [self.conn.session, node_id]
        )

        host = self.conn.request(
            "POST",
            "host.get_record",
            [self.conn.session, host_ref]
        )

        return host_ref, host
    

    def _get_node_storage_record(self, host_ref: str):
        """
        Vrátí první user storage record připojený k danému hostu.

        Args:
            host_ref: Xen reference hostu.

        Returns:
            SR record nebo None.
        """
        sr_records = self.conn.request(
            "POST",
            "SR.get_all_records",
            [self.conn.session]
        )

        for sr_ref, sr in sr_records.items():
            if sr.get("content_type") != "user":
                continue

            pbds = sr.get("PBDs", [])
            for pbd_ref in pbds:
                pbd = self.conn.request(
                    "POST",
                    "PBD.get_record",
                    [self.conn.session, pbd_ref]
                )

                if pbd.get("host") == host_ref:
                    return sr

        return None