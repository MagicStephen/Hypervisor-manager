from platforms.base.vm import BaseVmApi
import libvirt
from xml.dom import minidom
from xml.sax.saxutils import escape
from datetime import datetime
import xml.etree.ElementTree as ET
import uuid
import os
import socket
import subprocess
import re
from config import LOG_ROOT, BACKUP_ROOT

class KvmVmApi(BaseVmApi):
    """Implementace API vrstvy pro správu virtuálních strojů přes libvirt/KVM.

    Třída poskytuje operace pro:

    - vytváření a mazání VM
    - změnu stavu VM
    - čtení konfigurace a metrik
    - práci se snapshoty
    - práci se zálohami
    - otevření konzole
    """

    KVM_GUEST_DEFAULTS = {
        "linux24": {
            "machine": "pc-i440fx",
            "firmware": "bios",
        },
        "linux": {
            "machine": "q35",
            "firmware": "efi",
        },
        "windows-modern": {
            "machine": "q35",
            "firmware": "efi",
        },
        "windows-latest": {
            "machine": "q35",
            "firmware": "efi",
        },
        "other32": {
            "machine": "pc-i440fx",
            "firmware": "bios",
        },
        "other64": {
            "machine": "q35",
            "firmware": "bios",
        },
    }

    def __init__(self, connection):
        """Inicializuje API klienta pro práci s KVM/libvirt.

        Args:
            connection: Objekt zajišťující komunikaci s libvirt backendem.
        """
        self.conn = connection

    # KVM
    def get_vm_capabilities(self) -> dict:
        """Vrátí schopnosti platformy KVM.

        Returns:
            Slovník popisující podporované typy disků, sítí, guest OS,
            boot možností a dalších parametrů.
        """
        return {
            "source_types": ["empty", "iso", "backup"],

            "guest": {
                "types": ["linux24", "linux", "windows-modern", "windows-latest", "other32", "other64"],
                "default": "other64",
            },

            "disk": {
                "buses": ["scsi", "sata", "ide", "virtio"],
                "controllers": ["virtio-scsi-single"],
                "default_bus": "scsi",
                "default_controller": "virtio-scsi-single",
            },

            "network": {
                "models": ["virtio", "e1000", "rtl8139"],
                "default_model": "virtio",
            },

            "boot": {
                "firmware": ["default", "bios", "uefi"],
                "machines": ["default", "q35", "i440fx"],
                "secure_boot": False,
            },

            "graphics": {
                "models": ["default"],
                "default": "default",
            },

            "options": {
                "start_after_create": True,
            },
        }
    
    def create_vm(self, node_name: str, opt_params: dict) -> dict:
        """Vytvoří nový virtuální stroj.

        Podporované zdroje:

        - backup
        - ISO
        - prázdná konfigurace

        Args:
            node_name: Název uzlu.
            opt_params: Konfigurace VM.

        Returns:
            Slovník s výsledkem vytvoření VM.
        """
        
        source = opt_params.get("source")

        if source and source.get("type") == "backup":
             return self.restore_vm_from_backup(opt_params)

        return self._create_vm_base(node_name, opt_params, source)
    

    def destroy_vm(self, node_name:str , vm_id: str) -> None:
        """Smaže virtuální stroj včetně disků.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.

        Returns:
            Slovník obsahující seznam smazaných disků, přeskočených disků a chyb.
        """
         
        if not vm_id:
            raise ValueError("vm_id is required")

        conn = self.conn

        try:
            try:
                domain = conn.lookupByName(vm_id)
            except libvirt.libvirtError:
                domain = conn.lookupByUUIDString(vm_id)

            domain_xml = domain.XMLDesc(0)
            root = ET.fromstring(domain_xml)

            state, _ = domain.state()
            if state != libvirt.VIR_DOMAIN_SHUTOFF:
                domain.destroy()

            deleted_disks = []
            skipped_disks = []
            errors = []


            for disk in root.findall("./devices/disk"):
                if disk.get("device") != "disk":
                    continue

                source = disk.find("source")
                if source is None:
                    continue

                disk_type = disk.get("type")
                target = disk.find("target")
                target_dev = target.get("dev") if target is not None else None

                try:
             
                    if disk_type == "volume":
                        pool_name = source.get("pool")
                        vol_name = source.get("volume")

                        if not pool_name or not vol_name:
                            skipped_disks.append({
                                "target": target_dev,
                                "reason": "missing pool/volume attributes",
                            })
                            continue

                        pool = conn.storagePoolLookupByName(pool_name)
                        vol = pool.storageVolLookupByName(vol_name)
                        vol_path = None
                        try:
                            vol_path = vol.path()
                        except Exception:
                            pass

                        vol.delete(0)
                        deleted_disks.append({
                            "target": target_dev,
                            "type": "volume",
                            "pool": pool_name,
                            "volume": vol_name,
                            "path": vol_path,
                        })

               
                    elif disk_type in ("file", "block"):
                        path = source.get("file") or source.get("dev")
                        if not path:
                            skipped_disks.append({
                                "target": target_dev,
                                "reason": "missing source path",
                            })
                            continue

                     
                        driver = disk.find("driver")
                        fmt = driver.get("type") if driver is not None else None
                        readonly = disk.find("readonly") is not None

                        if readonly or fmt == "iso":
                            skipped_disks.append({
                                "target": target_dev,
                                "path": path,
                                "reason": "readonly/iso disk skipped",
                            })
                            continue

                        deleted = False

                    
                        try:
                            vol = conn.storageVolLookupByPath(path)
                            vol.delete(0)
                            deleted_disks.append({
                                "target": target_dev,
                                "type": disk_type,
                                "path": path,
                                "managed_by": "libvirt",
                            })
                            deleted = True
                        except libvirt.libvirtError:
                            pass

                 
                        if not deleted and disk_type == "file":
                            if os.path.exists(path):
                                os.remove(path)
                                deleted_disks.append({
                                    "target": target_dev,
                                    "type": disk_type,
                                    "path": path,
                                    "managed_by": "filesystem",
                                })
                                deleted = True

                        if not deleted:
                            skipped_disks.append({
                                "target": target_dev,
                                "path": path,
                                "reason": "not a managed libvirt volume or unsupported source",
                            })

                    else:
                        skipped_disks.append({
                            "target": target_dev,
                            "reason": f"unsupported disk type '{disk_type}'",
                        })

                except Exception as e:
                    errors.append({
                        "target": target_dev,
                        "error": str(e),
                    })

            # 3) smaž definici VM
            flags = 0
            if hasattr(libvirt, "VIR_DOMAIN_UNDEFINE_MANAGED_SAVE"):
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
            if hasattr(libvirt, "VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA"):
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
            if hasattr(libvirt, "VIR_DOMAIN_UNDEFINE_NVRAM"):
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_NVRAM
            if hasattr(libvirt, "VIR_DOMAIN_UNDEFINE_CHECKPOINTS_METADATA"):
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_CHECKPOINTS_METADATA

            if flags:
                domain.undefineFlags(flags)
            else:
                domain.undefine()

            return {
                "status": "success",
                "message": f"VM '{vm_id}' was destroyed and undefined",
                "deleted_disks": deleted_disks,
                "skipped_disks": skipped_disks,
                "errors": errors,
            }

        except libvirt.libvirtError as e:
            raise RuntimeError(f"Failed to destroy VM '{vm_id}': {e}") from e
    

    def get_vm_status(self, node_name: str, vm_id: str, params: list) -> dict:
        """Vrátí aktuální stav a vybrané metriky VM.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.
            params: Seznam požadovaných metrik.

        Returns:
            Slovník obsahující metriky jako CPU, paměť, disk atd.
        """
        res = {}
        params_set = set(params)

        current_metrics = {"cpu_usage"}
        vcpu_keys = {"cpu_num"}
        memory_keys = {"memory_total", "memory_used", "memory_free"}
        disk_keys = {"disk_total", "disk_used", "disk_free"}

        vm = self.conn.session.lookupByName(vm_id)
        
        query_metrics = [m for m in current_metrics if m in params_set]
        
        if query_metrics:
            metrics = self.conn.get_current_metrics(query_metrics, node_name, vm_id)

            for metric in query_metrics:
                res[metric] = metrics.get(metric)

        dom_info = None

        if params_set & (vcpu_keys | memory_keys):
            dom_info = vm.info()

        if dom_info is not None:
            state, max_mem_kb, cur_mem_kb, nr_virt_cpu, cpu_time_ns = dom_info

            if "cpu_num" in params_set:
                res["cpu_num"] = nr_virt_cpu

            if "memory_total" in params_set:
                res["memory_total"] = int(max_mem_kb) * 1024

        if params_set & memory_keys:
            memstats = {}
            try:
                memstats = vm.memoryStats()
            except libvirt.libvirtError:
                memstats = {}

            if memstats:
                available_kb = int(memstats.get("available", 0))
                unused_kb = int(memstats.get("unused", 0))
                actual_kb = int(memstats.get("actual", 0))

                total_kb = actual_kb or (dom_info[1] if dom_info else 0)

                if "memory_total" in params_set and total_kb:
                    res["memory_total"] = total_kb * 1024

                if "memory_used" in params_set and available_kb:
                    res["memory_used"] = max(0, available_kb - unused_kb) * 1024

                if "memory_free" in params_set:
                    if unused_kb:
                        res["memory_free"] = unused_kb * 1024
                    elif available_kb and total_kb:
                        res["memory_free"] = max(0, total_kb - (available_kb - unused_kb)) * 1024

        if disk_keys & params_set:
            total, used, free = self._get_vm_disk_summary(vm)

            if "disk_total" in params_set:
                res["disk_total"] = total

            if "disk_used" in params_set:
                res["disk_used"] = used

            if "disk_free" in params_set:
                res["disk_free"] = free

        if "uptime" in params_set:
            res["uptime"] = None

        if "sysname" in params_set:
            res["sysname"] = vm.name()

        return res


    def get_vm_time_metrics(self, node_name: str, vm_id: str, params: dict) -> list[dict]:
        """Vrátí časovou řadu metrik VM.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.
            params: Parametry dotazu (timeframe, fields).

        Returns:
            Seznam bodů časové řady.
        """

        timeframe = params.get("timeframe", "hour")
        fields = params.get("fields", [])

        response = self.conn.get_rrd_metrics(
            interval=timeframe,
            cf="AVERAGE",
            ds=fields,
            host=node_name,
            vm=vm_id
        )

        if not response.get("success"):
            return []

        result = []

        for ts, values in sorted(response.get("data", {}).items(), key=lambda x: int(x[0])):
            point = {"time": int(ts)}

            for field in fields:
                point[field] = values.get(field)

            result.append(point)

        return result


    def set_vm_status(self, node_name: str, vmid: str, status: str) -> dict:
        """Změní stav virtuálního stroje.

        Podporované akce:
        start, stop, shutdown, suspend, resume, reboot, reset

        Args:
            node_name: Název uzlu.
            vmid: Identifikátor VM.
            status: Požadovaná akce.

        Returns:
            Výsledek operace.
        """
         
        valid_statuses = {"start", "stop", "shutdown", "suspend", "reset", "reboot", "resume"}
        if status not in valid_statuses:
            raise ValueError("Invalid status")

        vm = self.conn.session.lookupByName(vmid)

        try:
            state, _ = vm.state()

            allowed_actions = {
                libvirt.VIR_DOMAIN_RUNNING: {"stop", "shutdown", "suspend", "reset", "reboot"},
                libvirt.VIR_DOMAIN_PAUSED: {"resume", "stop", "shutdown"},
                libvirt.VIR_DOMAIN_SHUTOFF: {"start"},
                libvirt.VIR_DOMAIN_SHUTDOWN: {"start"},
                libvirt.VIR_DOMAIN_CRASHED: {"start", "stop", "reset"},
            }

            allowed = allowed_actions.get(state, set())
            if status not in allowed:
                return {
                    "status": "error",
                    "message": f"Action '{status}' is not allowed in current VM state {state}"
                }

            if status == "start":
                vm.create()
            elif status == "stop":
                vm.destroy()
            elif status == "shutdown":
                vm.shutdown()
            elif status == "suspend":
                vm.suspend()
            elif status == "resume":
                vm.resume()
            elif status == "reboot":
                vm.reboot(0)
            elif status == "reset":
                vm.reset(0)

            return {"status": "ok", "message": f"Action '{status}' executed"}

        except libvirt.libvirtError as e:
            return {"status": "error", "message": str(e)}


    def manage_vm_snapshots(
        self,
        node_name: str,
        vmid: str,
        snap_data: dict | None = None,
    ) -> dict | list[dict]:
        """Vytvoří snapshot nebo vrátí seznam snapshotů.

        Args:
            node_name: Název uzlu.
            vmid: Identifikátor VM.
            snap_data: Parametry snapshotu.

        Returns:
            Nový snapshot nebo seznam snapshotů.
        """
         
        vm = self.conn.session.lookupByName(vmid)

        # CREATE SNAPSHOT
        if snap_data:
            snapshotname = (
                snap_data.get("snapshotname")
                or snap_data.get("snapname")
                or snap_data.get("name")
            )

            if not snapshotname:
                raise ValueError("Snapshot name is required")

            existing = [s.getName() for s in vm.listAllSnapshots()]
            if snapshotname in existing:
                raise ValueError("Snapshot name already exists")

            description = snap_data.get("description") or ""
            vm_state = bool(snap_data.get("vm_state", snap_data.get("vmstate", False)))

            memory_xml = (
                "<memory snapshot='internal'/>"
                if vm_state
                else "<memory snapshot='no'/>"
            )

            snapshot_xml = f"""
            <domainsnapshot>
                <name>{escape(snapshotname)}</name>
                <description>{escape(description)}</description>
                {memory_xml}
            </domainsnapshot>
            """.strip()

            snap = vm.snapshotCreateXML(snapshot_xml, 0)

            snap_time = None
            parent_name = None

            try:
                raw_xml = snap.getXMLDesc(0)
                xml = minidom.parseString(raw_xml)

                creation_nodes = xml.getElementsByTagName("creationTime")
                if creation_nodes and creation_nodes[0].firstChild:
                    snap_time = int(creation_nodes[0].firstChild.nodeValue)

                parent_nodes = xml.getElementsByTagName("parent")
                if parent_nodes:
                    name_nodes = parent_nodes[0].getElementsByTagName("name")
                    if name_nodes and name_nodes[0].firstChild:
                        parent_name = name_nodes[0].firstChild.nodeValue
            except Exception:
                pass

            return {
                "id": snap.getName(),
                "snapshot_ref": snap.getName(),
                "name": snap.getName(),
                "description": description or None,
                "snaptime": snap_time,
                "parent": parent_name,
                "parent_id": parent_name,
                "running": 0,
                "is_current": True,
            }

        # LIST SNAPSHOTS
        result = []
        snapshot_by_name = {}

        current_name = None
        try:
            if vm.hasCurrentSnapshot(0):
                current_snap = vm.snapshotCurrent(0)
                current_name = current_snap.getName()
        except Exception:
            current_name = None

        flags = getattr(libvirt, "VIR_DOMAIN_SNAPSHOT_LIST_TOPOLOGICAL", 0)

        try:
            snapshots = vm.listAllSnapshots(flags)
        except TypeError:
            snapshots = vm.listAllSnapshots()

        for snap in snapshots:
            description = None
            snaptime = None
            parent_name = None

            try:
                raw_xml = snap.getXMLDesc(0)
                xml = minidom.parseString(raw_xml)

                desc_nodes = xml.getElementsByTagName("description")
                if desc_nodes and desc_nodes[0].firstChild:
                    description = desc_nodes[0].firstChild.nodeValue

                creation_nodes = xml.getElementsByTagName("creationTime")
                if creation_nodes and creation_nodes[0].firstChild:
                    snaptime = int(creation_nodes[0].firstChild.nodeValue)

                parent_nodes = xml.getElementsByTagName("parent")
                if parent_nodes:
                    name_nodes = parent_nodes[0].getElementsByTagName("name")
                    if name_nodes and name_nodes[0].firstChild:
                        parent_name = name_nodes[0].firstChild.nodeValue

            except Exception:
                pass

            item = {
                "id": snap.getName(),
                "snapshot_ref": snap.getName(),
                "name": snap.getName(),
                "description": description,
                "snaptime": snaptime,
                "parent": parent_name,
                "parent_id": parent_name,
                "running": 0,
                "is_current": False,
            }

            snapshot_by_name[item["name"]] = item
            result.append(item)

        result.sort(key=lambda x: (x.get("snaptime") is None, x.get("snaptime") or 0))

        for item in result:
            if item["parent"] and item["parent"] in snapshot_by_name:
                item["parent_id"] = snapshot_by_name[item["parent"]]["id"]

        current_base = None
        if current_name:
            current_base = next((x for x in result if x["name"] == current_name), None)

        current_item = {
            "id": "current",
            "snapshot_ref": "current",
            "name": "current",
            "description": "Current VM state",
            "snaptime": None,
            "parent": current_base["name"] if current_base else None,
            "parent_id": current_base["id"] if current_base else None,
            "running": 1,
            "is_current": True,
        }

        return [current_item, *result]

    def drop_vm_snapshot(self, node_name: str, vmid: str, snapname: str) -> None:
        """Smaže snapshot virtuálního stroje.

        Args:
            node_name: Název uzlu.
            vmid: Identifikátor VM.
            snapname: Název snapshotu.

        Returns:
            Výsledek operace.
        """

        try:
            vm = self.conn.session.lookupByName(vmid)
            snap = vm.snapshotLookupByName(snapname, 0)

            snap.delete(0)

            return {
                "snapshot_ref": snapname,
                "name": snapname,
                "deleted": True
            }

        except libvirt.libvirtError as e:
            return {
                "status": "error",
                "message": str(e)
            }

    
    def rollback_vm_snapshot(self, node_name: str, vmid: str, snapname: str) -> None:
        """Provede rollback VM na snapshot.

        Args:
            node_name: Název uzlu.
            vmid: Identifikátor VM.
            snapname: Název snapshotu.

        Returns:
            Výsledek operace.
        """
        try:
            vm = self.conn.session.lookupByName(vmid)
            snap = vm.snapshotLookupByName(snapname, 0)

            vm.revertToSnapshot(snap, 0)

            return {
                "snapshot_ref": snapname,
                "name": snapname,
                "rolled_back": True,
            }

        except libvirt.libvirtError as e:
            return {
                "status": "error",
                "message": str(e)
            }
    

    def get_vm_config(self, node_name: str, vmid: str) -> dict:
        """Vrátí konfiguraci virtuálního stroje.

        Args:
            node_name: Název uzlu.
            vmid: Identifikátor VM.

        Returns:
            Normalizovaná konfigurace VM.
        """
        vm = self.conn.session.lookupByName(vmid)

        raw_xml = vm.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
        xml = minidom.parseString(raw_xml)
        domain = xml.documentElement

        name = vm.name()

        memory_mb = None
        memory_nodes = domain.getElementsByTagName("currentMemory")

        if memory_nodes and memory_nodes[0].firstChild:
            try:
                memory_kib = int(memory_nodes[0].firstChild.nodeValue)
                memory_mb = memory_kib // 1024
            except (ValueError, TypeError):
                memory_mb = None

        cpu_info = self._get_vm_cpu_config(xml)
        disks, cdroms = self._get_vm_disks_and_cdroms(xml)
        networks = self._get_vm_networks_config(xml)
        boot = self._get_vm_boot_config(xml)
        options = self._get_vm_options_config(xml, vm)

        return {
            "vmid": vmid,
            "name": name,
            "memory_mb": memory_mb,
            "cpu": cpu_info,
            "disks": disks,
            "cdroms": cdroms,
            "networks": networks,
            "boot": boot,
            "options": options,
        }
    
    def set_vm_config(self, node_name: str, vmid: str, optional_params: dict) -> dict:
        """Aktualizuje konfiguraci virtuálního stroje.

        Args:
            node_name: Název Proxmox uzlu.
            vm_id: Identifikátor virtuálního stroje.
            optional_params: Parametry konfigurace, které mají být změněny.
        """
        vm = self.conn.session.lookupByName(vmid)
        was_running = vm.isActive() == 1

        current_config = self.get_vm_config(node_name, vmid)

        raw_xml = vm.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
        xml = minidom.parseString(raw_xml)

        changed = False
        requires_shutdown = False

        options = optional_params.get("options") or {}
        current_options = current_config.get("options") or {}

        # NAME
        if optional_params.get("name") and optional_params["name"] != current_config.get("name"):
            self._set_domain_name(xml, optional_params["name"])
            changed = True

        # MEMORY
        if optional_params.get("memory_mb") is not None:
            new_memory = int(optional_params["memory_mb"])
            old_memory = int(current_config.get("memory_mb") or 0)

            if new_memory != old_memory:
                self._set_memory(xml, new_memory)
                changed = True
                requires_shutdown = True

        # CPU
        if optional_params.get("cpu"):
            new_cpu = optional_params.get("cpu") or {}
            old_cpu = current_config.get("cpu") or {}

            if (
                int(new_cpu.get("cores") or old_cpu.get("cores") or 1) != int(old_cpu.get("cores") or 1)
                or int(new_cpu.get("sockets") or old_cpu.get("sockets") or 1) != int(old_cpu.get("sockets") or 1)
                or (new_cpu.get("type") or old_cpu.get("type")) != old_cpu.get("type")
            ):
                self._set_cpu(xml, new_cpu, old_cpu)
                changed = True
                requires_shutdown = True

        # GRAPHICS
        if "graphics" in options:
            new_graphics = options.get("graphics") or "default"
            old_graphics = current_options.get("graphics") or "default"

            if new_graphics != old_graphics:
                self._set_graphics(xml, new_graphics)
                changed = True
                requires_shutdown = True

        # BOOT
        if optional_params.get("boot"):
            new_boot = optional_params.get("boot") or {}
            old_boot = current_config.get("boot") or {}

            if (new_boot.get("order") or []) != (old_boot.get("order") or []):
                self._set_boot(xml, new_boot)
                changed = True
                requires_shutdown = True

        # DISKS
        old_disks = current_config.get("disks") or []

        for new_disk in optional_params.get("disks") or []:
            slot = new_disk.get("slot")
            if not slot:
                continue

            old_disk = next((d for d in old_disks if d.get("slot") == slot), None)

            comparable_new = {
                "slot": new_disk.get("slot"),
                "storage_id": new_disk.get("storage_id"),
                "volume": new_disk.get("volume"),
                "size_gb": new_disk.get("size_gb"),
                "controller_type": new_disk.get("controller_type"),
            }

            comparable_old = {
                "slot": old_disk.get("slot") if old_disk else None,
                "storage_id": old_disk.get("storage_id") if old_disk else None,
                "volume": old_disk.get("volume") if old_disk else None,
                "size_gb": old_disk.get("size_gb") if old_disk else None,
                "controller_type": old_disk.get("controller_type") if old_disk else None,
            }

            if old_disk is None or comparable_new != comparable_old:
                self._set_disk(xml, vm, new_disk)
                changed = True
                requires_shutdown = True

        # CDROMS
        old_cdroms = current_config.get("cdroms") or []
        new_cdroms = optional_params.get("cdroms") or []

        if "cdroms" in optional_params:
            new_cdrom_slots = {c.get("slot") for c in new_cdroms if c.get("slot")}
            devices = self._get_devices_node(xml)

            for old_cdrom in old_cdroms:
                old_slot = old_cdrom.get("slot")
                if old_slot and old_slot not in new_cdrom_slots:
                    old_node = self._find_disk_by_target(devices, old_slot, "cdrom")
                    if old_node is not None:
                        devices.removeChild(old_node)
                        changed = True
                        requires_shutdown = True

        for new_cdrom in new_cdroms:
            slot = new_cdrom.get("slot")
            if not slot:
                continue

            old_cdrom = next((c for c in old_cdroms if c.get("slot") == slot), None)

            comparable_new = {
                "slot": new_cdrom.get("slot"),
                "storage_id": new_cdrom.get("storage_id"),
                "volume": new_cdrom.get("volume") or new_cdrom.get("path"),
            }

            comparable_old = {
                "slot": old_cdrom.get("slot") if old_cdrom else None,
                "storage_id": old_cdrom.get("storage_id") if old_cdrom else None,
                "volume": old_cdrom.get("volume") if old_cdrom else None,
            }

            if old_cdrom is None or comparable_new != comparable_old:
                self._set_cdrom(xml, new_cdrom)
                changed = True
                requires_shutdown = True

        # NETWORKS
        old_networks = current_config.get("networks") or []

        for new_network in optional_params.get("networks") or []:
            slot = new_network.get("slot")
            if not slot:
                continue

            old_network = next((n for n in old_networks if n.get("slot") == slot), None)

            comparable_new = {
                "slot": new_network.get("slot"),
                "network_id": new_network.get("network_id"),
                "model": new_network.get("model"),
                "mac": new_network.get("mac"),
                "connected": new_network.get("connected", True),
            }

            comparable_old = {
                "slot": old_network.get("slot") if old_network else None,
                "network_id": old_network.get("network_id") if old_network else None,
                "model": old_network.get("model") if old_network else None,
                "mac": old_network.get("mac") if old_network else None,
                "connected": old_network.get("connected", True) if old_network else True,
            }

            if old_network is None or comparable_new != comparable_old:
                self._set_network(xml, new_network)
                changed = True
                requires_shutdown = True

        if changed:
            self.conn.session.defineXML(xml.toxml())

        if "autostart" in options:
            new_autostart = bool(options.get("autostart"))
            old_autostart = bool(current_options.get("autostart"))

            if new_autostart != old_autostart:
                vm.setAutostart(1 if new_autostart else 0)
                changed = True

        return {
            "success": True,
            "changed": changed,
            "required_action": "shutdown" if requires_shutdown else "none",
            "was_running": was_running,
        }


    def _set_domain_name(self, xml, new_name: str):
        domain = xml.documentElement
        name_nodes = domain.getElementsByTagName("name")

        if name_nodes:
            node = name_nodes[0]
            if node.firstChild:
                node.firstChild.nodeValue = str(new_name)
            else:
                node.appendChild(xml.createTextNode(str(new_name)))
            return

        node = xml.createElement("name")
        node.appendChild(xml.createTextNode(str(new_name)))
        domain.insertBefore(node, domain.firstChild)


    def _set_memory(self, xml, memory_mb: int):
        domain = xml.documentElement
        memory_kib = int(memory_mb) * 1024

        for tag in ("memory", "currentMemory"):
            nodes = domain.getElementsByTagName(tag)
            node = nodes[0] if nodes else None

            if node is None:
                node = xml.createElement(tag)
                node.setAttribute("unit", "KiB")
                domain.appendChild(node)

            if node.firstChild:
                node.firstChild.nodeValue = str(memory_kib)
            else:
                node.appendChild(xml.createTextNode(str(memory_kib)))


    def _set_cpu(self, xml, new_cpu: dict, old_cpu: dict):
        domain = xml.documentElement

        cores = int(new_cpu.get("cores") or old_cpu.get("cores") or 1)
        sockets = int(new_cpu.get("sockets") or old_cpu.get("sockets") or 1)
        cpu_type = new_cpu.get("type") or old_cpu.get("type") or "host-model"
        threads = 1
        total_vcpu = cores * sockets * threads

        vcpu_nodes = domain.getElementsByTagName("vcpu")
        vcpu_node = vcpu_nodes[0] if vcpu_nodes else xml.createElement("vcpu")

        if not vcpu_nodes:
            vcpu_node.setAttribute("placement", "static")
            domain.appendChild(vcpu_node)

        if vcpu_node.firstChild:
            vcpu_node.firstChild.nodeValue = str(total_vcpu)
        else:
            vcpu_node.appendChild(xml.createTextNode(str(total_vcpu)))

        cpu_nodes = domain.getElementsByTagName("cpu")
        cpu_node = cpu_nodes[0] if cpu_nodes else xml.createElement("cpu")

        if not cpu_nodes:
            domain.appendChild(cpu_node)

        if cpu_type in ("host", "host-passthrough"):
            cpu_node.setAttribute("mode", "host-passthrough")
        elif cpu_type in ("host-model", "default"):
            cpu_node.setAttribute("mode", "host-model")
        else:
            cpu_node.setAttribute("mode", "custom")

        topology_nodes = cpu_node.getElementsByTagName("topology")
        topology = topology_nodes[0] if topology_nodes else xml.createElement("topology")

        if not topology_nodes:
            cpu_node.appendChild(topology)

        topology.setAttribute("sockets", str(sockets))
        topology.setAttribute("cores", str(cores))
        topology.setAttribute("threads", str(threads))


    def _set_graphics(self, xml, graphics_type: str):
        if graphics_type == "default":
            graphics_type = "vnc"

        if graphics_type in ("none", "disabled"):
            devices = self._get_devices_node(xml)
            for node in list(devices.getElementsByTagName("graphics")):
                devices.removeChild(node)
            return

        if graphics_type not in ("vnc", "spice"):
            raise ValueError("graphics type must be 'vnc', 'spice', 'none' or 'default'")

        devices = self._get_devices_node(xml)
        nodes = devices.getElementsByTagName("graphics")
        node = nodes[0] if nodes else xml.createElement("graphics")

        if not nodes:
            devices.appendChild(node)

        node.setAttribute("type", graphics_type)
        node.setAttribute("autoport", "yes")
        node.setAttribute("port", "-1")


    def _set_boot(self, xml, boot_params: dict):
        order = boot_params.get("order") or []
        domain = xml.documentElement

        os_nodes = domain.getElementsByTagName("os")
        if not os_nodes:
            return

        os_node = os_nodes[0]

        for node in list(os_node.getElementsByTagName("boot")):
            os_node.removeChild(node)

        for item in order:
            if str(item).startswith(("ide", "sata")):
                dev = "cdrom"
            elif str(item).startswith("net"):
                dev = "network"
            else:
                dev = "hd"

            boot_node = xml.createElement("boot")
            boot_node.setAttribute("dev", dev)
            os_node.appendChild(boot_node)


    def _set_disk(self, xml, vm, disk_params: dict):
        slot = disk_params.get("slot")
        if not slot:
            raise ValueError("Disk requires slot")

        storage_id = disk_params.get("storage_id")
        volume = disk_params.get("volume")
        size_gb = disk_params.get("size_gb")
        fmt = disk_params.get("format") or "qcow2"

        bus, target_dev = self._disk_target_from_slot(slot)

        devices = self._get_devices_node(xml)
        disk_node = self._find_disk_by_target(devices, target_dev, "disk")

        if disk_node is None:
            disk_node = xml.createElement("disk")
            disk_node.setAttribute("type", "volume" if storage_id else "file")
            disk_node.setAttribute("device", "disk")
            devices.appendChild(disk_node)

        driver = self._first_child(xml, disk_node, "driver")
        driver.setAttribute("name", "qemu")
        driver.setAttribute("type", fmt)

        target = self._first_child(xml, disk_node, "target")
        target.setAttribute("dev", target_dev)
        target.setAttribute("bus", bus)

        source = self._first_child(xml, disk_node, "source")

        if volume:
            if storage_id:
                disk_node.setAttribute("type", "volume")
                source.removeAttribute("file") if source.hasAttribute("file") else None
                source.setAttribute("pool", storage_id)
                source.setAttribute("volume", volume)
            else:
                disk_node.setAttribute("type", "file")
                source.removeAttribute("pool") if source.hasAttribute("pool") else None
                source.removeAttribute("volume") if source.hasAttribute("volume") else None
                source.setAttribute("file", volume)

        elif storage_id and size_gb is not None:
            pool = self.conn.session.storagePoolLookupByName(storage_id)
            vol_name = f"{vm.name()}-{slot}.{fmt}"

            try:
                vol = pool.storageVolLookupByName(vol_name)
            except libvirt.libvirtError:
                capacity_bytes = int(size_gb) * 1024 * 1024 * 1024
                volume_xml = f"""
                <volume>
                    <name>{escape(vol_name)}</name>
                    <capacity unit="bytes">{capacity_bytes}</capacity>
                    <target>
                        <format type="{escape(fmt)}"/>
                    </target>
                </volume>
                """.strip()
                vol = pool.createXML(volume_xml, 0)

            disk_node.setAttribute("type", "volume")
            source.removeAttribute("file") if source.hasAttribute("file") else None
            source.setAttribute("pool", storage_id)
            source.setAttribute("volume", vol.name())

        if size_gb is not None:
            self._resize_disk(vm, source, target_dev, size_gb)


    def _set_cdrom(self, xml, cdrom_params: dict):
        slot = cdrom_params.get("slot")
        if not slot:
            raise ValueError("CD-ROM requires slot")

        storage_id = cdrom_params.get("storage_id")
        volume = cdrom_params.get("volume") or cdrom_params.get("path")

        if not storage_id:
            raise ValueError("CD-ROM requires storage_id")

        if not volume:
            raise ValueError("CD-ROM requires volume or path")

        devices = self._get_devices_node(xml)
        cdrom_node = self._find_disk_by_target(devices, slot, "cdrom")

        if cdrom_node is None:
            cdrom_node = xml.createElement("disk")
            cdrom_node.setAttribute("device", "cdrom")
            devices.appendChild(cdrom_node)

        cdrom_node.setAttribute("type", "volume")

        driver = self._first_child(xml, cdrom_node, "driver")
        driver.setAttribute("name", "qemu")
        driver.setAttribute("type", "raw")

        source = self._first_child(xml, cdrom_node, "source")
        source.removeAttribute("file") if source.hasAttribute("file") else None
        source.setAttribute("pool", storage_id)
        source.setAttribute("volume", volume)

        target = self._first_child(xml, cdrom_node, "target")
        target.setAttribute("dev", slot)
        target.setAttribute("bus", cdrom_params.get("controller_type") or "ide")

        if not cdrom_node.getElementsByTagName("readonly"):
            cdrom_node.appendChild(xml.createElement("readonly"))


    def _set_network(self, xml, network_params: dict):
        slot = network_params.get("slot")
        if not slot:
            raise ValueError("Network requires slot")

        network_id = network_params.get("network_id")
        if not network_id:
            raise ValueError("Network requires network_id")

        devices = self._get_devices_node(xml)
        iface = self._find_interface_by_slot(devices, slot)

        if iface is None:
            iface = xml.createElement("interface")
            devices.appendChild(iface)

        iface.setAttribute("type", "bridge")

        source = self._first_child(xml, iface, "source")
        source.removeAttribute("network") if source.hasAttribute("network") else None
        source.setAttribute("bridge", network_id)

        target = self._first_child(xml, iface, "target")
        target.setAttribute("dev", slot)

        if network_params.get("mac"):
            mac = self._first_child(xml, iface, "mac")
            mac.setAttribute("address", network_params["mac"])

        model = self._first_child(xml, iface, "model")
        model.setAttribute("type", network_params.get("model") or "virtio")

        if network_params.get("connected", True) is False:
            link = self._first_child(xml, iface, "link")
            link.setAttribute("state", "down")
        else:
            for link in list(iface.getElementsByTagName("link")):
                iface.removeChild(link)


    def _get_devices_node(self, xml):
        nodes = xml.documentElement.getElementsByTagName("devices")
        if not nodes:
            raise ValueError("Missing <devices> element")
        return nodes[0]


    def _first_child(self, xml, parent, tag: str):
        nodes = parent.getElementsByTagName(tag)
        if nodes:
            return nodes[0]

        node = xml.createElement(tag)
        parent.appendChild(node)
        return node


    def _find_disk_by_target(self, devices, slot: str, device_type: str | None = None):
        for disk in devices.getElementsByTagName("disk"):
            if device_type and disk.getAttribute("device") != device_type:
                continue

            target_nodes = disk.getElementsByTagName("target")
            if target_nodes and target_nodes[0].getAttribute("dev") == slot:
                return disk

        return None


    def _find_interface_by_slot(self, devices, slot: str):
        if slot.startswith("net"):
            try:
                index = int(slot.replace("net", ""))
                interfaces = devices.getElementsByTagName("interface")
                if index < len(interfaces):
                    return interfaces[index]
            except ValueError:
                pass

        for iface in devices.getElementsByTagName("interface"):
            target_nodes = iface.getElementsByTagName("target")
            if target_nodes and target_nodes[0].getAttribute("dev") == slot:
                return iface

        return None

    def _resolve_disk_path_from_node(self, source):
        if source.hasAttribute("file"):
            return source.getAttribute("file")

        if source.hasAttribute("pool") and source.hasAttribute("volume"):
            pool = self.conn.session.storagePoolLookupByName(source.getAttribute("pool"))
            vol = pool.storageVolLookupByName(source.getAttribute("volume"))
            return vol.path()

        return None


    def _resize_disk(self, vm, source, target_dev: str, size_gb: int):
        size_bytes = int(size_gb) * 1024 * 1024 * 1024

        if vm.isActive():
            try:
                vm.blockResize(
                    target_dev,
                    size_bytes,
                    libvirt.VIR_DOMAIN_BLOCK_RESIZE_BYTES,
                )
                return
            except libvirt.libvirtError:
                pass

        if source.hasAttribute("pool") and source.hasAttribute("volume"):
            pool = self.conn.session.storagePoolLookupByName(source.getAttribute("pool"))
            vol = pool.storageVolLookupByName(source.getAttribute("volume"))
            vol.resize(size_bytes, 0)
            return

        if source.hasAttribute("file"):
            vol = self.conn.session.storageVolLookupByPath(source.getAttribute("file"))
            vol.resize(size_bytes, 0)
            return

        raise ValueError("Cannot resolve disk source for resize")








    def create_vm_backup(self, node_name: str, vm_id: str, backup_root: str) -> None:
        """Vytvoří zálohu VM pomocí NBD exportu.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.
            backup_root: Cílová složka záloh.
        """
        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_dir = os.path.join(
            backup_root,
            "kvm",
            str(vm_id),
            backup_time
        )

        os.makedirs(backup_dir, exist_ok=True)

        dom = self.conn.session.lookupByName(vm_id)

        try:
            dom.abortJob()
        except libvirt.libvirtError:
            pass

        vm_xml = dom.XMLDesc(0)
        xml_path = os.path.join(backup_dir, "vm.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(vm_xml)

        root = ET.fromstring(vm_xml)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("", 0))
        nbd_port = sock.getsockname()[1]
        sock.close()

        domainbackup = ET.Element("domainbackup", {"mode": "pull"})
        ET.SubElement(domainbackup, "server", {
            "transport": "tcp",
            "name": self.conn.host,
            "port": str(nbd_port)
        })

        disks_el = ET.SubElement(domainbackup, "disks")
        exports = []

        for disk in root.findall("./devices/disk"):
            if disk.get("device") != "disk":
                continue

            target = disk.find("target")
            source = disk.find("source")

            if target is None:
                continue

            dev = target.get("dev")
            if not dev:
                continue

            source_protocol = None
            disk_type = "file"

            if source is not None:
                source_protocol = source.get("protocol")
                if source.get("dev"):
                    disk_type = "block"

            if source_protocol:
                raise Exception(
                    f"Disk {dev} uses network storage/protocol ({source_protocol}), "
                    "this simple backup method supports only file/block disks."
                )

            export_name = f"{vm_id}-{dev}"
            scratch_path = f"/tmp/libvirt-backup-{vm_id}-{dev}.scratch"

            disk_el = ET.SubElement(disks_el, "disk", {
                "name": dev,
                "type": disk_type,
                "exportname": export_name
            })

            ET.SubElement(disk_el, "scratch", {
                "file": scratch_path
            })

            exports.append({
                "device": dev,
                "exportname": export_name,
                "local_file": os.path.join(backup_dir, f"{dev}.qcow2")
            })

        backup_xml = ET.tostring(domainbackup, encoding="unicode")

        dom.backupBegin(backup_xml, None, 0)

        try:
            try:
                runtime_backup_xml = dom.backupGetXMLDesc(0)
            except Exception:
                runtime_backup_xml = backup_xml

            runtime_root = ET.fromstring(runtime_backup_xml)

            server_el = runtime_root.find("./server")
            runtime_host = self.conn.host
            runtime_port = nbd_port

            if server_el is not None:
                runtime_host = server_el.get("name", self.conn.host)
                runtime_port = int(server_el.get("port", str(nbd_port)))

            runtime_exports = {}
            for disk_el in runtime_root.findall("./disks/disk"):
                disk_name = disk_el.get("name")
                export_name = disk_el.get("exportname", disk_name)
                runtime_exports[disk_name] = export_name

            for item in exports:
                if item["device"] in runtime_exports:
                    item["exportname"] = runtime_exports[item["device"]]

            for item in exports:
                nbd_url = f"nbd://{runtime_host}:{runtime_port}/{item['exportname']}"
                cmd = [
                    "qemu-img",
                    "convert",
                    "-p",
                    "-O", "qcow2",
                    nbd_url,
                    item["local_file"]
                ]
                subprocess.run(cmd, check=True)

        finally:
            try:
                dom.abortJob()
            except libvirt.libvirtError:
                pass
    

    def restore_vm_from_backup(self, opt_params: dict):
        """Obnoví VM ze zálohy.

        Args:
            opt_params: Parametry obsahující cestu k záloze a cílové jméno VM.

        Returns:
            Výsledek obnovy VM.
        """
         
        source_info = opt_params.get("source", {})
        backup_name = source_info.get("path")
        storage_id = source_info.get("storage_id")

        if not backup_name:
            raise ValueError("Backup source requires path")

        if storage_id == "kvm-local-backups":
            backup_dir = os.path.join(BACKUP_ROOT, "kvm", backup_name)
        else:
            backup_dir = backup_name

        if not os.path.isdir(backup_dir):
            raise ValueError(f"Backup directory does not exist: {backup_dir}")

        restored_name = opt_params["name"]
        start = bool(opt_params.get("options", {}).get("start_after_create", False))

        vm_xml_path = os.path.join(backup_dir, "vm.xml")
        if not os.path.isfile(vm_xml_path):
            raise ValueError(f"Backup XML not found: {vm_xml_path}")

        with open(vm_xml_path, "r", encoding="utf-8") as f:
            domain_xml = f.read()

        root = ET.fromstring(domain_xml)

        name_elem = root.find("./name")
        if name_elem is None:
            raise ValueError("Backup XML does not contain <name>")
        name_elem.text = restored_name

        uuid_elem = root.find("./uuid")
        if uuid_elem is not None:
            uuid_elem.text = str(uuid.uuid4())

        remote_base_dir = f"/vm-storage/{restored_name}"
        self.conn.run_ssh_command(f"mkdir -p '{remote_base_dir}'")

        for disk in root.findall("./devices/disk"):
            if disk.get("device") != "disk":
                continue

            target_elem = disk.find("target")
            source_elem = disk.find("source")

            if target_elem is None or source_elem is None:
                continue

            dev = target_elem.get("dev")
            if not dev:
                continue

            local_disk_path = os.path.join(backup_dir, f"{dev}.qcow2")
            if not os.path.isfile(local_disk_path):
                raise FileNotFoundError(f"Backup disk not found: {local_disk_path}")

            remote_disk_path = f"{remote_base_dir}/{dev}.qcow2"

            self.conn.copy_file_to_remote(local_disk_path, remote_disk_path)

            if "file" in source_elem.attrib:
                source_elem.set("file", remote_disk_path)

        for iface in root.findall("./devices/interface"):
            mac_elem = iface.find("mac")
            if mac_elem is not None:
                iface.remove(mac_elem)

            target_elem = iface.find("target")
            if target_elem is not None:
                iface.remove(target_elem)

        for serial in root.findall("./devices/serial"):
            source_elem = serial.find("source")
            if source_elem is not None:
                serial.remove(source_elem)

        for console in root.findall("./devices/console"):
            source_elem = console.find("source")
            if source_elem is not None:
                console.remove(source_elem)

        for channel in root.findall("./devices/channel"):
            source_elem = channel.find("source")
            if source_elem is not None:
                channel.remove(source_elem)

        if "id" in root.attrib:
            del root.attrib["id"]

        for graphics in root.findall("./devices/graphics"):
            if "port" in graphics.attrib:
                del graphics.attrib["port"]
            graphics.set("autoport", "yes")

        restored_xml = ET.tostring(root, encoding="unicode")

        dom = self.conn.session.defineXML(restored_xml)
        if dom is None:
            raise RuntimeError("Failed to restore VM from backup")

        if start:
            dom.create()

        return {
            "success": True,
            "name": dom.name(),
            "uuid": dom.UUIDString(),
            "backup_dir": backup_dir,
            "remote_dir": remote_base_dir,
            "status": "running" if start else "defined",
        }

    def open_console(self, node_name: str, vm_id: str, protocol: str = "vnc") -> dict:
        """Vrátí informace pro připojení ke konzoli VM.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.
            protocol: Typ konzole (aktuálně pouze VNC).

        Returns:
            Informace pro připojení (host, port, websocket URL).
        """
        
        dom = self.conn.session.lookupByName(vm_id)
        root = ET.fromstring(dom.XMLDesc(0))

        graphics = root.find("./devices/graphics[@type='vnc']")
        if graphics is None:
            raise Exception("No VNC configured")

        port = graphics.get("port")
        websocket = graphics.get("websocket")
        listen = graphics.get("listen")

        listen_elem = graphics.find("listen")
        if listen_elem is not None and listen_elem.get("address"):
            listen = listen_elem.get("address")

        host = self.conn.host
        if listen and listen not in ("0.0.0.0", "::"):
            host = listen

        port = int(port) if port and port != "-1" else None
        websocket = int(websocket) if websocket and websocket != "-1" else None

        if not port and not websocket:
            raise Exception("No usable console endpoint")

        return {
            "protocol": "vnc",
            "host": host,
            "port": port,
            "ticket": None,
            "ws_url": f"ws://{host}:{websocket}" if websocket else None,
        }
    
    def get_vm_backups(self, node_name: str, vm_id: str):
        """Vrátí seznam dostupných záloh VM.

        Args:
            node_name: Název uzlu.
            vm_id: Identifikátor VM.

        Returns:
            Seznam záloh.
        """
        return self._get_fs_vm_backups(vm_id, "kvm")
            
    def get_vm_logs(
        self,
        node_name: str,
        vm_name: str,
        limit: int = 1000,
    ) -> dict:
        """Vrátí logy VM ze syslogu.

        Args:
            node_name: Název uzlu.
            vm_name: Název VM.
            limit: Maximální počet řádků.

        Returns:
            Slovník obsahující logy.
        """
        if not vm_name:
            raise ValueError("vm_name is required")

        if limit < 0:
            raise ValueError("limit must be >= 0")

        syslog_path = os.path.join(LOG_ROOT, self.conn.host, "syslog.log")

        if not os.path.isfile(syslog_path):
            raise FileNotFoundError(f"Syslog file '{syslog_path}' not found")

        escaped_vm_name = re.escape(vm_name)
        pattern = re.compile(rf"kvm-qemu-{escaped_vm_name}:")

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
                    if pattern.search(line):
                        matched_lines.append(line)
                        if limit > 0 and len(matched_lines) >= limit:
                            break

            if buffer and (limit == 0 or len(matched_lines) < limit):
                line = buffer.decode("utf-8", errors="replace")
                if pattern.search(line):
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
    

    def _parse_vm_config(self, opt_params: dict) -> dict:
        name = opt_params["name"]
        memory_mib = int(opt_params.get("memory_mb", 2048))

        cpu = opt_params.get("cpu", {})
        cores = int(cpu.get("cores", 1))
        sockets = int(cpu.get("sockets", 1))
        threads = int(cpu.get("threads", 1))
        cpu_type = cpu.get("type", "host-model")

        disks = opt_params.get("disks", [])
        networks = opt_params.get("networks", [])
        boot = opt_params.get("boot", {})
        options = opt_params.get("options", {})
        guest = opt_params.get("guest", "linux")

        return {
            "vmid": opt_params.get("vmid"),
            "name": name,
            "memory_mib": memory_mib,
            "cores": cores,
            "sockets": sockets,
            "threads": threads,
            "cpu_type": cpu_type,
            "guest": guest,
            "disks": disks,
            "networks": networks,
            "boot": boot,
            "options": options,
        }
    
    def _map_cpu_mode(self, cpu_type: str) -> str:
        if cpu_type in ("host", "host-passthrough"):
            return "host-passthrough"
        if cpu_type in ("host-model", "default"):
            return "host-model"
        return "host-model"
    
    def _disk_target_from_slot(self, slot: str) -> tuple[str, str]:
        if not slot:
            raise ValueError("Disk slot is required")

        if re.match(r"^vd[a-z]+$", slot):
            return "virtio", slot

        if re.match(r"^sd[a-z]+$", slot):
            return "scsi", slot

        if re.match(r"^hd[a-z]+$", slot):
            return "ide", slot

        letters = "abcdefghijklmnopqrstuvwxyz"

        if slot.startswith("scsi"):
            index = int(slot.replace("scsi", ""))
            return "scsi", f"sd{letters[index]}"

        if slot.startswith("virtio"):
            index = int(slot.replace("virtio", ""))
            return "virtio", f"vd{letters[index]}"

        if slot.startswith("sata"):
            index = int(slot.replace("sata", ""))
            return "sata", f"sd{letters[index]}"

        if slot.startswith("ide"):
            index = int(slot.replace("ide", ""))
            return "ide", f"hd{letters[index]}"

        raise ValueError(f"Unsupported disk slot: {slot}")
        
    def _create_disk_volumes(self, vm_config: dict) -> list[dict]:
        created = []

        for disk in vm_config["disks"]:
            slot = disk.get("slot")
            storage_id = disk.get("storage_id")
            size_gb = disk.get("size_gb")
            disk_format = disk.get("format", "qcow2")

            if not slot:
                raise ValueError("Disk requires slot")
            if not storage_id:
                raise ValueError(f"Disk {slot} requires storage_id")
            if size_gb is None:
                raise ValueError(f"Disk {slot} requires size_gb")

            pool = self.conn.session.storagePoolLookupByName(storage_id)

            try:
                pool.refresh(0)
            except Exception:
                pass

            vol_name = f"{vm_config['name']}-{slot}.{disk_format}"

            try:
                pool.storageVolLookupByName(vol_name)
                raise ValueError(f"Volume '{vol_name}' already exists in pool '{storage_id}'")
            except libvirt.libvirtError:
                pass

            capacity_bytes = int(size_gb) * 1024 * 1024 * 1024

            volume_xml = f"""
            <volume>
                <name>{escape(vol_name)}</name>
                <capacity unit="bytes">{capacity_bytes}</capacity>
                <target>
                    <format type="{escape(disk_format)}"/>
                </target>
            </volume>
            """.strip()

            vol = pool.createXML(volume_xml, 0)
            if vol is None:
                raise RuntimeError(f"Failed to create volume for disk {slot}")

            bus, target_dev = self._disk_target_from_slot(slot)

            created.append({
                "slot": slot,
                "storage_id": storage_id,
                "path": vol.path(),
                "name": vol.name(),
                "format": disk_format,
                "bus": bus,
                "target_dev": target_dev,
                "controller_type": disk.get("controller_type"),
                "backup": disk.get("backup", True),
            })

        return created
    
    def _build_disks_xml(self, created_disks: list[dict]) -> str:
        xml_parts = []

        need_scsi_controller = any(d["bus"] == "scsi" for d in created_disks)

        if need_scsi_controller:
            controller_model = "virtio-scsi"
            for d in created_disks:
                if d.get("controller_type") == "virtio-scsi-single":
                    controller_model = "virtio-scsi"
                    break

            xml_parts.append(f"""
            <controller type='scsi' index='0' model='{controller_model}'/>
            """.strip())

        for disk in created_disks:
            xml_parts.append(f"""
            <disk type='file' device='disk'>
                <driver name='qemu' type='{escape(disk["format"])}'/>
                <source file='{escape(disk["path"])}'/>
                <target dev='{escape(disk["target_dev"])}' bus='{escape(disk["bus"])}'/>
            </disk>
            """.strip())

        return "\n".join(xml_parts)
    
    def _build_networks_xml(self, vm_config: dict) -> str:
        xml_parts = []

        for nic in vm_config["networks"]:
            if not nic.get("connected", True):
                continue

            slot = nic.get("slot")
            network_id = nic.get("network_id")
            model = nic.get("model", "virtio")
            mac = nic.get("mac")

            if not slot:
                raise ValueError("Network requires slot")
            if not network_id:
                raise ValueError(f"Network {slot} requires network_id")

            mac_xml = f"<mac address='{escape(mac)}'/>" if mac else ""

            xml_parts.append(f"""
            <interface type='bridge'>
                <source bridge='{escape(network_id)}'/>
                <model type='{escape(model)}'/>
                {mac_xml}
            </interface>
            """.strip())

        return "\n".join(xml_parts)
        
    def _build_boot_xml(self, vm_config: dict, boot_from_cdrom: bool = False) -> str:
        order = vm_config.get("boot", {}).get("order", [])

        if boot_from_cdrom:
            return """
            <boot dev='cdrom'/>
            <boot dev='hd'/>
            """.strip()

        if not order:
            return "<boot dev='hd'/>"

        first = order[0]

        if first.startswith(("scsi", "virtio", "sata", "ide")):
            return "<boot dev='hd'/>"

        return "<boot dev='hd'/>"
    
    def _build_cdrom_xml(self, storage_id: str, volume: str) -> str:
        return f"""
        <disk type='volume' device='cdrom'>
            <driver name='qemu' type='raw'/>
            <source pool='{escape(storage_id)}' volume='{escape(volume)}'/>
            <target dev='hdd' bus='ide'/>
            <readonly/>
        </disk>
        """.strip()
    
    def _build_domain_xml(
        self,
        vm_config: dict,
        disks_xml: str,
        networks_xml: str,
        boot_xml: str,
        cdrom_xml: str = "",
    ) -> str:
        name = escape(vm_config["name"])
        memory_mib = vm_config["memory_mib"]
        cores = vm_config["cores"]
        sockets = vm_config["sockets"]
        threads = vm_config["threads"]
        vcpus = cores * sockets * threads
        cpu_mode = escape(self._map_cpu_mode(vm_config["cpu_type"]))

        graphics = vm_config.get("options", {}).get("graphics", "default")

        graphics_xml = "<graphics type='vnc' autoport='yes' listen='0.0.0.0'/>"
        if graphics in (None, "none", "disabled"):
            graphics_xml = ""

        return f"""
        <domain type='kvm'>
            <name>{name}</name>
            <memory unit='MiB'>{memory_mib}</memory>
            <currentMemory unit='MiB'>{memory_mib}</currentMemory>
            <vcpu placement='static'>{vcpus}</vcpu>

            <cpu mode='{cpu_mode}'>
                <topology sockets='{sockets}' dies='1' cores='{cores}' threads='{threads}'/>
            </cpu>

            <os>
                <type arch='x86_64'>hvm</type>
                {boot_xml}
            </os>

            <features>
                <acpi/>
                <apic/>
            </features>

            <devices>
                <emulator>/usr/bin/qemu-system-x86_64</emulator>

                {disks_xml}
                {cdrom_xml}
                {networks_xml}

                {graphics_xml}

                <video>
                    <model type='virtio'/>
                </video>
            </devices>
        </domain>
        """.strip()
    
    def _create_vm_base(self, node_id, opt_params: dict, source: dict | None):
        vm_config = self._parse_vm_config(opt_params)

        if not vm_config["disks"]:
            raise ValueError("At least one disk is required")

        created_disks = self._create_disk_volumes(vm_config)

        disks_xml = self._build_disks_xml(created_disks)
        networks_xml = self._build_networks_xml(vm_config)

        iso_storage_id = None
        iso_volume = None

        if source and source.get("type") == "iso":
            iso_storage_id = source.get("storage_id")
            iso_volume = source.get("path")

            if not iso_storage_id:
                raise ValueError("ISO source requires storage_id")

            if not iso_volume:
                raise ValueError("ISO source requires path")

            pool = self.conn.session.storagePoolLookupByName(iso_storage_id)

            try:
                pool.refresh(0)
            except Exception:
                pass

            pool.storageVolLookupByName(iso_volume)


        boot_xml = self._build_boot_xml(vm_config, boot_from_cdrom=bool(iso_volume))
        cdrom_xml = (
            self._build_cdrom_xml(iso_storage_id, iso_volume)
            if iso_storage_id and iso_volume
            else ""
        )

        domain_xml = self._build_domain_xml(
            vm_config=vm_config,
            disks_xml=disks_xml,
            networks_xml=networks_xml,
            boot_xml=boot_xml,
            cdrom_xml=cdrom_xml,
        )

        dom = self.conn.session.defineXML(domain_xml)
        if dom is None:
            raise RuntimeError("Failed to define VM")

        start_after_create = vm_config["options"].get("start_after_create", False)
        autostart = vm_config["options"].get("autostart", False)

        if autostart:
            dom.setAutostart(1)

        status = "defined"
        if start_after_create:
            dom.create()
            status = "running"

        return {
            "success": True,
            "name": dom.name(),
            "uuid": dom.UUIDString(),
            "status": status,
            "iso_path": iso_path,
            "disks": created_disks,
        }
    

    def _get_vm_disk_summary(self, dom):
        raw_xml = dom.XMLDesc()
        xml = minidom.parseString(raw_xml)

        total_capacity = 0
        total_allocated = 0

        for disk in xml.getElementsByTagName("disk"):
            if disk.getAttribute("device") != "disk":
                continue

            target = disk.getElementsByTagName("target")[0]
            dev = target.getAttribute("dev")

            try:
                capacity, allocation, physical = dom.blockInfo(dev, 0)
            except Exception:
                continue

            total_capacity += capacity
            total_allocated += allocation

        return  total_capacity, total_allocated, total_capacity - total_allocated
    
    def _get_vm_cpu_config(self, xml) -> dict:
        domain = xml.documentElement

        vcpu_count = None
        vcpu_nodes = domain.getElementsByTagName("vcpu")
        if vcpu_nodes and vcpu_nodes[0].firstChild:
            try:
                vcpu_count = int(vcpu_nodes[0].firstChild.nodeValue)
            except (ValueError, TypeError):
                vcpu_count = None

        cpu_type = None
        sockets = None
        cores = None

        cpu_nodes = domain.getElementsByTagName("cpu")
        if cpu_nodes:
            cpu_node = cpu_nodes[0]

            if cpu_node.hasAttribute("mode"):
                cpu_type = cpu_node.getAttribute("mode")
            elif cpu_node.hasAttribute("match"):
                cpu_type = cpu_node.getAttribute("match")

            topo_nodes = cpu_node.getElementsByTagName("topology")
            if topo_nodes:
                topo = topo_nodes[0]

                if topo.hasAttribute("sockets"):
                    try:
                        sockets = int(topo.getAttribute("sockets"))
                    except ValueError:
                        sockets = None

                if topo.hasAttribute("cores"):
                    try:
                        cores = int(topo.getAttribute("cores"))
                    except ValueError:
                        cores = None

        # fallback: když topology není
        if sockets is None:
            sockets = 1 if vcpu_count else None

        if cores is None and vcpu_count is not None:
            cores = vcpu_count

        return {
            "cores": cores,
            "sockets": sockets,
            "type": cpu_type,
        }
    
    def _get_vm_boot_config(self, xml) -> dict:
        domain = xml.documentElement

        order = []
        firmware = "default"
        machine = "default"

        os_nodes = domain.getElementsByTagName("os")
        if os_nodes:
            os_node = os_nodes[0]

            type_nodes = os_node.getElementsByTagName("type")
            if type_nodes:
                type_node = type_nodes[0]
                if type_node.hasAttribute("machine"):
                    machine = type_node.getAttribute("machine")

            if os_node.hasAttribute("firmware"):
                firmware = os_node.getAttribute("firmware")

            boot_nodes = os_node.getElementsByTagName("boot")
            for boot_node in boot_nodes:
                if boot_node.hasAttribute("dev"):
                    order.append(boot_node.getAttribute("dev"))

            loader_nodes = os_node.getElementsByTagName("loader")
            if loader_nodes and loader_nodes[0].firstChild:
                loader_path = loader_nodes[0].firstChild.nodeValue.strip()
                if "OVMF" in loader_path or "ovmf" in loader_path:
                    firmware = "uefi"
                elif firmware == "default":
                    firmware = "bios"

        return {
            "order": order,
            "firmware": firmware,
            "machine": machine,
        }
    
    def _get_vm_options_config(self, xml, vm) -> dict:
        graphics = "default"

        graphics_nodes = xml.getElementsByTagName("graphics")
        if graphics_nodes:
            g = graphics_nodes[0]
            if g.hasAttribute("type"):
                graphics = g.getAttribute("type")

        return {
            "autostart": bool(vm.autostart()),
            "graphics": graphics,
        }
    
    def _get_vm_networks_config(self, xml) -> list[dict]:
        networks = []

        for idx, iface in enumerate(xml.getElementsByTagName("interface")):
            iface_type = iface.getAttribute("type")

            mac = None
            mac_nodes = iface.getElementsByTagName("mac")
            if mac_nodes and mac_nodes[0].hasAttribute("address"):
                mac = mac_nodes[0].getAttribute("address")

            model = None
            model_nodes = iface.getElementsByTagName("model")
            if model_nodes and model_nodes[0].hasAttribute("type"):
                model = model_nodes[0].getAttribute("type")

            source_nodes = iface.getElementsByTagName("source")
            source = source_nodes[0] if source_nodes else None

            network_id = None
            connected = True

            if source:
                if source.hasAttribute("bridge"):
                    network_id = source.getAttribute("bridge")
                elif source.hasAttribute("network"):
                    network_id = source.getAttribute("network")
                elif source.hasAttribute("dev"):
                    network_id = source.getAttribute("dev")

            link_nodes = iface.getElementsByTagName("link")
            if link_nodes and link_nodes[0].hasAttribute("state"):
                connected = link_nodes[0].getAttribute("state") != "down"

            networks.append({
                "slot": f"net{idx}",
                "network_id": network_id,
                "model": model,
                "mac": mac,
                "connected": connected,
            })

        return networks
    
    def _get_vm_disks_and_cdroms(self, xml) -> tuple[list[dict], list[dict]]:
        disks = []
        cdroms = []

        disk_index = 0
        cdrom_index = 0

        for disk in xml.getElementsByTagName("disk"):
            device_type = disk.getAttribute("device") or "disk"
            disk_type = disk.getAttribute("type") or None

            target_nodes = disk.getElementsByTagName("target")
            target = target_nodes[0] if target_nodes else None

            target_dev = target.getAttribute("dev") if target and target.hasAttribute("dev") else None
            target_bus = target.getAttribute("bus") if target and target.hasAttribute("bus") else None

            source_nodes = disk.getElementsByTagName("source")
            source = source_nodes[0] if source_nodes else None

            storage_id = None
            volume = None
            size_gb = None

            # zjistit source
            source_path = None
            if source:
                for attr in ("file", "dev", "name", "volume"):
                    if source.hasAttribute(attr):
                        source_path = source.getAttribute(attr)
                        break

            # pokus o dohledání pool/volume + velikosti
            if disk_type == "file" and source and source.hasAttribute("file"):
                file_path = source.getAttribute("file")
                volume = file_path.split("/")[-1]

                try:
                    vol = self.conn.session.storageVolLookupByPath(file_path)
                    vol_xml = minidom.parseString(vol.XMLDesc())

                    cap_nodes = vol_xml.getElementsByTagName("capacity")
                    if cap_nodes and cap_nodes[0].firstChild:
                        try:
                            size_bytes = int(cap_nodes[0].firstChild.nodeValue)
                            size_gb = round(size_bytes / (1024 ** 3))
                        except (ValueError, TypeError):
                            size_gb = None

                    pool = vol.storagePoolLookupByVolume()
                    pool_xml = minidom.parseString(pool.XMLDesc())
                    pool_name_nodes = pool_xml.getElementsByTagName("name")
                    if pool_name_nodes and pool_name_nodes[0].firstChild:
                        storage_id = pool_name_nodes[0].firstChild.nodeValue

                except libvirt.libvirtError:
                    pass

            elif disk_type == "volume" and source:
                if source.hasAttribute("pool"):
                    storage_id = source.getAttribute("pool")

                if source.hasAttribute("volume"):
                    volume = source.getAttribute("volume")

                if storage_id and volume:
                    try:
                        pool = self.conn.session.storagePoolLookupByName(storage_id)
                        vol = pool.storageVolLookupByName(volume)
                        vol_xml = minidom.parseString(vol.XMLDesc())

                        cap_nodes = vol_xml.getElementsByTagName("capacity")
                        if cap_nodes and cap_nodes[0].firstChild:
                            size_bytes = int(cap_nodes[0].firstChild.nodeValue)
                            size_gb = round(size_bytes / (1024 ** 3))

                    except libvirt.libvirtError:
                        size_gb = None

            item = {
                "slot": target_dev or (f"{target_bus}{disk_index}" if target_bus else f"disk{disk_index}"),
                "storage_id": storage_id,
                "volume": volume or source_path,
                "size_gb": size_gb,
                "controller_type": target_bus,
            }

            if device_type == "cdrom":
                cdroms.append(item)
                cdrom_index += 1
            else:
                disks.append(item)
                disk_index += 1

        return disks, cdroms
