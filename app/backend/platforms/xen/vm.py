from platforms.base.vm import BaseVmApi
import os
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from config import LOG_ROOT
from config import BACKUP_ROOT
from fastapi import HTTPException
import time
from platforms.xen.connection import XenConnection

class XenVmApi(BaseVmApi):
    """Implementace API vrstvy pro správu virtuálních strojů v Xen prostředí.

    Třída poskytuje operace pro:

    - vytváření a mazání VM
    - změnu stavu VM
    - čtení konfigurace a metrik
    - práci se snapshoty
    - práci se zálohami
    - otevření konzole
    
    """

    XEN_GUEST_TEMPLATE_MAP = {
        "linux24": "07d91aaa-43f7-430a-bf84-0edb6714df0f",   # Debian Bookworm 12
        "linux": "dfbd1201-329f-4c87-9f0c-78a6f5270ba0",     # Generic Linux BIOS
        "windows-modern": "7774689b-4ca1-4dea-8545-dddd6b64c17f",  # Windows 10 (64-bit)
        "windows-latest": "1f8728f9-6354-4a68-adc3-222c34f2bb94",  # Windows 11
        "other32": "552bce37-51b2-445d-84f2-5f33fa112d7e",   # Other install media
        "other64": "552bce37-51b2-445d-84f2-5f33fa112d7e",   # Other install media
    }

    def __init__(self, connection: XenConnection):
        self.conn = connection

    def create_vm(self, node_id: str, opt_params: dict) -> dict:
        """Vytvoří nový virtuální stroj v Xen prostředí.

        Podporované zdroje vytvoření:

        - ze zálohy (`backup`)
        - z template (`template`)
        - z ISO obrazu (`iso`)

        Metoda následně aplikuje požadovanou konfiguraci:

        - paměť
        - CPU
        - disky
        - síťové adaptéry
        - boot parametry
        - autostart / start po vytvoření

        Args:
            node_id: UUID uzlu.
            opt_params: Interní konfigurace VM včetně zdroje, CPU, paměti, disků, sítí, boot parametrů a dalších voleb.

        Returns:
            Slovník s informací o výsledku vytvoření VM.

        Raises:
            ValueError: Pokud chybí povinné parametry nebo není nalezen template, storage, network nebo host.
        """

        def slot_to_userdevice(slot: str) -> str:
            if slot.startswith(("scsi", "xvd", "sd", "hd", "vd", "ide", "sata")):
                suffix = "".join(ch for ch in slot if ch.isdigit())
                if suffix == "":
                    raise ValueError(f"Invalid disk slot: {slot}")
                return suffix
            raise ValueError(f"Unsupported disk slot: {slot}")

        def nic_slot_to_device(slot, fallback_index: int) -> str:
            if slot is None:
                return str(fallback_index)

            suffix = "".join(ch for ch in str(slot) if ch.isdigit())
            if suffix == "":
                return str(fallback_index)
            return suffix

        def build_configuration(params: dict) -> dict:
            config = {}

            name = params.get("name")
            if name:
                config["name"] = name

            memory = params.get("memory_mb")
            if memory is not None:
                config["memory_mb"] = int(memory)

            cpu = params.get("cpu", {})
            config["cpu"] = {}

            if cpu.get("cores") is not None:
                config["cpu"]["cores"] = int(cpu["cores"])

            if cpu.get("sockets") is not None:
                config["cpu"]["sockets"] = int(cpu["sockets"])

            if cpu.get("type"):
                config["cpu"]["type"] = cpu["type"]

            guest = params.get("guest")
            if guest:
                config["guest"] = guest

            disks = params.get("disks", [])
            config["disks"] = []
            for disk in disks:
                slot = disk.get("slot")
                storage_id = disk.get("storage_id")
                size_gb = disk.get("size_gb")

                if not slot:
                    raise ValueError("Disk requires slot")
                if not storage_id:
                    raise ValueError("Disk requires storage_id")
                if size_gb is None:
                    raise ValueError("Disk requires size_gb")

                config["disks"].append({
                    "slot": slot,
                    "storage_id": storage_id,
                    "size_gb": int(size_gb),
                    "read_only": bool(disk.get("read_only", False)),
                    "bootable": bool(disk.get("bootable", False)),
                })

            networks = params.get("networks", [])
            config["networks"] = []
            for nic in networks:
                if not nic.get("connected", True):
                    continue

                network_id = nic.get("network_id")
                if not network_id:
                    raise ValueError("Network requires network_id")

                config["networks"].append({
                    "slot": nic.get("slot"),
                    "network_id": network_id,
                    "model": nic.get("model", "virtio"),
                    "mac": nic.get("mac"),
                })

            options = params.get("options", {})
            config["options"] = {
                "autostart": bool(options.get("autostart", False)),
                "start_after_create": bool(options.get("start_after_create", False)),
                "graphics": options.get("graphics"),
            }

            boot = params.get("boot", {})
            config["boot"] = {
                "order": boot.get("order", []),
                "firmware": boot.get("firmware"),
                "machine": boot.get("machine"),
            }

            return config

        vm_ref = None
        source = opt_params.get("source", {})
        if not source:
            raise ValueError("Missing source")

        stype = source.get("type")

        name = opt_params.get("name")
        if not name:
            raise ValueError("VM name is required")

        config_data = build_configuration(opt_params)
        guest = config_data.get("guest")

        debug = {
            "stype": stype,
            "node": node_id,
            "source": source,
            "config_data": config_data,
            "guest": guest,
        }

        host_ref = None
        if node_id:
            host_ref = self.conn.get_xapi_obj_ref("host", str(node_id))
            debug["host_ref"] = host_ref
            if not host_ref:
                raise ValueError(f"Host '{node_id}' was not found")


        if stype == "backup":

            name = opt_params.get("name")
            path = os.path.join(BACKUP_ROOT, 'xen', source.get("path"))

            if not path:
                raise ValueError("Backup requires source.path")

            if not name:
                raise ValueError("Backup restore requires name")

            if not os.path.exists(path):
                raise ValueError(f"Backup file '{path}' does not exist")

            host_ref = None
            if node_id:
                host_ref = self.conn.get_xapi_obj_ref("host", str(node_id))
                debug["host_ref"] = host_ref

                if not host_ref:
                    raise ValueError(f"Host '{node_id}' was not found")

            import_result = self.conn.import_xva(
                file_path=path,
                session_ref=self.conn.session,
                host_ref=host_ref
            )

            debug["import_result"] = import_result

            vm_ref = import_result.get("vm_ref")
            if not vm_ref:
                raise ValueError("Backup import did not return VM reference")

            debug["vm_ref"] = vm_ref

            vm_record = self.conn.request(
                "POST",
                "VM.get_record",
                [self.conn.session, vm_ref]
            )
            debug["vm_record"] = vm_record

            self.conn.request(
                "POST",
                "VM.set_name_label",
                [self.conn.session, vm_ref, name]
            )

            if host_ref:
                self.conn.request(
                    "POST",
                    "VM.set_affinity",
                    [self.conn.session, vm_ref, host_ref]
                )

            vm_uuid = self.conn.request(
                "POST",
                "VM.get_uuid",
                [self.conn.session, vm_ref]
            )

            return {
                "success": True,
                "vmid": vm_uuid,
                "data": {},
            }

        if stype in ("template", "clone"):
            template_vmid = source.get("vmid")
            if not template_vmid and guest:
                template_vmid = self.XEN_GUEST_TEMPLATE_MAP.get(guest)

            debug["template_vmid"] = template_vmid

            if not template_vmid:
                raise ValueError("Template requires vmid or supported guest type")

            template_ref = self.conn.get_xapi_obj_ref("VM", str(template_vmid))
            debug["template_ref"] = template_ref

            if not template_ref:
                raise ValueError(f"Template '{template_vmid}' was not found")

            target = source.get("target", {})
            full_clone = bool(target.get("full", False))
            target_storage_id = target.get("storage_id")

            debug["full_clone"] = full_clone
            debug["target_storage_id"] = target_storage_id

            if full_clone:
                if not target_storage_id:
                    raise ValueError("Full clone requires target.storage_id")

                target_sr_ref = self.conn.get_xapi_obj_ref("SR", str(target_storage_id))
                debug["target_sr_ref"] = target_sr_ref

                if not target_sr_ref:
                    raise ValueError(f"Target storage '{target_storage_id}' was not found")

                new_vm = self.conn.request(
                    "POST",
                    "VM.copy",
                    [self.conn.session, template_ref, name, target_sr_ref]
                )
            else:
                new_vm = self.conn.request(
                    "POST",
                    "VM.clone",
                    [self.conn.session, template_ref, name]
                )

            if not new_vm:
                raise ValueError("VM clone/copy returned no VM reference")
            
        elif stype == "iso":
            
            template_vmid = source.get("vmid")
            if not template_vmid and guest:
                template_vmid = self.XEN_GUEST_TEMPLATE_MAP.get(guest)

            if not template_vmid:
                raise ValueError("ISO requires vmid or supported guest type")

            template_ref = self.conn.get_xapi_obj_ref("VM", str(template_vmid))

            if not template_ref:
                raise ValueError(f"ISO template '{template_vmid}' was not found")

            new_vm = self.conn.request(
                "POST",
                "VM.clone",
                [self.conn.session, template_ref, name]
            )

            if not new_vm:
                raise ValueError("VM clone returned no VM reference")

            debug["provision_result"] = self.conn.request(
                "POST",
                "VM.provision",
                [self.conn.session, new_vm]
            )

        else:
            raise ValueError(f"Unsupported source type: {stype}")

        debug["vm_record"] = self.conn.request(
            "POST",
            "VM.get_record",
            [self.conn.session, new_vm]
        )

        if host_ref:
            debug["affinity_result"] = self.conn.request(
                "POST",
                "VM.set_affinity",
                [self.conn.session, new_vm, host_ref]
            )

        if config_data.get("name"):
            debug["set_name_label"] = self.conn.request(
                "POST",
                "VM.set_name_label",
                [self.conn.session, new_vm, config_data["name"]]
            )

        if config_data.get("memory_mb") is not None:
            memory_bytes = int(config_data["memory_mb"]) * 1024 * 1024
            debug["memory_bytes"] = memory_bytes

            debug["set_memory_limits"] = self.conn.request(
                "POST",
                "VM.set_memory_limits",
                [
                    self.conn.session,
                    new_vm,
                    str(memory_bytes),
                    str(memory_bytes),
                    str(memory_bytes),
                    str(memory_bytes),
                ]
            )

        cpu = config_data.get("cpu", {})
        cores = cpu.get("cores")
        sockets = cpu.get("sockets", 1)

        if cores is not None:
            vcpus = int(cores) * int(sockets)
            debug["vcpus"] = vcpus

            debug["set_vcpus_max"] = self.conn.request(
                "POST",
                "VM.set_VCPUs_max",
                [self.conn.session, new_vm, str(vcpus)]
            )
            debug["set_vcpus_startup"] = self.conn.request(
                "POST",
                "VM.set_VCPUs_at_startup",
                [self.conn.session, new_vm, str(vcpus)]
            )

        debug["created_disks"] = []
        for disk in config_data.get("disks", []):
            disk_debug = {"input": disk}

            sr_ref = self.conn.get_xapi_obj_ref("SR", str(disk["storage_id"]))
            disk_debug["sr_ref"] = sr_ref

            if not sr_ref:
                raise ValueError(f"Storage '{disk['storage_id']}' was not found")

            size_bytes = int(disk["size_gb"]) * 1024 * 1024 * 1024
            disk_debug["size_bytes"] = size_bytes

            vdi_record = {
                "name_label": f'{config_data.get("name", "vm")}-{disk["slot"]}',
                "name_description": "",
                "SR": sr_ref,
                "virtual_size": str(size_bytes),
                "type": "user",
                "sharable": False,
                "read_only": bool(disk.get("read_only", False)),
                "other_config": {},
                "sm_config": {},
                "xenstore_data": {},
                "tags": [],
            }
            disk_debug["vdi_record"] = vdi_record

            vdi_ref = self.conn.request(
                "POST",
                "VDI.create",
                [self.conn.session, vdi_record]
            )
            disk_debug["vdi_ref_raw"] = vdi_ref

            if isinstance(vdi_ref, dict):
                vdi_ref = vdi_ref.get("Value", vdi_ref.get("value", vdi_ref))

            disk_debug["vdi_ref"] = vdi_ref

            vbd_record = {
                "VM": new_vm,
                "VDI": vdi_ref,
                "userdevice": slot_to_userdevice(disk["slot"]),
                "bootable": bool(disk.get("bootable", False)),
                "mode": "RO" if disk.get("read_only", False) else "RW",
                "type": "Disk",
                "unpluggable": True,
                "empty": False,
                "other_config": {},
                "qos_algorithm_type": "",
                "qos_algorithm_params": {},
            }
            disk_debug["vbd_record"] = vbd_record

            disk_debug["vbd_create_result"] = self.conn.request(
                "POST",
                "VBD.create",
                [self.conn.session, vbd_record]
            )

            debug["created_disks"].append(disk_debug)

        debug["created_networks"] = []
        for idx, nic in enumerate(config_data.get("networks", [])):
            nic_debug = {"input": nic, "index": idx}

            network_ref = self.conn.get_xapi_obj_ref("network", str(nic["network_id"]))
            nic_debug["network_ref"] = network_ref

            if not network_ref:
                raise ValueError(f"Network '{nic['network_id']}' was not found")

            vif_record = {
                "device": nic_slot_to_device(nic.get("slot"), idx),
                "network": network_ref,
                "VM": new_vm,
                "MAC": nic.get("mac") or "",
                "MTU": "1500",
                "qos_algorithm_type": "",
                "qos_algorithm_params": {},
                "other_config": {},
                "currently_attached": False,
            }
            nic_debug["vif_record"] = vif_record

            nic_debug["vif_create_result"] = self.conn.request(
                "POST",
                "VIF.create",
                [self.conn.session, vif_record]
            )

            debug["created_networks"].append(nic_debug)

        if stype == "iso":
            iso_storage_id = source.get("storage_id")
            iso_path = source.get("path")

            if not iso_storage_id or not iso_path:
                raise ValueError("ISO requires storage_id and path")

            debug["iso_storage_id"] = iso_storage_id
            debug["iso_path"] = iso_path

            iso_sr_ref = self.conn.get_xapi_obj_ref("SR", str(iso_storage_id))
            debug["iso_sr_ref"] = iso_sr_ref

            if not iso_sr_ref:
                raise ValueError(f"ISO storage '{iso_storage_id}' was not found")

            all_vdis = self.conn.request(
                "POST",
                "VDI.get_all_records",
                [self.conn.session]
            )
            debug["all_vdis_raw"] = all_vdis

            if isinstance(all_vdis, dict) and "Value" in all_vdis:
                all_vdis = all_vdis["Value"]

            iso_vdi_ref = None
            for ref, rec in all_vdis.items():
                if rec.get("SR") == iso_sr_ref and rec.get("name_label") == iso_path:
                    iso_vdi_ref = ref
                    break

            debug["iso_vdi_ref"] = iso_vdi_ref

            if not iso_vdi_ref:
                raise ValueError(f"ISO '{iso_path}' not found in SR '{iso_storage_id}'")

            iso_vbd_record = {
                "VM": new_vm,
                "VDI": iso_vdi_ref,
                "userdevice": "3",
                "bootable": True,
                "mode": "RO",
                "type": "CD",
                "unpluggable": True,
                "empty": False,
                "other_config": {},
                "qos_algorithm_type": "",
                "qos_algorithm_params": {},
            }
            debug["iso_vbd_record"] = iso_vbd_record

            debug["iso_vbd_create_result"] = self.conn.request(
                "POST",
                "VBD.create",
                [self.conn.session, iso_vbd_record]
            )

            debug["set_boot_policy"] = self.conn.request(
                "POST",
                "VM.set_HVM_boot_policy",
                [self.conn.session, new_vm, "BIOS order"]
            )
            debug["set_boot_params"] = self.conn.request(
                "POST",
                "VM.set_HVM_boot_params",
                [self.conn.session, new_vm, {"order": "dc"}]
            )

        if config_data.get("options", {}).get("autostart"):
            debug["set_other_config"] = self.conn.request(
                "POST",
                "VM.set_other_config",
                [self.conn.session, new_vm, {"auto_poweron": "true"}]
            )

        if config_data.get("options", {}).get("start_after_create"):
            if host_ref:
                debug["start_result"] = self.conn.request(
                    "POST",
                    "VM.start_on",
                    [self.conn.session, new_vm, host_ref, False, True]
                )
            else:
                debug["start_result"] = self.conn.request(
                    "POST",
                    "VM.start",
                    [self.conn.session, new_vm, False, True]
                )

        vm_uuid = self.conn.request(
            "POST",
            "VM.get_uuid",
            [self.conn.session, new_vm]
        )

        return {
            "success": True,
            "vmid": vm_uuid,
            "data": {},
        }
       

    def destroy_vm(self, node_id: str, vm_id: str) -> None:
        """Smaže virtuální stroj.

        Pokud je VM spuštěná, nejprve provede clean shutdown a následně VM odstraní z Xen prostředí.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.

        Raises:
            Exception: Pokud VM s daným UUID neexistuje.
        """

        vms = self.conn.request(
            "POST",
            "VM.get_all_records",
            [self.conn.session]
        )

        vm_ref = None

        for ref, vm in vms.items():
            if vm["uuid"] == vm_id:
                vm_ref = ref
                break

        if not vm_ref:
            raise Exception(f"VM s UUID '{vm_id}' nebyla nalezena")

        power_state = vms[vm_ref]["power_state"]

        if power_state == "Running":
            self.conn.request(
                "POST",
                "VM.clean_shutdown",
                [self.conn.session, vm_ref]
            )

        self.conn.request(
            "POST",
            "VM.destroy",
            [self.conn.session, vm_ref]
        )

    def get_vm_status(self, node_id: str, vm_id: str, params: dict) -> dict:
        """Vrátí aktuální stav a základní resource statistiky virtuálního stroje.

        Kombinuje data z:

        - VM recordu
        - guest metrics
        - Xen RRD metrik
        - připojených disků

        Args:
            node_id: Identifikátor uzlu.
            vm_id: UUID virtuálního stroje.
            params: Seznam požadovaných metrik.

        Returns:
            Slovník obsahující pouze vyžádané metriky.
        """

        vms = self.conn.request(
            "POST",
            "VM.get_all_records",
            [self.conn.session]
        )

        for vm_ref, vm in vms.items():
            if not vm.get("is_a_template"):
                continue

        params_set = set(params)
        rrd_required = {
            "cpu_usage", 
            "memory_total", 
            "memory_used", 
            "memory_free"
        }

        vm_ref, vm = self._get_vm(vm_id)

        metrics_guest = {}
        rrd_metrics = {}

        total = 0
        used = 0

        if params_set & {"sysname", "kernel"}:

            metrics_ref = vm.get("guest_metrics")

            if metrics_ref and metrics_ref != "OpaqueRef:NULL":
                metrics_guest = self.conn.request(
                    "POST",
                    "VM_guest_metrics.get_record",
                    [self.conn.session, metrics_ref]
                )

        if {"cpu_num"} & params_set:
            cpu_count = int(vm.get("VCPUs_max") or vm.get("VCPUs_at_startup") or 0)
        else:
            cpu_count = None
        
        if params_set & rrd_required:
            
            rrd_metrics = self.get_vm_time_metrics(
                node_id=node_id,
                vm_id=vm_id,
                params={
                    "timeframe": "current",
                    "fields": list(params_set & rrd_required)
                }
            )

        if params_set & {"disk_total", "disk_free", "disk_used"}:
            total, used = self._get_vm_disk_total_size(vm_ref)

        uptime_seconds = None

        if "uptime" in params_set:
            metrics_ref_vm = vm.get("metrics")

            if metrics_ref_vm and metrics_ref_vm != "OpaqueRef:NULL":
                vm_metrics = self.conn.request(
                    "POST",
                    "VM_metrics.get_record",
                    [self.conn.session, metrics_ref_vm]
                )

                target  = vm_metrics.get("start_time")
                target = datetime.strptime(target, "%Y%m%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)

                uptime_seconds = int((now - target).total_seconds())

        values = {
            "uptime": uptime_seconds,
            "cpu_usage": float(rrd_metrics.get('cpu_usage', 0)),
            "cpu_num": cpu_count,

            "memory_total": rrd_metrics.get('memory_total', None),
            "memory_free": rrd_metrics.get('memory_free', None),
            "memory_used": rrd_metrics.get('memory_used', None),

            "disk_total": total,
            "disk_used": used,
            "disk_free": total - used,

            "sysname": metrics_guest.get("os_version", {}).get("name", None),
            "kernel": metrics_guest.get("os_version", {}).get("uname", None),
        }

        return {k: v for k, v in values.items() if k in params_set}
    
    def get_vm_time_metrics(self, node_id: str, vm_id: str, params: dict) -> list[dict]:
        """Vrátí časovou řadu výkonových metrik virtuálního stroje.

        Metriky jsou načítány z Xen RRD endpointu a převáděny do interního
        formátu používaného aplikací.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            params:
                - timeframe: časový interval
                - fields: seznam požadovaných metrik

        Returns:
            Seznam časových bodů nebo poslední bod pro interval `current`.
        """

        timeframe = params.get("timeframe", "hour")
        fields = params.get("fields", [])

        request_params = {
            "start": str(int(time.time()) - self.conn.TIMEFRAME_TO_SECONDS[timeframe]),
            "cf": "AVERAGE",
            "host": "false",
            "vm_uuid": vm_id,
        }

        r = requests.get(
            f"https://{self.conn.host}/rrd_updates",
            cookies={"session_id": self.conn.session},
            verify=False,
            headers={**self.conn.headers, "Accept": "application/json"},
            params=request_params,
        )

        r.raise_for_status()
        data = r.json()

        legends = data["meta"]["legend"]
        rows = data["data"]

        metric_map = {
            "cpu_usage": {
                "patterns": ["cpu_usage"],
                "type": "single",
            },
            "net_in": {
                "patterns": ["vif_", "_rx"],
                "type": "multi",
            },
            "net_out": {
                "patterns": ["vif_", "_tx"],
                "type": "multi",
            },
            "memory_used": {
                "patterns": ["memory", "memory_internal_free"],
                "type": "memory",
            },
            "memory_total": {
                "patterns": ["memory"],
                "type": "single",
            },
            "memory_free": {
                "patterns": ["memory_internal_free"],
                "type": "single",
            },
            "disk_read": {
                "patterns": ["io_throughput_read"],
                "type": "single",
            },
            "disk_write": {
                "patterns": ["io_throughput_write"],
                "type": "single",
            },
        }

        for metric in fields:
            if metric not in metric_map:
                continue

            config = metric_map[metric]
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

            elif metric_type == "multi":
                found_indexes = []

                for i, legend in enumerate(legends):
                    legend_last = legend.split(":")[-1]

                    if patterns[0] in legend_last and patterns[1] in legend_last:
                        found_indexes.append(i)

                config["indexes"] = found_indexes

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
            point = {"time": ts}

            for field in fields:
                metric_conf = metric_map.get(field)
                if not metric_conf:
                    point[field] = None
                    continue

                metric_type = metric_conf.get("type")
                metric_index = metric_conf.get("indexes")

                if metric_type == "memory":
                    if not isinstance(metric_index, dict):
                        point[field] = None
                        continue

                    total_idx = metric_index.get("total")
                    free_idx = metric_index.get("free")

                    mem_total = values[total_idx] if total_idx is not None and total_idx < len(values) else None
                    mem_free = values[free_idx] if free_idx is not None and free_idx < len(values) else None

                    if mem_total is None or mem_free is None:
                        point[field] = None
                        continue

                    mem_total = float(mem_total)
                    mem_free = float(mem_free)

                    used = mem_total - (mem_free * 1024)
                    point[field] = used if used >= 0 else 0

                elif metric_type == "multi":
                    if not isinstance(metric_index, list):
                        point[field] = None
                        continue

                    total = 0.0
                    found = False

                    for idx in metric_index:
                        if idx is None or idx >= len(values):
                            continue

                        value = values[idx]
                        if value is not None:
                            total += float(value)
                            found = True

                    point[field] = total if found else None

                else:
                    idx = metric_index
                    if idx is None or idx >= len(values):
                        point[field] = None
                        continue

                    value = values[idx]
                    if value is None:
                        point[field] = None
                        continue

                    if field == "memory_free":
                        point[field] = float(value) * 1024  # KiB -> Bytes
                    else:
                        point[field] = float(value)

            result.append(point)

        result.sort(key=lambda x: x["time"])

        if timeframe == "current":
            return result[-1] if result else {}

        return result

    def set_vm_status(self, node_id: str, vm_id: str, status: str) -> dict:
        """Změní stav virtuálního stroje.

        Podporované operace: `start`, `stop`, `shutdown`, `suspend`, `reset`, `reboot`, `resume`


        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            status: Cílová akce nad stavem VM.

        Returns:
            Výsledek volání Xen API.
        """

        vm_ref = self._get_vm(vm_id, True)

        action_map = {
            "start": "VM.start",
            "stop": "VM.hard_shutdown",
            "shutdown": "VM.clean_shutdown",
            "suspend": "VM.suspend",
            "resume": "VM.resume",
            "reboot": "VM.clean_reboot",
            "reset": "VM.hard_reboot",
        }


        if status == "start":
            return self.conn.request(
                "POST",
                action_map[status],
                [self.conn.session, vm_ref, False, True]
            )

        if status == "resume":
            return self.conn.request(
                "POST",
                action_map[status],
                [self.conn.session, vm_ref, False, True],
                300
            )
        else:
            result = self.conn.request(
                "POST",
                action_map[status],
                [self.conn.session, vm_ref]
            )


        return {
            "success": True,
            "task_id": None,
            "data": result,
        }

    def manage_vm_snapshots(
        self,
        node_id: str,
        vm_id: str,
        snap_data: dict | None = None,
    ) -> dict | list[dict]:
        """Vytvoří snapshot nebo vrátí seznam snapshotů virtuálního stroje.

        Pokud jsou předány `snap_data`, metoda vytvoří nový snapshot.
        Jinak vrací seznam existujících snapshotů.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            snap_data: Parametry pro vytvoření snapshotu.

        Returns:
            Metadata nového snapshotu nebo seznam snapshotů VM.

        Raises:
            ValueError: Pokud při vytváření snapshotu chybí jeho jméno.
        """
        vm_ref, vm_main_record = self._get_vm(vm_id)

        # CREATE SNAPSHOT
        if snap_data:
            snapshotname = snap_data.get("snapshotname") or snap_data.get("snapname") or snap_data.get("name")
            description = snap_data.get("description")
            vm_state = snap_data.get("vm_state", snap_data.get("vmstate", 0))

            if not snapshotname:
                raise ValueError("Snapshot name is required")

            method = "VM.checkpoint" if bool(vm_state) else "VM.snapshot"

            snap_ref = self.conn.request(
                "POST",
                method,
                [self.conn.session, vm_ref, snapshotname],
                300
            )

            if description:
                self.conn.request(
                    "POST",
                    "VM.set_name_description",
                    [self.conn.session, snap_ref, description]
                )

            snap_uuid = self.conn.request(
                "POST",
                "VM.get_uuid",
                [self.conn.session, snap_ref]
            )

            try:
                self.conn.request(
                    "POST",
                    "VM.remove_from_other_config",
                    [self.conn.session, vm_ref, "current_snapshot_uuid"]
                )
            except Exception:
                pass

            self.conn.request(
                "POST",
                "VM.add_to_other_config",
                [self.conn.session, vm_ref, "current_snapshot_uuid", snap_uuid]
            )

            return {
                "id": snap_uuid,
                "snapshot_ref": snap_ref,
                "name": snapshotname,
                "description": description or None,
            }

        # LIST SNAPSHOTS
        all_vms = self.conn.request(
            "POST",
            "VM.get_all_records",
            [self.conn.session]
        ) or {}

        real_snapshots = []

        for ref, snapshot_record in all_vms.items():
            if not snapshot_record.get("is_a_snapshot"):
                continue

            if snapshot_record.get("snapshot_of") != vm_ref:
                continue

            snapshot_time = snapshot_record.get("snapshot_time")

            real_snapshots.append({
                "id": snapshot_record.get("uuid"),
                "name": snapshot_record.get("name_label"),
                "description": snapshot_record.get("name_description"),
                "snaptime": int(
                    datetime.fromisoformat(snapshot_time.replace("Z", "+00:00")).timestamp()
                ) if snapshot_time else None,
                "parent": None,
                "parent_id": None,
                "running": 0,
                "is_current": False,
                "snapshot_ref": ref,
            })

        real_snapshots.sort(key=lambda x: x.get("snaptime") or 0)

        previous = None
        for snapshot in real_snapshots:
            snapshot["parent"] = previous["name"] if previous else None
            snapshot["parent_id"] = previous["id"] if previous else None
            previous = snapshot

        current_snapshot_id = (vm_main_record.get("other_config") or {}).get("current_snapshot_uuid")

        current_base = None
        for snapshot in real_snapshots:
            if snapshot["id"] == current_snapshot_id:
                current_base = snapshot
                break

        if current_base is None and real_snapshots:
            current_base = real_snapshots[-1]

        current_item = {
            "id": "current",
            "name": "current",
            "description": "Current VM state",
            "snaptime": None,
            "parent": current_base["name"] if current_base else None,
            "parent_id": current_base["id"] if current_base else None,
            "running": 1,
            "is_current": True,
        }

        result = [current_item]
        result.extend(real_snapshots)

        return result


    def drop_vm_snapshot(self, node_id: str, vm_id: str, snapshot: str) -> None:
        """Smaže snapshot virtuálního stroje.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            snapshot: UUID snapshotu.

        Raises:
            ValueError: Pokud zadané ID nepatří snapshotu nebo snapshot nepatří dané VM.
        """
        vm_ref = self._get_vm(vm_id, True)
 
        snap_ref = self.conn.request(
            "POST",
            "VM.get_by_uuid",
            [self.conn.session, snapshot]
        )

        snap_record = self.conn.request(
            "POST",
            "VM.get_record",
            [self.conn.session, snap_ref]
        )

        if not snap_record.get("is_a_snapshot"):
            raise ValueError("Given snapshot id is not snapshot.")

        if snap_record.get("snapshot_of") != vm_ref:
            raise ValueError("Snapshot does not belong to this VM")

        snap_record = self.conn.request(
            "POST",
            "VM.destroy",
            [self.conn.session, snap_ref]
        )

    def rollback_vm_snapshot(self, node_id: str, vm_id: str, snapshot: str, auto_start: bool = True) -> None:
        """Provede rollback virtuálního stroje na zadaný snapshot.

        Po rollbacku může podle stavu VM provést automatické spuštění nebo
        resume a současně aktualizuje informaci o current snapshotu.

        Args:
            node_id: Identifikátor uzlu.
            vm_id: UUID virtuálního stroje.
            snapshot: UUID snapshotu.
            auto_start: Pokud je VM po revertu halted, provede automatický start.

        Raises:
            ValueError: Pokud zadané ID nepatří snapshotu nebo snapshot
                nepatří dané VM.
        """

        vm_ref, _ = self._get_vm(vm_id)

        snap_ref = self.conn.request(
            "POST",
            "VM.get_by_uuid",
            [self.conn.session, snapshot]
        )

        snap_record = self.conn.request(
            "POST",
            "VM.get_record",
            [self.conn.session, snap_ref]
        )

        if not snap_record.get("is_a_snapshot"):
            raise ValueError("Given snapshot id is not snapshot.")

        if snap_record.get("snapshot_of") != vm_ref:
            raise ValueError("Snapshot does not belong to this VM")

        self.conn.request(
            "POST",
            "VM.revert",
            [self.conn.session, snap_ref]
        )

        try:
            self.conn.request(
                "POST",
                "VM.remove_from_other_config",
                [self.conn.session, vm_ref, "current_snapshot_uuid"]
            )
        except Exception:
            pass

        try:
            self.conn.request(
                "POST",
                "VM.add_to_other_config",
                [self.conn.session, vm_ref, "current_snapshot_uuid", snapshot]
            )
        except Exception:
            pass

        final_state = None

        try:
            _, vm_record_after = self._get_vm(vm_id)
            power_state = (vm_record_after.get("power_state") or "").lower()

            if power_state == "suspended":
                self.conn.request(
                    "POST",
                    "VM.resume",
                    [self.conn.session, vm_ref, False, False]
                )
                final_state = "running"

            elif power_state == "halted" and auto_start:
                self.conn.request(
                    "POST",
                    "VM.start",
                    [self.conn.session, vm_ref, False, False]
                )
                final_state = "running"

            else:
                final_state = power_state
        
        except Exception:
            pass

    def get_vm_config(self, node_id: str, vm_id: str) -> dict:
        """Vrátí normalizovanou konfiguraci virtuálního stroje.

        Konfigurace je převedena z formátu Xen API do interní struktury
        zahrnující CPU, paměť, disky, CD-ROM mechaniky, sítě, boot nastavení
        a obecné volby.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.

        Returns:
            Normalizovaná konfigurace VM.

        Raises:
            ValueError: Pokud zadané ID patří snapshotu místo běžné VM.
        """
        vm_ref, vm_record = self._get_vm(vm_id)

        if vm_record.get("is_a_snapshot"):
            raise ValueError("Given VM id belongs to snapshot, not regular VM")

        def _safe_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _to_mb(value):
            try:
                return int(value) // (1024 * 1024)
            except (TypeError, ValueError):
                return None

        def _to_gb(value):
            try:
                size = int(value)
                return size // (1024 ** 3)
            except (TypeError, ValueError):
                return None

        def _detect_guest_type(vm: dict) -> str | None:
            os_version = vm.get("os_version") or {}
            name = " ".join(str(v) for v in os_version.values() if v).lower()

            if "windows" in name:
                return "windows"

            if any(x in name for x in [
                "ubuntu", "debian", "centos", "rhel", "red hat",
                "rocky", "alma", "suse", "linux"
            ]):
                return "linux"

            return None

        def _parse_boot_order(order: str) -> list[str]:
            """
            Xen order typicky:
            c = disk
            d = cdrom
            n = net

            Vrátíme proxmox-like sloty.
            """
            if not order:
                return []

            result = []
            mapping = {
                "c": "scsi0",
                "d": "ide0",
                "n": "net0",
            }

            for ch in order:
                mapped = mapping.get(ch)
                if mapped:
                    result.append(mapped)

            return result

        platform = vm_record.get("platform", {}) or {}
        hvm_boot = vm_record.get("HVM_boot_params", {}) or {}
        other_config = vm_record.get("other_config", {}) or {}

        vcpus = _safe_int(vm_record.get("VCPUs_max")) or _safe_int(vm_record.get("VCPUs_at_startup"))
        cores_per_socket = _safe_int(platform.get("cores-per-socket"))

        if vcpus and cores_per_socket and cores_per_socket > 0:
            cpu_cores = cores_per_socket
            cpu_sockets = max(1, vcpus // cores_per_socket)
        else:
            cpu_cores = vcpus
            cpu_sockets = 1 if vcpus else None

        result = {
            "vmid": _safe_int(vm_id) if str(vm_id).isdigit() else vm_id,
            "name": vm_record.get("name_label"),
            "memory_mb": _to_mb(vm_record.get("memory_static_max")),
            "cpu": {
                "cores": cpu_cores,
                "sockets": cpu_sockets,
                "type": "host",
            },
            "guest": _detect_guest_type(vm_record),
            "disks": [],
            "cdroms": [],
            "networks": [],
            "boot": {
                "order": _parse_boot_order(hvm_boot.get("order", "")),
                "firmware": hvm_boot.get("firmware", "default") or "default",
                "machine": "default",
            },
            "options": {
                "autostart": str(other_config.get("auto_poweron", "false")).lower() in ("1", "true", "yes"),
                "start_after_create": False,
                "graphics": platform.get("vga", "default") or "default",
            },
        }

        # DISKS / CDROMS
        disk_index = 0
        cdrom_index = 0

        for vbd_ref in vm_record.get("VBDs", []):
            vbd = self.conn.get_xapi_obj_record("VBD", vbd_ref)

            if not vbd:
                continue

            vbd_type = (vbd.get("type") or "").lower()

            vdi = None
            sr = None
            sr_ref = None

            vdi_ref = vbd.get("VDI")
            if vdi_ref and vdi_ref != "OpaqueRef:NULL":
                vdi = self.conn.get_xapi_obj_record("VDI", vdi_ref)
                if vdi:
                    sr_ref = vdi.get("SR")
                    if sr_ref and sr_ref != "OpaqueRef:NULL":
                        sr = self.conn.get_xapi_obj_record("SR", sr_ref)

            if vbd_type == "cd":
                result["cdroms"].append({
                    "slot": f"ide{cdrom_index}",
                    "storage_id": sr.get("uuid") if sr else None,
                    "storage": sr.get("name_label") if sr else None,
                    "volume": vdi.get("name_label") if vdi else None,
                    "size_gb": None,
                    "controller_type": "ide",
                })
                cdrom_index += 1

            elif vbd_type == "disk":
                result["disks"].append({
                    "slot": f"scsi{disk_index}",
                    "storage_id": sr.get("uuid") if sr else None,
                    "storage": sr.get("name_label") if sr else None,
                    "volume": vdi.get("name_label") if vdi else None,
                    "size_gb": _to_gb(vdi.get("virtual_size")) if vdi else None,
                    "controller_type": "virtio-scsi-single",
                })
                disk_index += 1

        # NETWORKS
        net_index = 0

        for vif_ref in vm_record.get("VIFs", []):
            vif = self.conn.get_xapi_obj_record("VIF", vif_ref)
            if not vif:
                continue

            network_ref = vif.get("network")
            network_rec = self.conn.get_xapi_obj_record("network", network_ref) if network_ref else None

            result["networks"].append({
                "slot": f"net{net_index}",
                "network_id": network_rec.get("bridge") if network_rec else None,
                "model": "virtio",
                "mac": vif.get("MAC"),
                "connected": bool(vif.get("currently_attached")),
            })
            net_index += 1

        return result
    

    def set_vm_config(self, node_id: str, vm_id: str, optional_params: dict) -> dict:
        """Aktualizuje konfiguraci virtuálního stroje.

        Podle typu změn může být před aplikací konfigurace vyžadováno vypnutí VM.
        Metoda podporuje aktualizaci:

        - jména
        - paměti
        - CPU
        - autostartu
        - boot order
        - disků
        - síťových karet
        - CD-ROM mechanik

        Args:
            node_id: Identifikátor uzlu.
            vm_id: UUID virtuálního stroje.
            optional_params: Parametry konfigurace, které mají být změněny.

        Returns:
            Slovník s informací o tom, zda bylo nutné VM vypnout a zda běžela.
        """

        vm_ref, vm_record = self._get_vm(vm_id)
        current_config = self.get_vm_config(node_id, vm_id)

        power_state = (vm_record.get("power_state") or "").lower()
        was_running = power_state == "running"

        requested_cpu = optional_params.get("cpu", {}) or {}
        current_cpu = current_config.get("cpu", {}) or {}

        options = optional_params.get("options", {}) or {}
        current_options = current_config.get("options", {}) or {}

        boot = optional_params.get("boot", {}) or {}
        current_boot = current_config.get("boot", {}) or {}

        changes = {
            "name": "name" in optional_params and optional_params.get("name") != current_config.get("name"),
            "memory_mb": (
                "memory_mb" in optional_params
                and int(optional_params.get("memory_mb") or 0) != int(current_config.get("memory_mb") or 0)
            ),
             "cpu": (
                "cpu" in optional_params
                and (
                    int(requested_cpu.get("cores") or 1) != int(current_cpu.get("cores") or 1)
                    or int(requested_cpu.get("sockets") or 1) != int(current_cpu.get("sockets") or 1)
                )
            ),
            "autostart": "autostart" in options and options.get("autostart") != current_options.get("autostart"),
            "boot": "order" in boot and boot.get("order") != current_boot.get("order"),
            "disks": "disks" in optional_params and (optional_params.get("disks") or []) != (current_config.get("disks") or []),
            "networks": "networks" in optional_params and (optional_params.get("networks") or []) != (current_config.get("networks") or []),
            "cdroms": "cdroms" in optional_params and (optional_params.get("cdroms") or []) != (current_config.get("cdroms") or []),
        }

        if not any(changes.values()):
            return {
                "success": True,
                "changed": False,
                "changed_fields": [],
                "required_action": "none",
                "was_running": was_running,
            }

        requires_shutdown = any([
            changes["memory_mb"],
            changes["cpu"],
            changes["boot"],
            changes["disks"],
            changes["cdroms"],
        ])

        if requires_shutdown and was_running:
            print("STOPPING VM")
            self.set_vm_status(node_id, vm_id, "stop")
            time.sleep(1)
            vm_ref, vm_record = self._get_vm(vm_id)

        # 1) NAME
        if changes["name"]:
            print("UPDATING NAME")
            self.conn.request(
                "POST",
                "VM.set_name_label",
                [self.conn.session, vm_ref, optional_params["name"]]
            )

        # 2) MEMORY
        if changes["memory_mb"]:
            print("UPDATING MEMORY")
            memory_bytes = int(optional_params["memory_mb"]) * 1024 * 1024

            self.conn.request(
                "POST",
                "VM.set_memory",
                [self.conn.session, vm_ref, str(memory_bytes)]
            )

        # 3) CPU
        if changes["cpu"]:
            print("UPDATING CPU")

            cpu = optional_params.get("cpu", {}) or {}
            cores = int(cpu.get("cores") or 1)
            sockets = int(cpu.get("sockets") or 1)
            vcpus = cores * sockets

            current_vcpus_max = int(vm_record.get("VCPUs_max") or 0)
            current_vcpus_startup = int(vm_record.get("VCPUs_at_startup") or 0)

            print("CURRENT VCPUS MAX:", current_vcpus_max)
            print("CURRENT VCPUS STARTUP:", current_vcpus_startup)
            print("NEW VCPUS:", vcpus)

            if vcpus < current_vcpus_max:
                print("CPU DOWN: startup first")
                self.conn.request(
                    "POST",
                    "VM.set_VCPUs_at_startup",
                    [self.conn.session, vm_ref, str(vcpus)]
                )
                self.conn.request(
                    "POST",
                    "VM.set_VCPUs_max",
                    [self.conn.session, vm_ref, str(vcpus)]
                )

            elif vcpus > current_vcpus_max:
                print("CPU UP: max first")
                self.conn.request(
                    "POST",
                    "VM.set_VCPUs_max",
                    [self.conn.session, vm_ref, str(vcpus)]
                )
                self.conn.request(
                    "POST",
                    "VM.set_VCPUs_at_startup",
                    [self.conn.session, vm_ref, str(vcpus)]
                )

            platform = dict(vm_record.get("platform", {}) or {})

            if platform.get("cores-per-socket") != str(cores):
                print("UPDATING CORES PER SOCKET")
                platform["cores-per-socket"] = str(cores)

                self.conn.request(
                    "POST",
                    "VM.set_platform",
                    [self.conn.session, vm_ref, platform]
                )

        # 5) BOOT ORDER
        if changes["boot"]:
            print("UPDATING BOOT ORDER")

            boot_mapping = {
                "scsi0": "c",
                "ide0": "d",
                "net0": "n",
            }

            boot_order = ""
            for item in boot.get("order") or []:
                value = boot_mapping.get(item)
                if value and value not in boot_order:
                    boot_order += value

            hvm_boot = dict(vm_record.get("HVM_boot_params", {}) or {})
            hvm_boot["order"] = boot_order

            self.conn.request(
                "POST",
                "VM.set_HVM_boot_params",
                [self.conn.session, vm_ref, hvm_boot]
            )

        # 6) DISKS
        if changes["disks"]:
            print("UPDATING DISKS")

            for disk in optional_params.get("disks", []) or []:
                slot = disk.get("slot")
                if not slot:
                    continue

                userdevice = "".join(ch for ch in str(slot) if ch.isdigit())
                if not userdevice:
                    raise ValueError(f"Invalid disk slot '{slot}'")

                vbd_ref = None
                vbd = None

                for existing_vbd_ref in vm_record.get("VBDs", []):
                    existing_vbd = self.conn.request(
                        "POST",
                        "VBD.get_record",
                        [self.conn.session, existing_vbd_ref]
                    )

                    if not existing_vbd:
                        continue

                    if (
                        str(existing_vbd.get("userdevice")) == str(userdevice)
                        and (existing_vbd.get("type") or "").lower() == "disk"
                    ):
                        vbd_ref = existing_vbd_ref
                        vbd = existing_vbd
                        break

                if vbd:
                    if disk.get("size_gb") is None:
                        continue

                    vdi_ref = vbd.get("VDI")
                    if not vdi_ref or vdi_ref == "OpaqueRef:NULL":
                        continue

                    vdi = self.conn.request(
                        "POST",
                        "VDI.get_record",
                        [self.conn.session, vdi_ref]
                    )

                    old_size_bytes = int(vdi.get("virtual_size") or 0)
                    new_size_bytes = int(disk["size_gb"]) * 1024 * 1024 * 1024

                    if new_size_bytes > old_size_bytes:
                        self.conn.request(
                            "POST",
                            "VDI.resize",
                            [self.conn.session, vdi_ref, str(new_size_bytes)]
                        )

                    continue

                storage_id = disk.get("storage_id")
                size_gb = disk.get("size_gb")

                if not storage_id:
                    raise ValueError(f"New disk '{slot}' requires storage_id")

                if size_gb is None:
                    raise ValueError(f"New disk '{slot}' requires size_gb")

                sr_ref = self.conn.get_xapi_obj_ref("SR", storage_id)
                if not sr_ref:
                    raise ValueError(f"Storage '{storage_id}' not found")

                vdi_ref = self.conn.request(
                    "POST",
                    "VDI.create",
                    [self.conn.session, {
                        "name_label": disk.get("volume") or f"{vm_record.get('name_label')}-{slot}",
                        "name_description": "",
                        "SR": sr_ref,
                        "virtual_size": str(int(size_gb) * 1024 * 1024 * 1024),
                        "type": "user",
                        "sharable": False,
                        "read_only": False,
                        "other_config": {},
                        "sm_config": {},
                        "xenstore_data": {},
                        "tags": [],
                    }]
                )

                self.conn.request(
                    "POST",
                    "VBD.create",
                    [self.conn.session, {
                        "VM": vm_ref,
                        "VDI": vdi_ref,
                        "userdevice": userdevice,
                        "bootable": False,
                        "mode": "RW",
                        "type": "Disk",
                        "unpluggable": True,
                        "empty": False,
                        "other_config": {},
                        "qos_algorithm_type": "",
                        "qos_algorithm_params": {},
                    }]
                )

        # 7) NETWORKS
        if changes["networks"]:
            print("UPDATING NETWORKS")

            for nic in optional_params.get("networks", []) or []:
                slot = nic.get("slot")
                if not slot:
                    continue

                userdevice = "".join(ch for ch in str(slot) if ch.isdigit())
                if not userdevice:
                    raise ValueError(f"Invalid network slot '{slot}'")

                existing_vif_ref = None

                for vif_ref in vm_record.get("VIFs", []):
                    vif = self.conn.request(
                        "POST",
                        "VIF.get_record",
                        [self.conn.session, vif_ref]
                    )

                    if not vif:
                        continue

                    if str(vif.get("device")) == str(userdevice):
                        existing_vif_ref = vif_ref
                        break

                if existing_vif_ref:
                    continue

                network_id = nic.get("network_id")
                if not network_id:
                    raise ValueError(f"Network '{slot}' requires network_id")

                networks = self.conn.request(
                    "POST",
                    "network.get_all_records",
                    [self.conn.session]
                )

                network_ref = None
                for ref, network in networks.items():
                    if network.get("bridge") == network_id:
                        network_ref = ref
                        break

                if not network_ref:
                    raise ValueError(f"Network '{network_id}' not found")

                self.conn.request(
                    "POST",
                    "VIF.create",
                    [self.conn.session, {
                        "device": userdevice,
                        "network": network_ref,
                        "VM": vm_ref,
                        "MAC": nic.get("mac") or "",
                        "MTU": "1500",
                        "qos_algorithm_type": "",
                        "qos_algorithm_params": {},
                        "other_config": {},
                        "currently_attached": False,
                    }]
                )

        # 8) CDROMS
        if changes["cdroms"]:
            print("UPDATING CDROMS")

            requested_cdroms = optional_params.get("cdroms", []) or []
            requested_cdrom_slots = {
                cdrom.get("slot")
                for cdrom in requested_cdroms
                if cdrom.get("slot")
            }

            for existing_vbd_ref in vm_record.get("VBDs", []):
                existing_vbd = self.conn.request(
                    "POST",
                    "VBD.get_record",
                    [self.conn.session, existing_vbd_ref]
                )

                if not existing_vbd:
                    continue

                if (existing_vbd.get("type") or "").lower() != "cd":
                    continue

                userdevice = str(existing_vbd.get("userdevice") or "")
                existing_slot = f"ide{userdevice}"

                if existing_slot not in requested_cdrom_slots:
                    print(f"REMOVING CDROM {existing_slot}")

                    self.conn.request(
                        "POST",
                        "VBD.destroy",
                        [self.conn.session, existing_vbd_ref]
                    )

            vm_ref, vm_record = self._get_vm(vm_id)

            for cdrom in optional_params.get("cdroms", []) or []:
                slot = cdrom.get("slot")
                if not slot:
                    continue

                userdevice = "".join(ch for ch in str(slot) if ch.isdigit())
                if not userdevice:
                    raise ValueError(f"Invalid CD-ROM slot '{slot}'")

                existing_cdrom = None

                for existing_vbd_ref in vm_record.get("VBDs", []):
                    existing_vbd = self.conn.request(
                        "POST",
                        "VBD.get_record",
                        [self.conn.session, existing_vbd_ref]
                    )

                    if not existing_vbd:
                        continue

                    if (
                        str(existing_vbd.get("userdevice")) == str(userdevice)
                        and (existing_vbd.get("type") or "").lower() == "cd"
                    ):
                        existing_cdrom = existing_vbd
                        break

                if existing_cdrom:
                    continue

                storage_id = cdrom.get("storage_id")
                source = cdrom.get("volume") or cdrom.get("path")

                if not storage_id:
                    raise ValueError(f"CD-ROM '{slot}' requires storage_id")

                if not source:
                    raise ValueError(f"CD-ROM '{slot}' requires volume or path")

                sr_ref = self.conn.get_xapi_obj_ref("SR", storage_id)
                if not sr_ref:
                    raise ValueError(f"Storage '{storage_id}' not found")

                all_vdis = self.conn.request(
                    "POST",
                    "VDI.get_all_records",
                    [self.conn.session]
                )

                iso_vdi_ref = None

                for vdi_ref, vdi in all_vdis.items():
                    if vdi.get("SR") != sr_ref:
                        continue

                    name_label = vdi.get("name_label") or ""
                    location = vdi.get("location") or ""

                    if source == name_label or source == location:
                        iso_vdi_ref = vdi_ref
                        break

                if not iso_vdi_ref:
                    raise ValueError(f"ISO '{source}' not found in storage '{storage_id}'")

                self.conn.request(
                    "POST",
                    "VBD.create",
                    [self.conn.session, {
                        "VM": vm_ref,
                        "VDI": iso_vdi_ref,
                        "userdevice": userdevice,
                        "bootable": True,
                        "mode": "RO",
                        "type": "CD",
                        "unpluggable": True,
                        "empty": False,
                        "other_config": {},
                        "qos_algorithm_type": "",
                        "qos_algorithm_params": {},
                    }]
                )

        return {
            "success": True,
            "required_action": "shutdown" if requires_shutdown else "none",
            "was_running": was_running,
        }
    
    def get_vm_backups(self, node_id: str, vm_id: str) -> list[dict]:
        """Vrátí seznam dostupných filesystemových záloh pro zadanou VM.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.

        Returns:
            Seznam záloh nalezených v backup struktuře pro Xen.
        """
        return self._get_fs_vm_backups(vm_id, "xen")

    def create_vm_backup(self, node_id: str, vm_id: str, backup_root: str) -> None:
        """Vytvoří zálohu virtuálního stroje.

        Pokud VM běží, vytvoří snapshot a exportuje snapshot.
        Pokud je VM zastavená nebo suspendovaná, exportuje přímo VM.

        Args:
            node_id: Identifikátor uzlu.
            vm_id: UUID virtuálního stroje.
            backup_root: Kořenový adresář pro ukládání záloh.

        Returns:
            Metadata o vytvořené záloze.

        Raises:
            ValueError: Pokud jde o control domain nebo template VM.
            Exception: Pokud je VM v nepodporovaném power state.
        """
        vm_ref, vm = self._get_vm(vm_id)

        backup_root = os.path.join(backup_root, "xen", vm_id)

        if vm.get("is_control_domain"):
            raise ValueError("Cannot operate on control domain VM")

        if vm.get("is_a_template"):
            raise ValueError("Cannot operate on template VM")

        vm_uuid = vm.get("uuid")
        vm_name = vm.get("name_label") or vm_uuid
        power_state = (vm.get("power_state") or "").lower()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        base_dir = backup_root
        os.makedirs(base_dir, exist_ok=True)

        compression = False
        metadata_only = False

        snapshot_ref = None
        export_uuid = vm_uuid
        mode = "offline_export"

        try:
            if power_state == "running":
                print("Running VM -> creating snapshot")

                snapshot_name = f"{vm_name}-backup-{timestamp}"
                snapshot_res = self.manage_vm_snapshots(
                    node_id,
                    vm_id,
                    {
                        "snapshotname": snapshot_name,
                        "description": "live backup",
                        "vm_state": 0,  # snapshot
                    }
                )

                snapshot_ref = snapshot_res["snapshot_ref"]

                export_uuid = self.conn.request(
                    "POST",
                    "VM.get_record",
                    [self.conn.session, snapshot_ref]
                )["uuid"]

                mode = "live_snapshot_export"
                print("Snapshot created:", snapshot_ref)
                print("Snapshot UUID:", export_uuid)

            elif power_state in ["halted", "suspended"]:
                print("Offline VM -> direct export")
                export_uuid = vm_uuid
                mode = "offline_export"

            else:
                raise Exception(f"Nepodporovaný power state pro backup: {power_state}")

            extension = "meta" if metadata_only else "xva"
            destination = os.path.join(base_dir, f"{export_uuid}_{timestamp}.{extension}")

            task_ref = self.conn.request(
                "POST",
                "task.create",
                [self.conn.session, f"Export {vm_name}", f"Export VM {export_uuid}"]
            )

            endpoint = "export_metadata" if metadata_only else "export"
            url = f"https://{self.conn.host}/{endpoint}"

            params = {
                "session_id": self.conn.session,
                "task_id": task_ref,
                "uuid": export_uuid,
            }

            if not metadata_only:
                params["use_compression"] = "true" if compression else "false"

            print("Export params:", params)

            try:
                with requests.get(
                    url,
                    params=params,
                    stream=True,
                    verify=False,
                    timeout=300,
                    allow_redirects=True
                ) as response:
                    
                    response.raise_for_status()

                    with open(destination, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)

            except requests.exceptions.HTTPError as e:
                print("Response body:", e.response.text)
                raise ConnectionError(
                    f"HTTP error {e.response.status_code} for {url}"
                ) from e

            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"Connection failed: {str(e)}") from e

        finally:
            if snapshot_ref:
                try:
                    self.conn.request(
                        "VM.destroy",
                        [self.conn.session, snapshot_ref]
                    )
                    print("Snapshot deleted:", snapshot_ref)
                except Exception as e:
                    print(f"Snapshot cleanup failed: {e}")
    
    def get_vm_logs(
        self,
        node_id: str,
        vm_id: str,
        limit: int = 1000,
    ) -> dict:
        """Vrátí logy související s virtuálním strojem ze syslog souboru.

        Metoda čte syslog odzadu a filtruje pouze řádky obsahující `vm_id`.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            limit: Maximální počet vrácených log řádků. Hodnota 0 znamená bez limitu.

        Returns:
            Slovník s počtem řádků a seznamem normalizovaných log záznamů.

        Raises:
            ValueError: Pokud chybí `vm_id` nebo je `limit` záporný.
            FileNotFoundError: Pokud neexistuje syslog soubor.
        """

        if not vm_id:
            raise ValueError("vm_id is required")

        if limit < 0:
            raise ValueError("limit must be >= 0")

        syslog_path = os.path.join(LOG_ROOT, self.conn.host, "syslog.log")

        if not os.path.isfile(syslog_path):
            raise FileNotFoundError(f"Syslog file '{syslog_path}' not found")

        matched_lines = []

        with open(syslog_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            buffer = b""

            while pos > 0 and (limit == 0 or len(matched_lines) < limit):
                read_size = min(4096, pos)
                pos -= read_size
                f.seek(pos)

                chunk = f.read(read_size)
                buffer = chunk + buffer

                lines = buffer.split(b"\n")
                buffer = lines[0]

                for raw_line in reversed(lines[1:]):
                    line = raw_line.decode("utf-8", errors="replace")
                    if vm_id in line:
                        matched_lines.append(line)
                        if limit > 0 and len(matched_lines) >= limit:
                            break

            if buffer and (limit == 0 or len(matched_lines) < limit):
                line = buffer.decode("utf-8", errors="replace")
                if vm_id in line:
                    matched_lines.append(line)

        matched_lines.reverse()

        normalized_lines = [
            {
                "upid": None,
                "type": "syslog",
                "starttime": None,
                "status": None,
                "line_no": index + 1,
                "text": line,
            }
            for index, line in enumerate(matched_lines)
        ]

        return {
            "lines_count": len(normalized_lines),
            "lines": normalized_lines,
        }
    
    def open_console(self, node_id: str, vm_id: str, protocol: str = "vnc") -> dict:
        """Otevře konzolové připojení k virtuálnímu stroji.

        Aktuálně je podporována VNC konzole nad Xen RFB konzolí.

        Args:
            node_id: UUID uzlu.
            vm_id: UUID virtuálního stroje.
            protocol: Typ protokolu konzole. Aktuálně očekáváno `vnc`.

        Returns:
            Informace potřebné pro připojení ke konzoli.

        Raises:
            HTTPException: Pokud VM nemá dostupnou konzoli nebo není dovoleno na ní operovat.
        """

        vm_ref, vm = self._get_vm(vm_id)

        if vm.get("is_control_domain"):
            raise HTTPException(
                status_code=400,
                detail="Operation not allowed on control domain VM"
            )

        console_refs = self.conn.request(
            "POST",
            "VM.get_consoles",
            [self.conn.session, vm_ref]
        )

        if not console_refs:
            raise HTTPException(
                status_code=404,
                detail="VNC console not found"
            )

        vnc_console = None

        for console_ref in console_refs:
            console = self.conn.request(
                "POST",
                "console.get_record",
                [self.conn.session, console_ref]
            )

            if (console.get("protocol") or "").upper() == "RFB":
                vnc_console = console
                break

        if not vnc_console:
            raise HTTPException(
                status_code=404,
                detail="VNC console location not found"
            )
        
        location = vnc_console.get("location")
        if not location:
            raise HTTPException(
                status_code=404,
                detail="Console references not found"
            )

        parsed = urlparse(location)
        query = parse_qs(parsed.query)

        port = None
        if "port" in query and query["port"]:
            try:
                port = int(query["port"][0])
            except (TypeError, ValueError):
                port = None


        ws_url = location
        if ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[len("https://"):]
        elif ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[len("http://"):]

        return {
            "protocol": "vnc",
            "port": port,
            "ticket": self.conn.session,  
            "ws_url": ws_url,
        }
    
    def _get_node(self, node):
        """Vrátí Xen host reference a kompletní host record.

        Args:
            node: UUID nebo identifikátor uzlu.

        Returns:
            Dvojice `(host_ref, host_record)`.
        """

        host_ref = vm_ref = self.conn.get_xapi_obj_ref("host", node)

        host = self.conn.get_xapi_obj_record("host", host_ref)

        return host_ref, host
    
    def _is_vm_resident_on_node(self, node_id: str, vm_uuid: str) -> bool:
        """Ověří, zda je VM rezidentní na zadaném uzlu.

        Args:
            node: UUID uzlu.
            vm_uuid: UUID virtuálního stroje.

        Returns:
            `True`, pokud je VM resident na daném uzlu, jinak `False`.
        """
        host_ref, host = self._get_node(node_id)

        resident_vms = host.get("resident_VMs", [])

        for vm_ref in resident_vms:
            current_uuid = self.conn.request(
                "POST",
                "VM.get_uuid",
                [self.conn.session, vm_ref]
            )
            if current_uuid == vm_uuid:
                return True

        return False
    
    def _get_vm(self, vmid: str, ref=False):
        """Vrátí Xen VM reference nebo kompletní VM record.

        Args:
            vmid: UUID virtuálního stroje.
            ref: Pokud je `True`, vrací pouze Xen reference VM.

        Returns:
            Xen reference VM nebo dvojice `(vm_ref, vm_record)`.

        Raises:
            HTTPException: Pokud jde o control domain nebo template VM.
        """
        vm_ref = self.conn.get_xapi_obj_ref("VM",vmid)

        if ref:
            return vm_ref

        vm = self.conn.get_xapi_obj_record("VM", vm_ref)

        if vm.get("is_control_domain"):
            raise HTTPException(status_code=400, detail="Operation not allowed on control domain VM")

        if vm.get("is_a_template"):
            raise HTTPException(status_code=400, detail="Operation not allowed on template VM")

        return vm_ref, vm

    def _get_vm_disk_total_size(self, vm_ref: str) -> tuple[int, int]:
        """Spočítá agregovanou velikost disků VM.

        Projde všechna VBD zařízení typu `Disk`, načte navázané VDI záznamy
        a sečte jejich virtuální velikost a fyzickou utilizaci.

        Args:
            vm_ref: Xen reference virtuálního stroje.

        Returns:
            Dvojice `(total_size, used_size)` v bajtech.
        """

        vbd_refs = self.conn.request(
            "POST",
            "VM.get_VBDs",
            [self.conn.session, vm_ref]
        )

        total_size = 0
        used_size = 0

        for vbd_ref in vbd_refs:
            vbd_rec = self.conn.request(
                "POST",
                "VBD.get_record",
                [self.conn.session, vbd_ref]
            )

            if not vbd_rec:
                continue

            if vbd_rec.get("type") != "Disk":
                continue

            if not vbd_rec.get("currently_attached", False) and vbd_rec.get("VDI") == "OpaqueRef:NULL":
                continue

            vdi_ref = vbd_rec.get("VDI")
            if not vdi_ref or vdi_ref == "OpaqueRef:NULL":
                continue

            vdi_rec = self.conn.request(
                "POST",
                "VDI.get_record",
                [self.conn.session, vdi_ref]
            )

            total_size += int(vdi_rec.get("virtual_size") or 0)
            used_size += int(vdi_rec.get("physical_utilisation") or 0)

        return total_size, used_size
    
    

    def get_vm_capabilities(self):
        return {
            "source_types": ["template", "iso", "backup"],

            "guest": {
                "types": ["linux24", "linux", "windows-modern", "windows-latest", "other32", "other64"],
                "default": "other64",
            },

            "disk": {
                "buses": ["scsi"],
                "controllers": ["default"],
                "default_bus": "scsi",
                "default_controller": "default",
            },

            "network": {
                "models": ["default"],
                "default_model": "default",
            },

            "boot": {
                "firmware": ["default"],
                "machines": ["default"],
                "secure_boot": False,
            },

            "graphics": {
                "models": ["default"],
                "default": "default",
            },

            "options": {
                "start_after_create": True
            },
        }
    