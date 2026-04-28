import libvirt
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import shlex
import re
import os
from config import LOG_ROOT, BACKUP_ROOT
from collections import deque
from platforms.kvm.connection import KvmConnection

class KvmNodeApi:
    """
    API wrapper pro práci s KVM uzly.

    Args:
        connection: Objekt zajišťující komunikaci s KVM/libvirt hostem.

    Attributes:
        conn (KvmConnection): Aktivní connection objekt pro komunikaci s KVM/libvirt hostem.
    """

    def __init__(self, connection: KvmConnection):
        self.conn = connection

    def get_node_status(self, node_name: str, params: list) -> dict:
        """
        Vrátí vybrané stavové informace o uzlu.

        Kombinuje data z:

        - aktuálních collectd metrik
        - libvirt host info
        - memory stats
        - systémových SSH dotazů

        Args:
            node_name: název uzlu.
            params: Seznam požadovaných metrik a informací.

        Returns:
            Slovník obsahující pouze vyžádané metriky.
        """
         
        res = {}
        params_set = set(params)

        current_metrics = {"cpu_usage", "load_avg", "swap_free", "swap_used", "swap_total"}
        host_info_keys = {"cpu_num", "cpu_model", "cpu_cores", "cpu_sockets"}
        memory_keys = {"memory_total", "memory_used", "memory_free"}
        disk_keys = {"disk_total", "disk_used", "disk_free"}

        host_info = None
        if params_set & host_info_keys:
            host_info = self.conn.session.getInfo()

        query_metrics = [m for m in current_metrics if m in params_set]
        if query_metrics:
            metrics = self.conn.get_current_metrics(query_metrics, node_name)

            for metric in query_metrics:
                res[metric] = metrics.get(metric)

        memstats = None
        if params_set & memory_keys:
            memstats = self.conn.session.getMemoryStats(
                libvirt.VIR_NODE_MEMORY_STATS_ALL_CELLS, 0
            )

            total_kb = int(memstats.get("total", 0))
            free_kb = int(memstats.get("free", 0))
            buffers_kb = int(memstats.get("buffers", 0))
            cached_kb = int(memstats.get("cached", 0))

            available_kb = free_kb + buffers_kb + cached_kb
            used_kb = total_kb - available_kb

            if "memory_total" in params_set:
                res["memory_total"] = total_kb * 1024

            if "memory_free" in params_set:
                res["memory_free"] = available_kb * 1024

            if "memory_used" in params_set:
                res["memory_used"] = used_kb * 1024

        if "uptime" in params_set:
            raw = self.conn.run_ssh_command("cat /proc/uptime")
            res["uptime"] = int(float(raw.split()[0]))


        if params_set & disk_keys:
            cmd = "df -B1 --output=size,used,avail / | tail -1"
            raw = self.conn.run_ssh_command(cmd)
            size, used, avail = map(int, raw.split())

            if "disk_total" in params_set:
                res["disk_total"] = size

            if "disk_free" in params_set:
                res["disk_free"] = avail

            if "disk_used" in params_set:
                res["disk_used"] = used

        if {"sysname", "release", "version", "boot_mode"} & params_set:

            boot_mode_cmd = 'if [ -d /sys/firmware/efi ]; then echo UEFI; else echo BIOS; fi'

            cmd = (
                'sh -c \''
                'echo "sysname=$(uname -s)"; '
                'echo "release=$(uname -r)"; '
                'echo "version=$(uname -v)"; '
                f'echo "boot_mode=$({boot_mode_cmd})"'
                '\''
            )

            raw = self.conn.run_ssh_command(cmd)
            parsed = {}

            for line in raw.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    parsed[key] = value

            if "sysname" in params_set:
                res["sysname"] = parsed.get("sysname")

            if "release" in params_set:
                res["release"] = parsed.get("release")

            if "version" in params_set:
                res["version"] = parsed.get("version")

            if "boot_mode" in params_set:
                res["boot_mode"] = parsed.get("boot_mode")

        return res
    

    def get_node_time_metrics(self, node_name: str, interval: str = "hour", cf: str = "AVERAGE", ds: list = None) -> list[dict]:
        """
        Vrátí časovou řadu metrik uzlu z collectd RRD databáze.

        Args:
            node_name: název uzlu.
            interval: Časový interval (např. "hour", "day", "week").
            cf: Konsolidační funkce (např. "AVERAGE", "MAX").
            ds: Seznam požadovaných metrik.

        Returns:
            Seznam bodů časové řady.
        """
         
        base_path = f"/var/lib/collectd/rrd/{node_name}"
        start_expr = self._interval_to_start(interval)

        cpu_files = self._find_host_cpu_idle_files(base_path)
        iface_files = self._find_host_interface_files(base_path)

        mem_used_file = f"{base_path}/memory/memory-used.rrd"
        mem_free_file = f"{base_path}/memory/memory-free.rrd"
        load_file = f"{base_path}/load/load.rrd"
        disk_files = self._find_host_disk_files(base_path)

        cmd_parts = [
            "rrdtool xport",
            f"--start {shlex.quote(start_expr)}",
            "--end now",
        ]

        # CPU idle per core
        for i, path in enumerate(cpu_files):
            var_name = f"cpuidle{i}"
            export_name = f"cpu_idle_{i}"
            cmd_parts.append(f"DEF:{var_name}={shlex.quote(path)}:value:{cf}")
            cmd_parts.append(f"XPORT:{var_name}:{shlex.quote(export_name)}")

        # Memory
        cmd_parts.append(f"DEF:mem_used={shlex.quote(mem_used_file)}:value:{cf}")
        cmd_parts.append("XPORT:mem_used:memory_used")

        cmd_parts.append(f"DEF:mem_free={shlex.quote(mem_free_file)}:value:{cf}")
        cmd_parts.append("XPORT:mem_free:memory_free")

        # Load
        cmd_parts.append(f"DEF:load_short={shlex.quote(load_file)}:shortterm:{cf}")
        cmd_parts.append("XPORT:load_short:load_avg")

        # Network rx/tx
        for i, path in enumerate(iface_files):
            rx_name = f"rx{i}"
            tx_name = f"tx{i}"
            rx_export = f"net_rx_{i}"
            tx_export = f"net_tx_{i}"

            cmd_parts.append(f"DEF:{rx_name}={shlex.quote(path)}:rx:{cf}")
            cmd_parts.append(f"DEF:{tx_name}={shlex.quote(path)}:tx:{cf}")
            cmd_parts.append(f"XPORT:{rx_name}:{shlex.quote(rx_export)}")
            cmd_parts.append(f"XPORT:{tx_name}:{shlex.quote(tx_export)}")

        # Disk read/write
        for i, path in enumerate(disk_files):
            read_name = f"diskread{i}"
            write_name = f"diskwrite{i}"
            read_export = f"disk_read_{i}"
            write_export = f"disk_write_{i}"

            cmd_parts.append(f"DEF:{read_name}={shlex.quote(path)}:read:{cf}")
            cmd_parts.append(f"DEF:{write_name}={shlex.quote(path)}:write:{cf}")
            cmd_parts.append(f"XPORT:{read_name}:{shlex.quote(read_export)}")
            cmd_parts.append(f"XPORT:{write_name}:{shlex.quote(write_export)}")

        cmd = " ".join(cmd_parts)
        xml_output = self.conn.run_ssh_command(cmd)
        parsed = self._parse_xport_xml(xml_output)

        records = []

        for ts, row in parsed.items():

            cpu_idle_values = [
                row[name]
                for name in row
                if name.startswith("cpu_idle_") and row[name] is not None
            ]

            cpu_usage = None
            if cpu_idle_values:
                avg_idle = sum(cpu_idle_values) / len(cpu_idle_values)
                cpu_usage = max(0.0, min(1.0, (100.0 - avg_idle) / 100.0))

            memory_used = row.get("memory_used")

            net_in = sum(
                value for name, value in row.items()
                if name.startswith("net_rx_") and value is not None
            )

            net_out = sum(
                value for name, value in row.items()
                if name.startswith("net_tx_") and value is not None
            )

            record = {
                "time": int(ts),
                "load_avg": row.get("load_avg"),
                "cpu_usage": cpu_usage,
                "net_out": net_out,
                "memory_used": memory_used,
                "net_in": net_in,
            }

            records.append(record)

        return records
    

    def get_node_storage(self, node_name: str | None = None) -> list[dict]:
        """
        Vrátí seznam storage dostupných na uzlu.

        Args:
            node_name: název uzlu

        Returns:
            Seznam storage s doplněnými informacemi o podporovaném uploadu.
        """
        storages = []

        for pool in self.conn.session.listAllStoragePools(0):
            pool.refresh(0)

            xml = ET.fromstring(pool.XMLDesc(0))

            storage_name = pool.name()
            storage_type = xml.get("type")

            path_node = xml.find(".//target/path")
            path = path_node.text if path_node is not None else ""

            path_lower = (path or "").lower()
            name_lower = storage_name.lower()

            if name_lower in ("root", "root1"):
                continue

            if any(x in path_lower for x in ["iso", "cdrom", "boot"]) or any(x in name_lower for x in ["iso", "cdrom"]):
                content = ["iso"]
            else:
                content = ["images"]

            accessible = pool.isActive() == 1
            active = int(accessible)
            enabled = int(accessible)

            info = pool.info()

            total = int(info[1])
            used = int(info[2])
            avail = int(info[3])
            used_fraction = (used / total) if total else 0

            content_allowed = []
            if "iso" in content:
                content_allowed.append("iso")

            storages.append({
                "active": active,
                "shared": None,
                "type": storage_type,
                "used_fraction": used_fraction,
                "storage": storage_name,
                "storage_id": storage_name,
                "total": total,
                "avail": avail,
                "used": used,
                "enabled": enabled,
                "content": content,
                "upload_allowed": content_allowed
            })

        backup_dir = os.path.join(BACKUP_ROOT, "kvm")
        if os.path.isdir(backup_dir):
            total = 0
            for entry in os.scandir(backup_dir):
                if entry.is_file():
                    total += entry.stat().st_size

            storages.append({
                "storage_id": "kvm-local-backups",
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
    
    def get_task_status(self, node_name: str, task_id: str) -> dict:
        """
        Vrátí detailní stav úlohy na uzlu.

        Args:
            node_name: Název uzlu.
            task_id: Identifikátor úlohy.

        Returns:
            Stav a metadata úlohy.
        """
        pass

    def get_node_networks(self, node_name: str) -> list[dict]:
        """
        Vrátí síťová rozhraní typu bridge dostupná na uzlu.

        Args:
            node_name: Identifikátor uzlu.

        Returns:
            Seznam network rozhraní.
        """
        networks = []

        for net in self.conn.session.listAllNetworks():
            xml = ET.fromstring(net.XMLDesc(0))

            name = net.name()
            bridge_node = xml.find("./bridge")
            bridge_name = bridge_node.get("name") if bridge_node is not None else name

            active = net.isActive() == 1
            autostart = net.autostart() == 1

            networks.append({
                "id": bridge_name,
                "name": bridge_name,
                "active": active,
                "type": "bridge",
                "default": bridge_name in {"virbr0", "br0"},
                "autostart": autostart,
                "network_name": name,
            })

        return networks
    

    def get_node_storage_content(self, node_name: str, storage_name: str) -> dict:
        """
        Vrátí obsah zvoleného storage.

        Podporuje:

        - libvirt storage pool
        - lokální backup pseudo-storage

        Args:
            node_name: Název uzlu.
            storage_name:  storage.

        Returns:
            Seznam položek dostupných ve storage.
        """

        def detect_content_type(volume):
            name = volume.name().lower()

            if name.endswith(".iso"):
                return "iso"

            if name.endswith((".qcow2", ".raw", ".img", ".vmdk")):
                return "images"

            if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.xz", ".tar.zst")):
                return "vztmpl"

            if name.endswith((".vma", ".vma.zst", ".vma.gz", ".bak", ".backup")):
                return "backup"

            return "images"
        
        if storage_name == "kvm-local-backups":
            backup_root = os.path.join(BACKUP_ROOT, "kvm")

            if not os.path.isdir(backup_root):
                return []

            items = []

            for entry in os.scandir(backup_root):
                if not entry.is_dir():
                    continue

                vm_xml_path = os.path.join(entry.path, "vm.xml")
                if not os.path.isfile(vm_xml_path):
                    continue

                stat = entry.stat()

                total_size = 0
                for root, _, files in os.walk(entry.path):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            total_size += os.path.getsize(file_path)
                        except OSError:
                            pass

                items.append({
                    "volid": entry.path,
                    "name": entry.name,
                    "content": "backup",
                    "size": total_size,
                    "mtime": int(stat.st_mtime),
                    "format": "dir",
                })

            items.sort(key=lambda x: x["mtime"], reverse=True)
            return items

        storage = self.conn.session.storagePoolLookupByName(storage_name)

        items = []

        for volume in storage.listAllVolumes():

            volume_info = storage.storageVolLookupByName(volume.name()).info()

            items.append({
                "volid": volume.name(),
                "name": volume.name(),
                "size": volume_info[1],
                "content": detect_content_type(volume),
            })

        return items


    def upload_node_storage_file(self, node_name: str, storage_name: str, content_type: str, file) -> dict:
        """
        Nahraje soubor do storage.

        Args:
            node_name: Název uzlu.
            storage_name: Identifikátor storage.
            content_type: Typ obsahu.
            file: Uploadovaný soubor.

        Returns:
            Metadata o nahraném souboru.
        """

        pool = self.conn.session.storagePoolLookupByName(storage_name)

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        filename = file.filename

        vol_xml = f"""
            <volume>
                <name>{escape(filename)}</name>
                <allocation unit="bytes">0</allocation>
                <capacity unit="bytes">{size}</capacity>
            </volume>
        """

        vol = pool.createXML(vol_xml, 0)

        stream = self.conn.session.newStream(0)
        vol.upload(stream, 0, size, 0)

        def reader(_handler, nbytes, _opaque):
            return file.file.read(nbytes)

        stream.sendAll(reader, None)
        stream.finish()

        try:
            pool.refresh(0)
        except Exception:
            pass

        return {
            "success": True,
            "storage": storage_name,
            "volume": vol.name(),
            "path": vol.path(),
            "key": vol.key(),
            "size": size,
            "content": content_type or "generic",
        }

    def delete_node_storage_content(self, node_name: str, storage_name: str, vol_id: str) -> dict:
        """
        Smaže položku ze storage.

        Args:
            node_name: Název uzlu.
            storage_name: Identifikátor storage poolu.
            vol_id: Identifikátor volume.

        Returns:
            Výsledek operace.

        Raises:
            ValueError: Pokud storage pool nebo volume neexistuje.
            RuntimeError: Pokud smazání volume selže.
        """

        try:
            pool = self.conn.session.storagePoolLookupByName(storage_name)
        except libvirt.libvirtError:
            raise ValueError(f"Storage pool {storage_name} does not exist")

        try:
            vol = pool.storageVolLookupByName(vol_id)
        except libvirt.libvirtError:
            raise ValueError(f"Volume {vol_id} does not exist in pool {storage_name}")

        try:
            vol.delete(0)
        except libvirt.libvirtError as e:
            raise RuntimeError(f"Failed to delete volume {vol_id}: {e}")

        return {"data": True}

    def get_node_logs(self, node_name: str, limit: int) -> dict:
        """
        Vrátí systémové logy uzlu.

        Args:
            node_name: Název uzlu.
            limit: Maximální počet vrácených log řádků.

        Returns:
            Seznam logů limitovaný na hodnotu v argumentu (`limit`).
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
    
    def _parse_xport_xml(self, xml_text: str) -> dict:
        """
        Převede XML výstup z `rrdtool xport` do slovníkové reprezentace.

        Args:
            xml_text: XML odpověď z `rrdtool xport`.

        Returns:
            Slovník ve formátu `{timestamp: {metric_name: value}}`.
        """
        root = ET.fromstring(xml_text)

        legends = []
        legend_node = root.find(".//legend")
        if legend_node is not None:
            legends = [entry.text for entry in legend_node.findall("entry")]

        rows_out = {}
        data_node = root.find(".//data")
        if data_node is None:
            return rows_out

        meta_node = root.find(".//meta")
        start = int(meta_node.findtext("start", "0")) if meta_node is not None else 0
        step = int(meta_node.findtext("step", "0")) if meta_node is not None else 0

        for row_index, row in enumerate(data_node.findall("row")):
            t_node = row.find("t")

            if t_node is not None and t_node.text is not None:
                ts = int(float(t_node.text))
            else:
                ts = start + (row_index * step)

            values = {}

            v_nodes = row.findall("v")
            for i, v in enumerate(v_nodes):
                name = legends[i] if i < len(legends) else f"v{i}"
                raw = v.text.strip() if v.text else "NaN"

                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    val = None

                if raw.lower() == "nan":
                    val = None

                values[name] = val

            rows_out[ts] = values

        return rows_out
    
    def _interval_to_start(self, interval: str) -> str:
        """
        Převede interní označení intervalu na výraz pro `rrdtool`.

        Args:
            interval: Interní označení intervalu.

        Returns:
            Výraz použitelný jako `--start` parametr pro `rrdtool`.
        """
        mapping = {
            "hour": "end-1h",
            "day": "end-1d",
            "week": "end-1w",
            "month": "end-1m",
            "year": "end-1y",
        }
        return mapping.get(interval, "end-1h")
    
    def _find_host_cpu_idle_files(self, base_path: str) -> list[str]:
        """
        Najde RRD soubory síťových rozhraní hostu.

        Filtrovaná jsou pomocná nebo interní rozhraní jako `lo`, `virbr*`,
        `docker*` a `vnet*`.

        Args:
            base_path: Kořenová cesta k RRD datům hostu.

        Returns:
            Seznam cest k `if_octets.rrd` souborům.
        """
        cmd = (
            f"find {shlex.quote(base_path)} -maxdepth 2 -type f "
            f"-path '*/cpu-*/cpu-idle.rrd' | sort"
        )
        raw = self.conn.run_ssh_command(cmd).strip()
        return [line.strip() for line in raw.splitlines() if line.strip()]


    def _find_host_interface_files(self, base_path: str) -> list[str]:
        """
        Najde RRD soubory síťových rozhraní hostu.

        Filtrovaná jsou pomocná nebo interní rozhraní jako `lo`, `virbr*`,
        `docker*` a `vnet*`.

        Args:
            base_path: Kořenová cesta k RRD datům hostu.

        Returns:
            Seznam cest k `if_octets.rrd` souborům.
        """
        cmd = (
            f"find {shlex.quote(base_path)} -maxdepth 2 -type f "
            f"-path '*/interface-*/if_octets.rrd' | sort"
        )
        raw = self.conn.run_ssh_command(cmd).strip()
        all_iface_files = [line.strip() for line in raw.splitlines() if line.strip()]

        iface_files = []
        for path in all_iface_files:
            m = re.search(r"/interface-([^/]+)/if_octets\.rrd$", path)
            iface_name = m.group(1) if m else ""

            if (
                iface_name == "lo"
                or iface_name.startswith("virbr")
                or iface_name.startswith("docker")
                or iface_name.startswith("vnet")
            ):
                continue

            iface_files.append(path)

        return iface_files


    def _find_host_disk_files(self, base_path: str) -> list[str]:
        """
        Najde RRD soubory diskových statistik hostu.

        Args:
            base_path: Kořenová cesta k RRD datům hostu.

        Returns:
            Seznam cest k `disk_octets.rrd` souborům.
        """
        cmd = (
            f"find {shlex.quote(base_path)} -maxdepth 2 -type f "
            f"-path '*/disk-*/disk_octets.rrd' | sort"
        )
        raw = self.conn.run_ssh_command(cmd).strip()
        return [line.strip() for line in raw.splitlines() if line.strip()]
    