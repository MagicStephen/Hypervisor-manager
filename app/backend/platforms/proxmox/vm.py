from platforms.base.vm import BaseVmApi
from platforms.proxmox.connection import ProxmoxConnection
import re
from urllib.parse import quote
import time

class ProxmoxVmApi(BaseVmApi):

    """Implementace API vrstvy pro správu virtuálních strojů v Proxmoxu.

    Třída poskytuje operace pro:

    - vytváření a mazání VM
    - změnu stavu VM
    - čtení konfigurace a metrik
    - práci se snapshoty
    - práci se zálohami
    - otevření konzole
    """

    RRD_METRICS = {
        "cpu":  "cpu_usage",
        "maxmem": "memory_total",
        "mem": "memory_used",
        "neting": "net_in",
        "netout": "net_out",
        "diskwrite": "disk_write",
        "diskread": "disk_read"
    }

    PROXMOX_GUEST_MAP = {
        "linux24": "l24",
        "linux": "l26",
        "windows-modern": "win10",
        "windows-latest": "win11",
        "other32": "other",
        "other64": "other",
    }

    def get_vm_capabilities(self):
        return {
            "source_types": ["template", "iso", "backup", "empty"],

            "guest": {
                "types": [
                    "linux24",
                    "linux",
                    "windows-modern",
                    "windows-latest",
                    "other32",
                    "other64"
                ],
                "default": "other64",
            },

            "disk": {
                "buses": ["scsi"],
                "controllers": [
                    "virtio-scsi-pci",
                    "virtio-scsi-single",
                    "lsi",
                    "lsi53c810",
                    "megasas",
                    "pvscsi"
                ],
                "default_bus": "scsi",
                "default_controller": "default",
            },

            "network": {
                "models": [
                    "virtio",
                    "e1000",
                    "rtl8139",
                    "vmxnet3"
                ],
                "default_model": "virtio",
            },

            "boot": {
                "firmware": [
                    "bios",
                    "seabios",
                    "uefi",
                    "ovmf"
                ],
                "machines": [
                    "pc",
                    "q35",
                ],
                "secure_boot": False,
            },

            "graphics": {
                "models": [
                    "default",
                ],
                "default": "default",
            },

            "options": {
                "start_after_create": True,
                "autostart": True,
            },
        }
    

    def __init__(self, connection: ProxmoxConnection):
        """Inicializuje API klienta pro práci s Proxmox VM.

        Args:
            connection: objekt zajišťující HTTP komunikaci s Proxmox API.
        """
         
        self.conn = connection

    def destroy_vm(self, node_name: str, vm_id: str) -> None:
        """Smaže virtuální stroj včetně nepoužívaných disků.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
        """

        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}"

        params = {
            "purge": 1,
            "destroy-unreferenced-disks": 1,
        }

        self.conn.request(
            method="DELETE",
            url=url,
            params=params,
        )

    def create_vm(self, node_name: str, opt_params: dict) -> dict:
        """Vytvoří nový virtuální stroj v Proxmoxu.

        Podporované zdroje vytvoření:

        - z zálohy (`backup`)
        - z template (`template`)
        - z ISO obrazu (`iso`)
        - z přímé konfigurace disků, sítí a boot parametrů

        Args:
            node_name: Název Proxmox uzlu.
            opt_params (dict): Konfigurace virtuálního stroje včetně zdroje, CPU, paměti, disků, sítí, boot voleb a dalších parametrů.

        Returns:
            Výsledek operace pro vytvoření.

        Raises:
            ValueError: Pokud chybí povinné parametry konfigurace.
        """

        def create_from_backup(backup_params, opt_params):
            data = {}

            storage_id = backup_params.get("storage_id")
            path = backup_params.get("path")

            if not storage_id or not path:
                raise ValueError("Backup requires storage_id and path")

            vmid = opt_params.get("vmid")
            if vmid is not None:
                data["vmid"] = vmid

            name = opt_params.get("name")
            if name:
                data["name"] = name

            memory = opt_params.get("memory_mb")
            if memory is not None:
                data["memory"] = memory

            cpu = opt_params.get("cpu", {})
            if cpu.get("cores") is not None:
                data["cores"] = cpu["cores"]
            if cpu.get("sockets") is not None:
                data["sockets"] = cpu["sockets"]

            data["archive"] = f"{storage_id}:backup/{path}"
            return data

        def build_configuration(data, params):
            vmid = params.get("vmid")
            if vmid is not None:
                data["vmid"] = vmid

            name = params.get("name")
            if name:
                data["name"] = name

            memory = params.get("memory_mb")
            if memory is not None:
                data["memory"] = memory

            cpu = params.get("cpu", {})
            if cpu.get("cores") is not None:
                data["cores"] = cpu["cores"]
            if cpu.get("sockets") is not None:
                data["sockets"] = cpu["sockets"]
            if cpu.get("type"):
                data["cpu"] = cpu["type"]

            guest = params.get("guest")
            if guest:
                ostype = self.PROXMOX_GUEST_MAP.get(guest)
                if ostype is not None:
                    data["ostype"] = ostype

            disks = params.get("disks", [])
            networks = params.get("networks", [])
            options = params.get("options", {})
            boot_params = params.get("boot", {})

            # DISKS
            for disk in disks:
                slot = disk.get("slot")
                storage_id = disk.get("storage_id")
                size_gb = disk.get("size_gb")
                controller_type = disk.get("controller_type")
                import_from = disk.get("import_from")

                if not slot:
                    raise ValueError("Disk requires slot")
                if not storage_id:
                    raise ValueError("Disk requires storage_id")

                if slot == "ide2":
                    raise ValueError("Slot ide2 is reserved for ISO/CD-ROM")

                if slot.startswith("scsi") and controller_type and controller_type != "default":
                    data["scsihw"] = controller_type

                parts = []

                if import_from:
                    parts.append(f"{storage_id}:0")
                    parts.append(f"import-from={import_from}")
                else:
                    if size_gb is None:
                        raise ValueError("Disk without import_from requires size_gb")
                    parts.append(f"{storage_id}:{size_gb}")

                if slot.startswith("scsi") and controller_type == "virtio-scsi-single":
                    parts.append("iothread=1")

                if disk.get("backup") is False:
                    parts.append("backup=0")

                data[slot] = ",".join(parts)

            # NETWORKS
            for nic in networks:
                if not nic.get("connected", True):
                    continue

                slot = nic.get("slot")
                if not slot:
                    raise ValueError("Network requires slot")

                bridge = nic.get("network_id")
                if not bridge:
                    raise ValueError("Network requires network_id")

                model = nic.get("model", "virtio")
                parts = [model, f"bridge={bridge}"]

                mac = nic.get("mac")
                if mac:
                    parts.append(f"macaddr={mac}")

                data[slot] = ",".join(parts)

            # OPTIONS
            if "autostart" in options:
                data["onboot"] = 1 if options["autostart"] else 0

            graphics = options.get("graphics")
            if graphics and graphics != "default":
                data["vga"] = graphics

            # BOOT
            order = boot_params.get("order", [])
            firmware = boot_params.get("firmware")
            machine = boot_params.get("machine")

            if machine and machine != "default":
                data["machine"] = machine

            if firmware and firmware != "default":
                if firmware in ("bios", "seabios"):
                    data["bios"] = "seabios"
                elif firmware in ("ovmf", "uefi"):
                    data["bios"] = "ovmf"

            if order:
                data["boot"] = "order=" + ";".join(order)

            return data

        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu"
        next_id_url = f"https://{self.conn.host}/api2/json/cluster/nextid"

        vmid = self.conn.request(method="GET", url=next_id_url)["data"]
        opt_params["vmid"] = vmid

        start_after_create = opt_params.get("options", {}).get("start_after_create", False)

        data = {}
        source = opt_params.get("source", {})

        if source:
            stype = source.get("type")

            if stype == "backup":
                data = create_from_backup(source, opt_params)
                result = self.conn.request(method="POST", url=url, data=data)

                return {
                    "success": True,
                    "data": result,
                    "vmid": str(vmid),
                }

            elif stype in ("template"):
                template_vmid = source.get("vmid")
                if template_vmid is None:
                    raise ValueError("Template requires vmid")

                new_vmid = opt_params.get("vmid")
                if new_vmid is None:
                    raise ValueError("Template clone requires target vmid")

                target = source.get("target", {})
                storage_id = target.get("storage_id")
                full_clone = target.get("full", True)

                clone_data = {
                    "newid": new_vmid,
                    "full": 1 if full_clone else 0
                }

                name = opt_params.get("name")
                if name:
                    clone_data["name"] = name

                if storage_id:
                    clone_data["storage"] = storage_id

                url_clone = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{template_vmid}/clone"
                clone_result = self.conn.request(method="POST", url=url_clone, data=clone_data)

                config_data = build_configuration({}, opt_params)
                config_data.pop("vmid", None)

                url_config = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{new_vmid}/config"
                self.conn.request(method="PUT", url=url_config, data=config_data)

                if start_after_create:
                    self.set_vm_status(node_name, str(new_vmid), "start")

                return {
                    "success": True,
                    "data": clone_result,
                    "vmid": str(new_vmid),
                }

            elif stype == "iso":
                storage_id = source.get("storage_id")
                path = source.get("path")

                if not storage_id or not path:
                    raise ValueError("ISO requires storage_id and path")

                data["ide2"] = f"{storage_id}:iso/{path},media=cdrom"

            data = build_configuration(data, opt_params)
            create_result = self.conn.request(method="POST", url=url, data=data)

            if start_after_create:
                self.set_vm_status(node_name, str(vmid), "start")

            return {
                "success": True,
                "data": create_result,
                "vmid": str(vmid),
            }


    def get_vm_status(self, node_name: str, vm_id: str, params: dict) -> dict:
        """Vrátí aktuální stav a základní resource statistiky virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            params: Doplňující parametry volání.

        Returns:
            Stav virtuálního stroje obsahující (uptime, CPU, paměť, disk...).
        """

        vm_url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/status/current"
        
        vm_res = self.conn.request(method="GET", url=vm_url)
        vm_data = vm_res.get("data", {})

        disk_total, disk_used, disk_free = self._get_vm_disk_usage_from_storage(node_name, vm_id)

        return {
            "uptime": vm_data.get("uptime"),
            "cpu_num": vm_data.get("cpus"),
            "cpu_usage": vm_data.get("cpu"),
            "memory_total": vm_data.get("maxmem"),
            "memory_used": vm_data.get("mem"),
            "memory_free": vm_data.get("freemem"),
            "disk_total": disk_total if disk_total is not None else vm_data.get("maxdisk"),
            "disk_used": disk_used,
            "disk_free": disk_free,
            "sysname": vm_data.get("name"), 
        }


    def set_vm_status(self, node_name: str, vm_id: str, status: str) -> dict:
        """Změní stav virtuálního stroje.

        Meti podporované operace patří: `start`, `stop`, `shutdown`, `suspend`, `reset`, `reboot`, `resume`

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            status: Cílová stavová akce.

        Returns:
            Identifikátor úlohy vytvořené Proxmoxem ve formátu:
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/status/{status}"

        res = self.conn.request(method="POST", url=url)

        return {
            "task_id": res.get("data")
        }
    
    def get_vm_time_metrics(self, node_name: str, vm_id: str, params: dict) -> list[dict]:
        """Vrátí časovou řadu výkonových metrik virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            params (dict): Parametry dotazu:
                - timeframe: časové období
                - fields: seznam požadovaných metrik

        Returns:
            Seznam časových bodů.
        """
        
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/rrddata"

        res = self.conn.request(
            method="GET",
            url=url,
            params={"timeframe": params["timeframe"]}
        ).get("data", [])

        result = []

        for point in res:
            p = {}
            p["time"] = point["time"]

            for proxmox_key, api_key in self.RRD_METRICS.items():
                if api_key in params["fields"] and proxmox_key in point:
                    p[api_key] = point[proxmox_key]

            result.append(p)

        return result
    
    def manage_vm_snapshots(self, node_name: str, vm_id: str, snap_parameters: dict | None = None) -> dict | list[dict]:
        """Vytvoří snapshot nebo vrátí seznam snapshotů virtuálního stroje.

        Pokud jsou předány `snap_parameters`, metoda vytvoří nový snapshot.
        Jinak vrací seznam existujících snapshotů.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snap_parameters (dict | None): Parametry pro vytvoření snapshotu.

        Returns:
            Id tasku pro vytvoření nového snapshotu nebo seznam všech snapshotů daného virtualního stroje. 
        """

        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/snapshot"

        if snap_parameters:
            res = self.conn.request(method="POST", url=url, data=snap_parameters)

            print(res)
            
            return {
                "task_id": res.get("data")
            }

        data = self.conn.request(method="GET", url=url)["data"]

        result = []
        for snapshot in data:
            item = dict(snapshot)
            item["id"] = snapshot.get("name")
            result.append(item)

        return result
        
    def drop_vm_snapshot(self, node_name: str, vm_id: str, snapname: str) -> None:
        """Smaže snapshot virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snapname: Název snapshotu.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/snapshot/{snapname}"
        self.conn.request(method="DELETE", url=url) 
    
    def rollback_vm_snapshot(self, node_name: str, vm_id: str, snapname: str) -> None:
        """Provede rollback virtuálního stroje na zadaný snapshot.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snapname: Název cílového snapshotu.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/snapshot/{snapname}/rollback"

        self.conn.request(method="POST", url=url)
    
    def get_vm_config(self, node_name: str, vm_id: str) -> dict:
        """Vrátí normalizovanou konfiguraci virtuálního stroje.

        Konfigurace je převedena z formátu Proxmox API do interní, čitelnější
        struktury zahrnující CPU, paměť, disky, CD-ROM mechaniky, sítě,
        boot nastavení a obecné volby.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.

        Returns:
            Normalizovaná konfigurace VM.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/config"
        response = self.conn.request(method="GET", url=url, params={"current": 1})
        data = response.get("data", response)

        def map_ostype(ostype: str) -> str | None:
            reverse_map = {v: k for k, v in self.PROXMOX_GUEST_MAP.items()}
            return reverse_map.get(ostype)

        def parse_boot_order(boot: str) -> list:
            if not boot:
                return []
            if boot.startswith("order="):
                boot = boot[len("order="):]
            return [item.strip() for item in boot.split(";") if item.strip()]

        def parse_config(value: str) -> dict:
            result = {}
            if not value:
                return result

            for part in value.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result

        result = {
            "vmid": int(vm_id),
            "name": data.get("name"),
            "memory_mb": int(data["memory"]) if data.get("memory") else None,
            "cpu": {
                "cores": int(data["cores"]) if data.get("cores") else None,
                "sockets": int(data["sockets"]) if data.get("sockets") else None,
                "type": data.get("cpu"),
            },
            "guest": map_ostype(data.get("ostype")),
            "disks": [],
            "cdroms": [],
            "networks": [],
            "boot": {
                "order": parse_boot_order(data.get("boot", "")),
                "firmware": data.get("bios", "default"),
                "machine": data.get("machine", "default"),
            },
            "options": {
                "autostart": str(data.get("onboot", "0")) == "1",
                "start_after_create": False,
                "graphics": data.get("vga", "default"),
            },
        }

        for key, value in data.items():
            if re.match(r"^(scsi|sata|virtio|ide)\d+$", key):
                parsed = parse_config(value)
                first_part = value.split(",")[0] if value else ""

                storage_id = None
                volume = None
                if ":" in first_part:
                    storage_id, volume = first_part.split(":", 1)

                size_gb = None
                if parsed.get("size"):
                    size = parsed["size"]
                    if size.endswith("G"):
                        try:
                            size_gb = int(size[:-1])
                        except ValueError:
                            size_gb = None

                item = {
                    "slot": key,
                    "storage_id": storage_id,
                    "storage": storage_id,
                    "volume": volume,
                    "size_gb": size_gb,
                    "controller_type": data.get("scsihw") if key.startswith("scsi") else key.rstrip("0123456789"),
                }

                if parsed.get("media") == "cdrom":
                    result["cdroms"].append(item)
                else:
                    result["disks"].append(item)

            elif re.match(r"^net\d+$", key):
                parsed = parse_config(value)

                model = None
                mac = None
                for candidate in ["virtio", "e1000", "rtl8139", "vmxnet3"]:
                    if candidate in parsed:
                        model = candidate
                        mac = parsed[candidate]
                        break

                result["networks"].append({
                    "slot": key,
                    "network_id": parsed.get("bridge"),
                    "model": model,
                    "mac": mac,
                    "connected": parsed.get("link_down", "0") != "1",
                })

        return result
    
    def set_vm_config(self, node_name: str, vm_id: str, optional_params: dict) -> dict:
        """Aktualizuje konfiguraci virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            optional_params: Parametry konfigurace, které mají být změněny.
        """

        config_url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/config"

        current_config = self.get_vm_config(node_name, vm_id)
        current_status = self.get_vm_status(node_name, vm_id, {})

        status_url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/status/current"
        raw_status = self.conn.request(method="GET", url=status_url).get("data", {})

        power_state = (raw_status.get("status") or "").lower()
        was_running = power_state == "running"

        config_data = self._build_proxmox_config(optional_params, for_update=True)

        requested_cdrom_slots = {
            cdrom.get("slot")
            for cdrom in optional_params.get("cdroms", []) or []
            if cdrom.get("slot")
        }

        current_cdrom_slots = {
            cdrom.get("slot")
            for cdrom in current_config.get("cdroms", []) or []
            if cdrom.get("slot")
        }

        cdroms_to_delete = current_cdrom_slots - requested_cdrom_slots

        if cdroms_to_delete:
            config_data["delete"] = ",".join(sorted(cdroms_to_delete))

        requested_disks = optional_params.get("disks", []) or []
        current_disks = current_config.get("disks", []) or []

        disk_resize_required = False

        for requested_disk in requested_disks:
            slot = requested_disk.get("slot")
            requested_size = requested_disk.get("size_gb")

            if not slot or requested_size is None:
                continue

            current_disk = next(
                (disk for disk in current_disks if disk.get("slot") == slot),
                None
            )

            if not current_disk:
                continue

            current_size = current_disk.get("size_gb")

            if current_size is None:
                continue

            if int(requested_size) > int(current_size):
                disk_resize_required = True
                break

        requires_shutdown = any([
            "memory_mb" in optional_params
            and int(optional_params.get("memory_mb") or 0) != int(current_config.get("memory_mb") or 0),

            "cpu" in optional_params
            and (
                int((optional_params.get("cpu") or {}).get("cores") or 1)
                != int((current_config.get("cpu") or {}).get("cores") or 1)
                or int((optional_params.get("cpu") or {}).get("sockets") or 1)
                != int((current_config.get("cpu") or {}).get("sockets") or 1)
            ),

            bool(cdroms_to_delete),
            disk_resize_required,
        ])

        if requires_shutdown and was_running:
            print("STOPPING PROXMOX VM")
            self.set_vm_status(node_name, vm_id, "stop")

            for _ in range(30):
                status_res = self.conn.request(method="GET", url=status_url).get("data", {})
                state = (status_res.get("status") or "").lower()

                print("PROXMOX VM STATE:", state)

                if state == "stopped":
                    break

                time.sleep(1)
            else:
                raise ValueError("VM did not stop in time")

        config_result = self.conn.request(
            method="POST",
            url=config_url,
            data=config_data
        )

        for requested_disk in requested_disks:
            slot = requested_disk.get("slot")
            requested_size = requested_disk.get("size_gb")

            if not slot or requested_size is None:
                continue

            current_disk = next(
                (disk for disk in current_disks if disk.get("slot") == slot),
                None
            )

            if not current_disk:
                continue

            current_size = current_disk.get("size_gb")

            if current_size is None:
                continue

            requested_size = int(requested_size)
            current_size = int(current_size)

            if requested_size > current_size:
                resize_url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/resize"

                self.conn.request(
                    method="PUT",
                    url=resize_url,
                    data={
                        "disk": slot,
                        "size": f"{requested_size}G",
                    }
                )

        return {
            "success": True,
            "required_action": "shutdown" if requires_shutdown else "none",
            "was_running": was_running,
        }
    
    def get_vm_backups(self, node_name:str, vm_id:str) -> list[dict]:
        """Vrátí seznam dostupných záloh pro zadaný virtuální stroj.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.

        Returns:
            Seznam záloh vrácených Proxmox API.
        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/storage/data/content"

        return self.conn.request(method="GET", url=url, params={"content":"backup", "vmid": vm_id})["data"]
    
    def create_vm_backup(self, node_name:str, vm_id: str, backup_root: str) -> None:
        """Vytvoří zálohu virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.

        """
        url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/vzdump"

        self.conn.request(method="POST", url=url, params={"vmid":{vm_id}, "storage": "data"})
    
    def get_vm_logs(
        self,
        node_name: str,
        vm_id: str,
        line_limit: int = 200,
    ) -> dict:
        """Vrátí logy úloh souvisejících s virtuálním strojem.

        Metoda iteruje přes tasky Proxmoxu, načítá jejich logy a vrací
        sjednocený seznam řádků seřazený podle času a pořadí v logu.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            line_limit: Maximální počet vrácených řádků logu.

        Returns:
            Slovník logů a jejich parametrů

        Raises:
            ValueError: Pokud `vm_id` chybí nebo je `line_limit` záporný.
        """
        if not vm_id:
            raise ValueError("vm_id is required")

        if line_limit < 0:
            raise ValueError("line_limit must be >= 0")

        base_url = f"https://{self.conn.host}/api2/json/nodes/{node_name}"

        task_page_size = 20
        task_start = 0
        max_task_pages = 5 if line_limit > 0 else 50

        collected_lines = []

        def fetch_full_task_log(upid: str) -> list[dict]:
            log_lines = []
            log_start = 0
            log_page_size = 200

            while True:
                resp = self.conn.request(
                    method="GET",
                    url=f"{base_url}/tasks/{upid}/log",
                    params={
                        "start": log_start,
                        "limit": log_page_size,
                    },
                )

                chunk = resp.get("data", []) or []
                if not chunk:
                    break

                log_lines.extend(chunk)

                if len(chunk) < log_page_size:
                    break

                log_start += log_page_size

            return log_lines

        current_page = 0

        while current_page < max_task_pages:
            tasks_resp = self.conn.request(
                method="GET",
                url=f"{base_url}/tasks",
                params={
                    "vmid": vm_id,
                    "start": task_start,
                    "limit": task_page_size,
                },
            )

            tasks = tasks_resp.get("data", []) or []
            if not tasks:
                break

            for task in tasks:
                upid = task.get("upid")
                if not upid:
                    continue

                task_log = fetch_full_task_log(upid)
                if not task_log:
                    continue

                normalized = [
                    {
                        "upid": upid,
                        "type": task.get("type"),
                        "starttime": task.get("starttime"),
                        "status": task.get("status"),
                        "line_no": item.get("n"),
                        "text": item.get("t"),
                    }
                    for item in task_log
                ]

                collected_lines.extend(normalized)

            task_start += task_page_size
            current_page += 1

            if line_limit > 0 and len(collected_lines) >= line_limit:
                break

        if collected_lines:
            collected_lines.sort(
                key=lambda x: (
                    x.get("starttime") or 0,
                    x.get("line_no") or 0,
                )
            )

        if line_limit > 0:
            collected_lines = collected_lines[-line_limit:]

        return {
            "lines_count": len(collected_lines),
            "lines": collected_lines,
        }

    def open_console(self, node_name: str, vm_id: str, protocol: str = "vnc") -> dict:
        """Otevře konzolové připojení k virtuálnímu stroji.

        Aktuálně je implementována pouze varianta `vnc`.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            protocol: Typ protokolu pro konzoli. Podporováno je `vnc`.

        Returns:
            Informace potřebné pro připojení variantou `vnc`
        """
        if protocol == "vnc":
            url = f"https://{self.conn.host}/api2/json/nodes/{node_name}/qemu/{vm_id}/vncproxy"
            res = self.conn.request(method="POST", url=url)

            data = res["data"]
            encoded_ticket = quote(data["ticket"], safe="")

            return {
                "protocol": "vnc",
                "port": data["port"],
                "ticket": data["ticket"],
                "ws_url": (
                    f"wss://{self.conn.host}"
                    f"/api2/json/nodes/{node_name}/qemu/{vm_id}/vncwebsocket"
                    f"?port={data['port']}&vncticket={encoded_ticket}"
                )
            }
        
    def _build_proxmox_config(self, params: dict, for_update: bool = False) -> dict:
        """Převede interní konfiguraci VM do formátu očekávaného Proxmox API.

        Args:
            params (dict): Interní reprezentace konfigurace VM.
            for_update (bool): Pokud je `True`, neodesílá se `vmid` pro vytvoření
                nové VM, ale jen změny pro update existující konfigurace.

        Returns:
            Konfigurační data připravená pro Proxmox API.

        Raises:
            ValueError: Pokud některá část konfigurace neobsahuje povinné hodnoty.
        """
         
        data = {}

        vmid = params.get("vmid")
        if vmid is not None and not for_update:
            data["vmid"] = vmid

        name = params.get("name")
        if name:
            data["name"] = name

        memory = params.get("memory_mb")
        if memory is not None:
            data["memory"] = memory

        cpu = params.get("cpu", {})
        if cpu.get("cores") is not None:
            data["cores"] = cpu["cores"]
        if cpu.get("sockets") is not None:
            data["sockets"] = cpu["sockets"]
        if cpu.get("type"):
            data["cpu"] = cpu["type"]

        guest = params.get("guest")
        if guest:
            ostype = self.PROXMOX_GUEST_MAP.get(guest)
            if ostype is not None:
                data["ostype"] = ostype

        disks = params.get("disks", [])
        networks = params.get("networks", [])
        cdroms = params.get("cdroms", [])
        options = params.get("options", {})
        boot_params = params.get("boot", {})

        # DISKS
        for disk in disks:
            slot = disk.get("slot")
            storage_id = disk.get("storage_id")
            size_gb = disk.get("size_gb")
            controller_type = disk.get("controller_type")
            import_from = disk.get("import_from")
            volume = disk.get("volume")

            if not slot:
                raise ValueError("Disk requires slot")

            if slot == "ide2":
                raise ValueError("Slot ide2 is reserved for ISO/CD-ROM")

            if slot.startswith("scsi") and controller_type and controller_type != "default":
                data["scsihw"] = controller_type

            parts = []

            if import_from:
                if not storage_id:
                    raise ValueError("Disk with import_from requires storage_id")
                parts.append(f"{storage_id}:0")
                parts.append(f"import-from={import_from}")

            elif volume:
                if not storage_id:
                    raise ValueError("Disk with volume requires storage_id")
                parts.append(f"{storage_id}:{volume}")

            else:
                if not storage_id:
                    raise ValueError("Disk requires storage_id")
                if size_gb is None:
                    raise ValueError("Disk without import_from/volume requires size_gb")
                parts.append(f"{storage_id}:{size_gb}")

            if size_gb is not None:
                parts.append(f"size={size_gb}G")

            if slot.startswith("scsi") and controller_type and controller_type != "default":
                parts.append("iothread=1")

            if disk.get("backup") is False:
                parts.append("backup=0")

            data[slot] = ",".join(parts)

        # CDROMS
        for cdrom in cdroms:
            slot = cdrom.get("slot")
            storage_id = cdrom.get("storage_id")
            volume = cdrom.get("volume")
            path = cdrom.get("path")

            if not slot:
                raise ValueError("CD-ROM requires slot")

            if not storage_id:
                raise ValueError("CD-ROM requires storage_id")

            source = volume or path
            if not source:
                raise ValueError("CD-ROM requires volume or path")

            source = str(source).strip()

            if ":" in source:
                proxmox_volume = source
            elif source.startswith("iso/"):
                proxmox_volume = f"{storage_id}:{source}"
            else:
                proxmox_volume = f"{storage_id}:iso/{source}"

            data[slot] = f"{proxmox_volume},media=cdrom"

        # NETWORKS
        for nic in networks:
            slot = nic.get("slot")
            if not slot:
                raise ValueError("Network requires slot")

            bridge = nic.get("network_id")
            if not bridge:
                raise ValueError("Network requires network_id")

            model = nic.get("model", "virtio")
            mac = nic.get("mac")
            connected = nic.get("connected", True)

            parts = [model, f"bridge={bridge}"]

            if mac:
                parts.append(f"macaddr={mac}")

            if not connected:
                parts.append("link_down=1")

            data[slot] = ",".join(parts)

        # OPTIONS
        if "autostart" in options:
            data["onboot"] = 1 if options["autostart"] else 0

        graphics = options.get("graphics")
        if graphics and graphics != "default":
            data["vga"] = graphics

        # BOOT
        order = boot_params.get("order", [])
        firmware = boot_params.get("firmware")
        machine = boot_params.get("machine")

        if machine and machine != "default":
            data["machine"] = machine

        if firmware and firmware != "default":
            if firmware in ("bios", "seabios"):
                data["bios"] = "seabios"
            elif firmware in ("ovmf", "uefi"):
                data["bios"] = "ovmf"

        if order:
            data["boot"] = "order=" + ";".join(order)

        return data
    

    def _get_vm_disk_usage_from_storage(self, node: str, vmid: str) -> tuple[int | None, int | None, int | None]:
        """Spočítá celkovou, využitou a volnou diskovou kapacitu VM ze storage vrstev.

        Prochází storage dostupná na uzlu, filtruje ta, která obsahují `images`,
        a následně agreguje velikosti diskových volume přiřazených k dané VM.

        Args:
            node: Název Proxmox uzlu.
            vmid: Identifikátor virtuálního stroje.

        Returns: Trojice ve formátu `(disk_total, disk_used, disk_free)` v bajtech.

        """
        storages_url = f"https://{self.conn.host}/api2/json/nodes/{node}/storage"
        storages_res = self.conn.request(method="GET", url=storages_url)
        storages = storages_res.get("data", [])

        total_sum = 0
        used_sum = 0
        found_any = False
        found_used_field = False

        for storage in storages:
            storage_id = storage.get("storage")
            content = storage.get("content", "")

            if not storage_id:
                continue

            content_types = {x.strip() for x in content.split(",") if x.strip()}
            if "images" not in content_types:
                continue

            content_url = f"https://{self.conn.host}/api2/json/nodes/{node}/storage/{storage_id}/content"
            content_res = self.conn.request(
                method="GET",
                url=content_url,
                params={"vmid": int(vmid)}
            )
            volumes = content_res.get("data", [])

            for vol in volumes:
                found_any = True

                vol_total = vol.get("size")
                vol_used = vol.get("used")

                if isinstance(vol_total, (int, float)):
                    total_sum += int(vol_total)

                if isinstance(vol_used, (int, float)):
                    used_sum += int(vol_used)
                    found_used_field = True

        if not found_any:
            return None, None, None

        if not found_used_field:
            return total_sum if total_sum > 0 else None, None, None

        return total_sum, used_sum, max(total_sum - used_sum, 0)