from platforms.base.vm import BaseVmApi
from pyVmomi import vim
from pyVim.task import WaitForTask
from datetime import datetime, timezone, timedelta
import os 
import time
import requests
import tarfile
import shutil
import re
from config import BACKUP_ROOT
import tempfile

VMX_PATTERN = re.compile(r'/vmfs/volumes/.+?/(?P<vmname>[^/]+)/[^ ]+\.vmx')
OPID_PATTERN = re.compile(r'opID=([a-zA-Z0-9\-]+)')

class EsxiVmApi(BaseVmApi):

    ESXI_GUEST_MAP = {
        "linux24": "otherLinux64Guest",
        "linux26": "otherLinux64Guest",
        "windows10": "windows9_64Guest",
        "windows11": "windows11_64Guest",
    }

    def __init__(self, connection):
        self.conn = connection

    def get_vm_capabilities(self) -> dict:
        """
        Vrací schopnosti ESXi VM API.

        Definuje podporované typy zdrojů, OS, disků, sítí,
        boot parametrů a dalších možností při vytváření VM.

        Returns:
            Struktura popisující capabilities.
        """
        return {
            "source_types": ["empty", "iso", "backup"],

            "guest": {
                "types": ["linux24", "linux", "windows-modern", "windows-latest", "other32", "other64"],
                "default": "other64",
            },

            "disk": {
                "buses": ["scsi", "sata", "ide"],
                "controllers": ["default"],
                "default_bus": "scsi",
                "default_controller": "default",
            },

            "network": {
                "models": ["e1000", "vmxnet3"],
                "default_model": "vmxnet3",
            },

            "boot": {
                "firmware": ["default", "bios", "efi"],
                "machines": ["default"],
                "secure_boot": False,
            },

            "graphics": {
                "models": ["default"],
                "default": "default",
            },

            "options": {
                "start_after_create": True
            }
        }

    def create_vm(self, node: str, opt_params: dict) -> dict:
        """
        Vytvoří virtuální stroj na ESXi hostu.

        Podporuje vytvoření:
            - z prázdného stavu
            - z ISO
            - z backupu (OVA/OVF)

        Args:
            node: MoID hosta.
            opt_params: Konfigurační parametry VM.

        Returns:
            Výsledek operace (success, vmid, name, status).

        Raises:
            ValueError: Neplatné parametry nebo nenalezený host/datastore.
            RuntimeError: Selhání při vytváření VM.
        """
        def create_vm_from_backup(
            source: dict,
            opt_params: dict,
            host: vim.HostSystem,
            resource_pool: vim.ResourcePool,
            vm_folder: vim.Folder,
        ):
            
            import pprint

            pprint.pprint(opt_params)
            
            rel_path = source.get("path")
            if not rel_path:
                raise ValueError("Backup requires source.path")

            backup_path = os.path.normpath(os.path.join(BACKUP_ROOT, rel_path))

            if not os.path.isdir(backup_path):
                raise ValueError(f"ESXi folder backup does not exist: {backup_path}")

            vm_name = opt_params.get("name") or source.get("name")
            if not vm_name:
                raise ValueError("Imported VM requires name")

            host_datastores = list(getattr(host, "datastore", []) or [])
            if not host_datastores:
                raise ValueError(f"Host '{host.name}' has no accessible datastore")

            datastore = next(
                (ds for ds in host_datastores if ds.name.lower() == "local"),
                host_datastores[0],
            )
            datastore_name = datastore.name

            esxi_host = self.conn.host.replace("https://", "").replace("http://", "").rstrip("/")
            session_cookie = self.conn.si._stub.cookie

            session = requests.Session()
            session.verify = False
            session.headers.update({"Cookie": session_cookie})

            target_folder = vm_name

            # 1) upload všech souborů backup složky do datastore
            for file_name in os.listdir(backup_path):
                local_file = os.path.join(backup_path, file_name)

                if not os.path.isfile(local_file):
                    continue

                remote_path = f"{target_folder}/{file_name}"

                upload_url = (
                    f"https://{esxi_host}/folder/{remote_path}"
                    f"?dcPath=ha-datacenter&dsName={datastore_name}"
                )

                with open(local_file, "rb") as f:
                    response = session.put(
                        upload_url,
                        data=f,
                        headers={"Content-Length": str(os.path.getsize(local_file))},
                        timeout=(30, 600),
                    )
                    response.raise_for_status()

            # 2) najít VMX soubor
            vmx_files = [
                f for f in os.listdir(backup_path)
                if f.lower().endswith(".vmx")
            ]

            if not vmx_files:
                raise ValueError("Backup folder does not contain .vmx file")

            vmx_name = vmx_files[0]
            datastore_vmx_path = f"[{datastore_name}] {target_folder}/{vmx_name}"

            # 3) register VM
            task = vm_folder.RegisterVM_Task(
                path=datastore_vmx_path,
                name=vm_name,
                asTemplate=False,
                pool=resource_pool,
                host=host,
            )
            WaitForTask(task)

            vm = self.conn.get_entity_by_name(vm_name, vim.VirtualMachine)

            options = opt_params.get("options", {})
            if vm and options.get("start_after_create"):
                power_task = vm.PowerOnVM_Task()
                WaitForTask(power_task)

            return {
                "success": True,
                "data": {
                    "vmid": getattr(vm, "_moId", None) if vm else None,
                    "name": vm_name,
                    "status": "imported",
                }
            }

        def create_vm_from_scratch(
            source: dict,
            opt_params: dict,
            host: vim.HostSystem,
            resource_pool: vim.ResourcePool,
            vm_folder: vim.Folder,
        ):
            
            disks = opt_params.get("disks", []) or []
            source = source or {}

            datastore_id = None

            if disks and disks[0].get("storage_id"):
                datastore_id = disks[0].get("storage_id")
            elif source.get("type") == "iso" and source.get("storage_id"):
                datastore_id = source.get("storage_id")
            else:
                datastore_id = opt_params.get("storage_id")

            datastore = self.conn.get_entity_by_moid(datastore_id, vim.Datastore)
            if not datastore:
                raise ValueError("Datastore not found")

            host_datastore_names = {ds.name for ds in getattr(host, "datastore", [])}
            if datastore.name not in host_datastore_names:
                raise ValueError(
                    f"Datastore '{datastore.name}' is not accessible from host '{host.name}'"
                )

            name = opt_params.get("name")
            if not name:
                raise ValueError("name is required")

            cpu = opt_params.get("cpu", {})
            cores = int(cpu.get("cores", 1))
            sockets = int(cpu.get("sockets", 1))
            memory_mb = int(opt_params.get("memory_mb", 1024))

            guest = opt_params.get("guest")
            guest_id = self.ESXI_GUEST_MAP.get(
                guest,
                opt_params.get("guest_id", "otherLinux64Guest")
            )
            vm_version = opt_params.get("compatibility_version", "vmx-19")

            disks = opt_params.get("disks", [])
            networks = opt_params.get("networks", [])

            config = vim.vm.ConfigSpec()
            config.name = name
            config.numCPUs = cores * sockets
            config.numCoresPerSocket = cores
            config.memoryMB = memory_mb
            config.guestId = guest_id
            config.version = vm_version
            config.files = vim.vm.FileInfo(vmPathName=f"[{datastore.name}]")

            device_changes = []
            controllers = {}
            next_keys = {
                "scsi": 1000,
                "sata": 15000,
                "ide": 200,
            }
            next_units = {}

            scsi_classes = {
                "lsiLogic": vim.vm.device.VirtualLsiLogicController,
                "lsiLogicSAS": vim.vm.device.VirtualLsiLogicSASController,
                "paravirtual": vim.vm.device.ParaVirtualSCSIController,
            }

            def ensure_controller(bus: str, controller_type: str | None = None):
                controller_aliases = {
                    "virtio-scsi-single": "paravirtual",
                    "virtio-scsi": "paravirtual",
                    "lsi-sas": "lsiLogicSAS",
                    "lsisas": "lsiLogicSAS",
                    "default": "lsiLogic",
                }

                normalized_controller_type = controller_aliases.get(
                    controller_type,
                    controller_type
                )

                key_name = f"{bus}:{normalized_controller_type or ''}"

                if key_name in controllers:
                    return controllers[key_name]

                if bus == "scsi":
                    scsi_classes = {
                        "lsiLogic": vim.vm.device.VirtualLsiLogicController,
                        "lsiLogicSAS": vim.vm.device.VirtualLsiLogicSASController,
                        "paravirtual": vim.vm.device.ParaVirtualSCSIController,
                    }

                    controller_cls = scsi_classes.get(normalized_controller_type or "lsiLogic")
                    if not controller_cls:
                        raise ValueError(
                            "Unsupported scsi controller type. Use 'lsiLogic', "
                            "'lsiLogicSAS', or 'paravirtual'"
                        )

                    controller = controller_cls()
                    controller_key = next_keys["scsi"]
                    controller.busNumber = 0
                    controller.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing
                    next_keys["scsi"] += 1

                elif bus == "sata":
                    controller = vim.vm.device.VirtualAHCIController()
                    controller_key = next_keys["sata"]
                    controller.busNumber = 0
                    next_keys["sata"] += 1

                elif bus == "ide":
                    controller = vim.vm.device.VirtualIDEController()
                    controller_key = next_keys["ide"]
                    controller.busNumber = 0
                    next_keys["ide"] += 1

                else:
                    raise ValueError("Unsupported bus type. Use 'scsi', 'sata', or 'ide'")

                controller_spec = vim.vm.device.VirtualDeviceSpec()
                controller_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                controller_spec.device = controller
                controller_spec.device.key = controller_key
                device_changes.append(controller_spec)

                controllers[key_name] = controller_key
                next_units[controller_key] = 0
                return controller_key

            # disks
            for disk in disks:
                size_gb = disk.get("size_gb")
                if size_gb is None:
                    raise ValueError("Disk requires size_gb")

                size_gb = int(size_gb)
                bus = disk.get("bus", "scsi").lower()
                controller_type = disk.get("controller_type")
                disk_type = disk.get("disk_type", "thin").lower()

                controller_key = ensure_controller(bus, controller_type)
                unit_number = next_units[controller_key]

                disk_spec = vim.vm.device.VirtualDeviceSpec()
                disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                disk_spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create
                disk_spec.device = vim.vm.device.VirtualDisk()
                disk_spec.device.key = 0
                disk_spec.device.controllerKey = controller_key
                disk_spec.device.unitNumber = unit_number
                disk_spec.device.capacityInKB = size_gb * 1024 * 1024

                backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
                backing.diskMode = "persistent"
                backing.datastore = datastore

                if disk_type == "thin":
                    backing.thinProvisioned = True
                    backing.eagerlyScrub = False
                elif disk_type == "thick":
                    backing.thinProvisioned = False
                    backing.eagerlyScrub = False
                elif disk_type == "eagerzeroedthick":
                    backing.thinProvisioned = False
                    backing.eagerlyScrub = True
                else:
                    raise ValueError(
                        "Unsupported disk_type. Use 'thin', 'thick', or 'eagerzeroedthick'"
                    )

                disk_spec.device.backing = backing
                device_changes.append(disk_spec)
                next_units[controller_key] += 1

            # iso
            if source.get("type") == "iso":
                iso_storage_id = source.get("storage_id") or opt_params.get("storage_id")
                if not iso_storage_id:
                    raise ValueError("ISO requires storage_id")

                iso_datastore = self.conn.get_entity_by_moid(iso_storage_id, vim.Datastore)
                if not iso_datastore:
                    raise ValueError("ISO datastore not found")

                if iso_datastore.name not in host_datastore_names:
                    raise ValueError(
                        f"Datastore '{iso_datastore.name}' is not accessible from host '{host.name}'"
                    )

                iso_path = source.get("path")
                if not iso_path:
                    raise ValueError("ISO source requires path")

                iso_bus = source.get("bus", "sata").lower()
                if iso_bus not in ("sata", "ide"):
                    raise ValueError("ISO bus must be 'sata' or 'ide'")

                controller_key = ensure_controller(iso_bus)
                unit_number = next_units[controller_key]

                cdrom_spec = vim.vm.device.VirtualDeviceSpec()
                cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                cdrom_spec.device = vim.vm.device.VirtualCdrom()
                cdrom_spec.device.controllerKey = controller_key
                cdrom_spec.device.unitNumber = unit_number
                cdrom_spec.device.key = -1

                cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
                cdrom_spec.device.backing.fileName = f"[{iso_datastore.name}] {iso_path}"

                cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                cdrom_spec.device.connectable.startConnected = True
                cdrom_spec.device.connectable.connected = True
                cdrom_spec.device.connectable.allowGuestControl = True

                device_changes.append(cdrom_spec)
                next_units[controller_key] += 1

            # networks
            for nic in networks:
                if nic.get("connected", True) is False:
                    continue

                network_name = nic.get("network") or nic.get("network_id")
                if not network_name:
                    raise ValueError("Network requires 'network' or 'network_id'")

                network = self.conn.get_entity_by_name(network_name, vim.Network)
                if not network:
                    raise ValueError(f"Network '{network_name}' not found")

                host_network_names = {net.name for net in getattr(host, "network", [])}
                if network.name not in host_network_names:
                    raise ValueError(
                        f"Network '{network.name}' is not accessible from host '{host.name}'"
                    )

                model = (nic.get("model") or "vmxnet3").lower()
                if model == "e1000":
                    nic_device = vim.vm.device.VirtualE1000()
                elif model == "e1000e":
                    nic_device = vim.vm.device.VirtualE1000e()
                else:
                    nic_device = vim.vm.device.VirtualVmxnet3()

                nic_spec = vim.vm.device.VirtualDeviceSpec()
                nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                nic_spec.device = nic_device
                nic_spec.device.wakeOnLanEnabled = True
                nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                nic_spec.device.backing.network = network
                nic_spec.device.backing.deviceName = network.name
                nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nic_spec.device.connectable.startConnected = True
                nic_spec.device.connectable.allowGuestControl = True

                mac = nic.get("mac")
                if mac:
                    nic_spec.device.addressType = "manual"
                    nic_spec.device.macAddress = mac

                device_changes.append(nic_spec)

            config.deviceChange = device_changes

            task = vm_folder.CreateVM_Task(config=config, pool=resource_pool, host=host)
            WaitForTask(task)

            vm = task.info.result

            options = opt_params.get("options", {})
            if options.get("start_after_create"):
                power_task = vm.PowerOnVM_Task()
                WaitForTask(power_task)

            return {
                "success": True,
                "data": {
                    "vmid": getattr(vm, "_moId", None),
                    "name": vm.name,
                    "status": "created",
                }
            }

        host = self.conn.get_entity_by_moid(node, vim.HostSystem)
        if not host:
            raise ValueError(f"Host '{node}' not found")

        current = getattr(host, "parent", None)
        dc = None

        while current:
            if isinstance(current, vim.Datacenter):
                dc = current
                break
            current = getattr(current, "parent", None)

        if not dc:
            dc = next(self.conn.get_container_view([vim.Datacenter]), None)

        if not dc:
            raise ValueError("Datacenter for host not found")

        parent = getattr(host, "parent", None)
        resource_pool = getattr(parent, "resourcePool", None)

        if not resource_pool and isinstance(parent, vim.ComputeResource):
            resource_pool = parent.resourcePool

        if not resource_pool:
            raise ValueError("Default resource pool not found")

        vm_folder = dc.vmFolder
        source = opt_params.get("source", {}) or {}
        source_type = source.get("type")

        if source_type == "backup":
            return create_vm_from_backup(
                source=source,
                opt_params=opt_params,
                host=host,
                resource_pool=resource_pool,
                vm_folder=vm_folder,
            )

        if source_type in (None, "", "iso"):
            return create_vm_from_scratch(
                source=source,
                opt_params=opt_params,
                host=host,
                resource_pool=resource_pool,
                vm_folder=vm_folder,
            )

        raise ValueError(f"Unsupported source.type: {source_type}")
    

    def _load_ovf_descriptor_and_files(self, path: str):
        backup_root = os.path.join(BACKUP_ROOT, "esxi")

        full_path = os.path.normpath(os.path.join(BACKUP_ROOT, path))

        if not full_path.startswith(os.path.normpath(BACKUP_ROOT) + os.sep):
            raise ValueError("Invalid backup path")

        if not os.path.exists(full_path):
            raise ValueError(f"Backup file '{full_path}' does not exist")

        if full_path.lower().endswith(".ova"):
            extract_dir = tempfile.mkdtemp(prefix="esxi_ova_")

            with tarfile.open(full_path, "r") as tar:
                tar.extractall(extract_dir)

            ovf_files = [
                os.path.join(extract_dir, f)
                for f in os.listdir(extract_dir)
                if f.lower().endswith(".ovf")
            ]

            if not ovf_files:
                raise ValueError("OVA does not contain OVF descriptor")

            ovf_path = ovf_files[0]

            with open(ovf_path, "r", encoding="utf-8") as f:
                ovf_descriptor = f.read()

            disk_files = {
                f: os.path.join(extract_dir, f)
                for f in os.listdir(extract_dir)
                if f.lower().endswith((".vmdk", ".iso"))
            }

            return ovf_descriptor, disk_files

        if full_path.lower().endswith(".ovf"):
            with open(full_path, "r", encoding="utf-8") as f:
                ovf_descriptor = f.read()

            base_dir = os.path.dirname(full_path)

            disk_files = {
                f: os.path.join(base_dir, f)
                for f in os.listdir(base_dir)
                if f.lower().endswith((".vmdk", ".iso"))
            }

            return ovf_descriptor, disk_files

        raise ValueError("Unsupported backup format")

    def get_vm_status(self, node, vmid: str, params) -> dict:
        """
            Získá aktuální stav virtuálního stroje.

            Vrací informace o:
                - uptime
                - CPU (počet, sockety, využití)
                - paměti
                - disku

            Args:
                node: MoID hosta.
                vmid: MoID virtuálního stroje.
                params: Další parametry (nevyužito).

            Returns:
                dict: Stav VM.

            Raises:
                ValueError: Pokud VM nebo host neexistuje.
        """
        host = self.conn.get_entity_by_moid(node, vim.HostSystem)

        if not host:
            raise ValueError(f"Host '{node}' not found")

        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
        
        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        runtime_host = getattr(getattr(vm, "runtime", None), "host", None)

        if runtime_host and getattr(runtime_host, "_moId", None) != getattr(host, "_moId", None):
            raise ValueError(
                f"VM '{vmid}' does not belong to host '{node}'"
            )

        summary = getattr(vm, "summary", None)
        runtime = getattr(vm, "runtime", None)

        uptime = None
        boot_time = getattr(getattr(summary, "runtime", None), "bootTime", None)
        if boot_time:
            now = datetime.now(timezone.utc)
            if boot_time.tzinfo is None:
                boot_time = boot_time.replace(tzinfo=timezone.utc)
            uptime = int((now - boot_time).total_seconds())

        cpu_total = getattr(vm.summary.config, "numCpu", None)
        cores_per_socket = getattr(vm.config.hardware, "numCoresPerSocket", None)

        cpu_sockets = None

        if cpu_total and cores_per_socket:
            cpu_sockets = int(cpu_total / cores_per_socket)

        cpu_usage = getattr(getattr(summary, "quickStats", None), "overallCpuUsage", None)
        cpu_usage_percent = None

        if cpu_usage is not None:
            num_cpu = getattr(summary.config, "numCpu", 0)

            host = getattr(runtime, "host", None)
            cpu_mhz_per_core = None

            if host:
                cpu_mhz_per_core = getattr(
                    getattr(host, "summary", None),
                    "hardware",
                    None
                ).cpuMhz

            if cpu_mhz_per_core and num_cpu:
                max_cpu_mhz = cpu_mhz_per_core * num_cpu
                cpu_usage_percent = (cpu_usage / max_cpu_mhz) 


        # Memory
        memory_total = None
        memory_total_mb = getattr(getattr(summary, "config", None), "memorySizeMB", None)

        if memory_total_mb is not None:
            memory_total = int(memory_total_mb) * 1024 * 1024

        quick_stats = getattr(summary, "quickStats", None)

        memory_used_mb = getattr(quick_stats, "guestMemoryUsage", None)
        if memory_used_mb is None:
            memory_used_mb = getattr(quick_stats, "hostMemoryUsage", None)

        memory_used = (
            int(memory_used_mb) * 1024 * 1024
            if memory_used_mb is not None
            else None
        )

        memory_free = None
        if memory_total is not None and memory_used is not None:
            memory_free = max(memory_total - memory_used, 0)

        # Disk
        disk_used = None
        disk_free = None

        disk_total = 0

        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                if device.capacityInKB is not None:
                    disk_total += int(device.capacityInKB) * 1024

        disk_used = getattr(vm.summary.storage, "committed", None)
        disk_free = disk_total - disk_used

        return {
            "uptime": uptime,
            "cpu_num": cpu_total,
            "cpu_sockets": cpu_sockets,
            "cpu_usage": cpu_usage_percent,    
            "memory_total": memory_total,
            "memory_used": memory_used,
            "memory_free": memory_free,
            "disk_total": disk_total,
            "disk_free": disk_free,
            "disk_used": disk_used,
        }
    

    def set_vm_status(self, node: str, vmid: str, status: str) -> dict:
        """
            Změní napájecí stav virtuálního stroje.

            Podporované operace:
                - start / resume
                - stop
                - shutdown
                - reboot
                - reset
                - suspend

            Args:
                node: MoID hosta.
                vmid: MoID virtuálního stroje.
                status: Požadovaná akce.

            Raises:
                ValueError: Pokud VM neexistuje.
                RuntimeError: Pokud operace selže.
        """
          
        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)

        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        power_state = vm.runtime.powerState

        try:

            if status in ["start", "resume"]:
                if power_state != vim.VirtualMachinePowerState.poweredOn:
                    task = vm.PowerOnVM_Task()

            elif status == "stop":
                if power_state != vim.VirtualMachinePowerState.poweredOff:
                    task = vm.PowerOffVM_Task()

            elif status == "shutdown":
                try:
                    vm.ShutdownGuest()
                except Exception:
                    task = vm.PowerOffVM_Task()

            elif status == "reboot":
                try:
                    vm.RebootGuest()
                except Exception:
                    task = vm.ResetVM_Task()

            elif status == "reset":
                task = vm.ResetVM_Task()

            elif status == "suspend":
                task = vm.SuspendVM_Task()

            if task is not None:
                WaitForTask(task)

        except Exception as e:
            raise RuntimeError(f"Failed to perform '{status}' on VM '{vmid}': {e}")
    
    def get_vm_time_metrics(self, node_id: str, vm_id: str, params: dict) -> list[dict]:
        """
        Získá časové metriky VM z vSphere Performance Manageru.

        Podporované metriky:
            - cpu_usage
            - memory_used
            - net_in / net_out
            - disk_read / disk_write
            - swap_used

        Args:
            node_id: ID hosta.
            vm_id: ID VM.
            params: Parametry (fields, timeframe, cf).

        Returns:
            Časová řada metrik.

        Raises:
            ValueError: Neplatné parametry nebo VM neexistuje.
        """
        if not vm_id:
            raise ValueError("vm_id is required")

        fields = params.get("fields") or []
        interval = params.get("timeframe", "hour")
        cf = params.get("cf", "AVERAGE")

        vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vm_id}' not found")

        perf_manager = self.conn.content.perfManager

        metric_map = {
            "cpu_usage": "cpu.usagemhz",         
            "memory_used": "mem.consumed",    
            "net_in": "net.received",          
            "net_out": "net.transmitted",     
            "swap_used": "mem.swapped",        
            "disk_read": "disk.read",         
            "disk_write": "disk.write",      
        }

        fields = fields or list(metric_map.keys())

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

        provider = perf_manager.QueryPerfProviderSummary(entity=vm)

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

        counter_lookup = {
            f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType}": c
            for c in perf_manager.perfCounter
        }

        metric_ids = []
        reverse_map = {}

        for alias in fields:
            base_name = metric_map.get(alias)
            if not base_name:
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
            entity=vm,
            metricId=metric_ids,
            intervalId=interval_id,
            startTime=start_time,
            endTime=end_time,
        )

        results = perf_manager.QueryPerf(querySpec=[query])
        if not results:
            return []

        raw = results[0]

        data = {}
        for sample in raw.sampleInfo:
            ts = int(sample.timestamp.timestamp())
            data[ts] = {"time": ts}

        runtime = vm.summary.runtime
        cpu_capacity = getattr(runtime, "maxCpuUsage", None)

        def normalize_value(field: str, value):
            if value is None:
                return None

    
            if isinstance(value, (int, float)) and value < 0:
                return None

            if field == "cpu_usage":
                # cpu.usage.average je percento -> chceme ratio 0-1
                return float(value) / cpu_capacity if cpu_capacity else float(v)

            if field in {"memory_used", "swap_used"}:
                # KB -> bytes
                return int(value) * 1024

            if field in {"net_in", "net_out", "disk_read", "disk_write"}:
                # KBps -> bytes/s
                return float(value) * 1024.0

            return value

        for series in raw.value:
            field = reverse_map.get(series.id.counterId)
            if not field:
                continue

            for i, v in enumerate(series.value):
                ts = int(raw.sampleInfo[i].timestamp.timestamp())
                data[ts][field] = normalize_value(field, v)

        result = []
        for ts in sorted(data.keys()):
            point = {"time": ts}
            for field in fields:
                if field in data[ts]:
                    point[field] = data[ts][field]
            result.append(point)

        return result

    
    def manage_vm_snapshots(self, node: str, vmid: str, snap_parameters: dict | None = None) -> dict | list[dict]:
        """
        Správa snapshotů virtuálního stroje.

        - Pokud snap_parameters existují → vytvoří snapshot
        - Jinak → vrátí seznam snapshotů

        Args:
            node: MoID hosta.
            vmid: MoID VM.
            snap_parameters: Parametry snapshotu.

        Returns:
            Seznam snapshotů (pokud není create).

        Raises:
            ValueError: Pokud VM neexistuje nebo chybí název snapshotu.
        """
        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)

        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        if snap_parameters:
            name = snap_parameters.get("snapname") or snap_parameters.get("snapshotname") or snap_parameters.get("name")
            if not name:
                raise ValueError("Snapshot name is required")

            description = snap_parameters.get("description", "")
            memory = snap_parameters.get("vmstate", snap_parameters.get("vm_state", False))

            requested_quiesce = snap_parameters.get("quiesce", False)
            tools_status = getattr(getattr(vm, "guest", None), "toolsStatus", None)
            tools_available = tools_status in ("toolsOk", "toolsOld")
            quiesce = requested_quiesce and tools_available

            task = vm.CreateSnapshot_Task(
                name=name,
                description=description,
                memory=memory,
                quiesce=quiesce,
            )
            WaitForTask(task)

            return

        snapshot_info = getattr(vm, "snapshot", None)
        root_list = getattr(snapshot_info, "rootSnapshotList", None)

        if not snapshot_info or not root_list:
            return [{
                "id": "current",
                "name": "current",
                "description": "Current VM state",
                "snaptime": None,
                "parent": None,
                "parent_id": None,
                "running": 1,
                "is_current": True,
            }]

        result = []
        current_snapshot = getattr(snapshot_info, "currentSnapshot", None)
        current_snapshot_id = getattr(current_snapshot, "_moId", None)

        stack = [(snap, None, None) for snap in root_list]

        while stack:
            snap, parent_name, parent_id = stack.pop()
            snap_ref = getattr(snap, "snapshot", None)

            snap_id = getattr(snap_ref, "_moId", None) or getattr(snap, "name", None)
            snap_name = getattr(snap, "name", None)

            item = {
                "id": snap_id,
                "name": snap_name,
                "description": getattr(snap, "description", None),
                "snaptime": int(snap.createTime.timestamp()) if getattr(snap, "createTime", None) else None,
                "parent": parent_name,
                "parent_id": parent_id,
                "running": 0,
                "is_current": False,
                "is_current_base": snap_id == current_snapshot_id,
                "snapshot_ref": snap_id,
            }
            result.append(item)

            children = getattr(snap, "childSnapshotList", None) or []
            for child in children:
                stack.append((child, snap_name, snap_id))

        result.sort(key=lambda x: x.get("snaptime") or 0)

        current_base = None
        for item in result:
            if item["id"] == current_snapshot_id:
                current_base = item
                break

        if current_base is None and result:
            current_base = result[-1]

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

        return [current_item] + result
    

    def drop_vm_snapshot(self, node: str, vmid: str, snapid: str) -> None:
        """
        Smaže snapshot virtuálního stroje.

        Args:
            node: MoID hosta.
            vmid: MoID VM.
            snapid: ID snapshotu.

        Raises:
            ValueError: Pokud snapshot nebo VM neexistuje.
        """
        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        snapshot_info = getattr(vm, "snapshot", None)
        root_list = getattr(snapshot_info, "rootSnapshotList", None)

        if not snapshot_info or not root_list:
            raise ValueError(f"VM '{vmid}' has no snapshots")

        target_snapshot = None
        stack = list(root_list)

        while stack:
            snap = stack.pop()

            snap_ref = getattr(snap, "snapshot", None)
            current_snap_moid = getattr(snap_ref, "_moId", None)

            if current_snap_moid == snapid:
                target_snapshot = snap_ref
                break

            children = getattr(snap, "childSnapshotList", None) or []
            stack.extend(children)

        if not target_snapshot:
            raise ValueError(f"Snapshot '{snapid}' not found for VM '{vmid}'")

        task = target_snapshot.RemoveSnapshot_Task(
            removeChildren=False,
            consolidate=True
        )

        WaitForTask(task)


    def rollback_vm_snapshot(self, node: str, vmid: str, snapid: str) -> None:
        """
        Vrátí VM do stavu konkrétního snapshotu.

        Args:
            node: MoID hosta.
            vmid: MoID VM.
            snapid: ID snapshotu.

        Raises:
            ValueError: Pokud snapshot nebo VM neexistuje.
        """
        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        snapshot_info = getattr(vm, "snapshot", None)
        root_list = getattr(snapshot_info, "rootSnapshotList", None)

        if not snapshot_info or not root_list:
            raise ValueError(f"VM '{vmid}' has no snapshots")

        target_snapshot = None
        stack = list(root_list)

        while stack:
            snap = stack.pop()

            snap_ref = getattr(snap, "snapshot", None)
            current_snap_moid = getattr(snap_ref, "_moId", None)

            if current_snap_moid == snapid:
                target_snapshot = snap_ref
                break

            children = getattr(snap, "childSnapshotList", None) or []
            stack.extend(children)

        if not target_snapshot:
            raise ValueError(f"Snapshot '{snapid}' not found for VM '{vmid}'")

        task = target_snapshot.RevertToSnapshot_Task()
        WaitForTask(task)


    def get_vm_config(self, node: str, vmid: str) -> dict:
        """
        Získá kompletní konfiguraci virtuálního stroje.

        Obsahuje:
            - CPU, RAM
            - disky
            - CD-ROM
            - sítě
            - boot nastavení
            - autostart

        Args:
            node: MoID hosta.
            vmid: MoID VM.

        Returns:
            dict: Konfigurace VM.

        Raises:
            ValueError: Pokud VM nebo config není dostupný.
        """
        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        config = getattr(vm, "config", None)
        hardware = getattr(config, "hardware", None) if config else None

        if not config or not hardware:
            raise ValueError(f"Config for VM '{vmid}' is not available")

        cpu_num = getattr(hardware, "numCPU", None)
        cpu_cores = getattr(hardware, "numCoresPerSocket", None)
        cpu_sockets = None

        if cpu_num and cpu_cores:
            cpu_sockets = cpu_num // cpu_cores
        elif cpu_num:
            cpu_sockets = cpu_num

        result = {
            "vmid": vmid,
            "name": getattr(config, "name", None),
            "memory_mb": getattr(hardware, "memoryMB", None),
            "cpu": {
                "cores": cpu_cores,
                "sockets": cpu_sockets,
                "type": None,
            },
            "guest": getattr(config, "guestId", None),
            "disks": [],
            "cdroms": [],
            "networks": [],
            "boot": {
                "order": [],          # boot device order
                "firmware": getattr(config, "firmware", None),
                "machine": getattr(config, "version", None),
            },
            "autostart": {
                "enabled": None,
                "start_order": None,
                "start_action": None,
                "start_delay": None,
                "stop_action": None,
                "stop_delay": None,
                "wait_for_heartbeat": None,
            },
            "options": {
                "autostart": None,
                "start_after_create": False,
                "graphics": None,
            },
        }

        devices = list(getattr(hardware, "device", []) or [])
        devices_by_key = {
            getattr(d, "key", None): d
            for d in devices
            if getattr(d, "key", None) is not None
        }

        def get_datastore_info_from_backing(backing):
            """
            Prefer backing.datastore.summary.name.
            Fallback to datastore path parsing from backing.fileName: [datastore] path/file
            """
            datastore_name = None
            volume = None
            file_name = getattr(backing, "fileName", None) if backing else None

            datastore = getattr(backing, "datastore", None) if backing else None
            if datastore:
                summary = getattr(datastore, "summary", None)
                datastore_name = getattr(summary, "name", None) or getattr(datastore, "name", None)

            if file_name:
                if file_name.startswith("[") and "]" in file_name:
                    end = file_name.find("]")
                    parsed_ds = file_name[1:end].strip()
                    volume = file_name[end + 1:].strip()
                    if not datastore_name:
                        datastore_name = parsed_ds
                else:
                    volume = file_name

            return datastore_name, volume, file_name

        def get_controller_type(controller_key):
            if controller_key is None:
                return None
            controller = devices_by_key.get(controller_key)
            return controller.__class__.__name__ if controller else None

        def boot_device_name(item):
            if isinstance(item, vim.vm.BootOptions.BootableDiskDevice):
                return "disk"
            if isinstance(item, vim.vm.BootOptions.BootableEthernetDevice):
                return "network"
            if isinstance(item, vim.vm.BootOptions.BootableCdromDevice):
                return "cdrom"
            if isinstance(item, vim.vm.BootOptions.BootableFloppyDevice):
                return "floppy"
            return item.__class__.__name__

        # Boot order = pořadí zařízení pro boot VM
        boot_options = getattr(config, "bootOptions", None)
        boot_order = getattr(boot_options, "bootOrder", None) if boot_options else None
        if boot_order:
            result["boot"]["order"] = [boot_device_name(item) for item in boot_order]

        # Auto-start order = host-level pořadí startu/vypnutí VM
        runtime = getattr(vm, "runtime", None) or getattr(getattr(vm, "summary", None), "runtime", None)
        host = getattr(runtime, "host", None) if runtime else None
        if host:
            host_config_manager = getattr(host, "configManager", None)
            auto_start_manager = getattr(host_config_manager, "autoStartManager", None) if host_config_manager else None
            auto_start_cfg = getattr(auto_start_manager, "config", None) if auto_start_manager else None

            if auto_start_cfg:
                result["autostart"]["enabled"] = getattr(auto_start_cfg, "defaults", None) is not None
                power_info = list(getattr(auto_start_cfg, "powerInfo", []) or [])

                for idx, info in enumerate(power_info, start=1):
                    key = getattr(info, "key", None)
                    if key and getattr(key, "_moId", None) == vmid:
                        result["autostart"]["start_order"] = idx
                        result["autostart"]["start_action"] = getattr(info, "startAction", None)
                        result["autostart"]["start_delay"] = getattr(info, "startDelay", None)
                        result["autostart"]["stop_action"] = getattr(info, "stopAction", None)
                        result["autostart"]["stop_delay"] = getattr(info, "stopDelay", None)
                        result["autostart"]["wait_for_heartbeat"] = getattr(info, "waitForHeartbeat", None)
                        result["options"]["autostart"] = getattr(info, "startAction", None) not in (None, "none")
                        break

        for device in devices:
            controller_key = getattr(device, "controllerKey", None)

            if isinstance(device, vim.vm.device.VirtualDisk):
                backing = getattr(device, "backing", None)

                capacity_bytes = getattr(device, "capacityInBytes", None)
                if capacity_bytes is None:
                    capacity_kb = getattr(device, "capacityInKB", None)
                    capacity_bytes = int(capacity_kb) * 1024 if capacity_kb is not None else None

                size_gb = None
                if capacity_bytes is not None:
                    size_gb = round(capacity_bytes / (1024 ** 3), 2)

                datastore_name, volume, file_name = get_datastore_info_from_backing(backing)

                result["disks"].append({
                    "slot": f"disk{len(result['disks'])}",
                    "storage_id": datastore_name,
                    "volume": volume,
                    "file_name": file_name,
                    "size_gb": size_gb,
                    "controller_type": get_controller_type(controller_key),
                    "unit_number": getattr(device, "unitNumber", None),
                    "label": getattr(getattr(device, "deviceInfo", None), "label", None),
                })

            elif isinstance(device, vim.vm.device.VirtualCdrom):
                backing = getattr(device, "backing", None)

                datastore_name, volume, file_name = get_datastore_info_from_backing(backing)

                backing_type = backing.__class__.__name__ if backing else None
                iso_path = getattr(backing, "fileName", None) if backing else None

                result["cdroms"].append({
                    "key": getattr(device, "key", None),
                    "slot": f"cdrom{len(result['cdroms'])}",
                    "storage_id": datastore_name,
                    "volume": volume,
                    "file_name": file_name,
                    "iso_path": iso_path,
                    "backing_type": backing_type,
                    "controller_type": get_controller_type(controller_key),
                    "unit_number": getattr(device, "unitNumber", None),
                    "label": getattr(getattr(device, "deviceInfo", None), "label", None),
                })

            elif isinstance(device, vim.vm.device.VirtualEthernetCard):
                backing = getattr(device, "backing", None)

                network_id = None
                if backing:
                    network = getattr(backing, "network", None)
                    network_id = (
                        getattr(backing, "deviceName", None)
                        or getattr(network, "name", None)
                        or getattr(network, "_moId", None)
                    )

                result["networks"].append({
                    "slot": f"net{len(result['networks'])}",
                    "network_id": network_id,
                    "model": device.__class__.__name__,
                    "mac": getattr(device, "macAddress", None),
                    "connected": getattr(getattr(device, "connectable", None), "connected", None),
                    "label": getattr(getattr(device, "deviceInfo", None), "label", None),
                })

            elif isinstance(device, vim.vm.device.VirtualVideoCard):
                result["options"]["graphics"] = "vmware"

        return result
        

    def create_vm_backup(self, node_id: str, vm_id: str, backup_root: str) -> None:
        """
        Vytvoří backup VM ve formátu OVA.

        VM musí být vypnutá.

        Args:
            node_id: ID hosta.
            vm_id: ID VM.
            backup_root: Cílový adresář.

        Returns:
            dict: Informace o backupu.

        Raises:
            ValueError: Pokud VM není vypnutá.
            RuntimeError: Pokud export selže.
        """

        vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vm_id}' not found")

        vm_name = getattr(vm, "name", vm_id)
        power_state = getattr(getattr(vm, "runtime", None), "powerState", None)

        if power_state == vim.VirtualMachinePowerState.poweredOn:
            raise ValueError("VM must be powered off for ESXi folder backup")

        vmx_path = vm.config.files.vmPathName
        # např. "[local] VMTEST2/VMTEST2.vmx"

        if not vmx_path or not vmx_path.startswith("["):
            raise ValueError(f"Invalid VM path: {vmx_path}")

        datastore_name = vmx_path.split("]")[0].strip("[")
        relative_vmx_path = vmx_path.split("]", 1)[1].strip()
        vm_folder = relative_vmx_path.rsplit("/", 1)[0]

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        backup_dir = os.path.join(backup_root, "esxi", vm_id, f"{vm_id}_{timestamp}")
        tmp_backup_dir = backup_dir + ".part"

        os.makedirs(os.path.dirname(backup_dir), exist_ok=True)

        session_cookie = self.conn.si._stub.cookie
        if not session_cookie:
            raise ValueError("Missing ESXi session cookie")

        esxi_host = self.conn.host.replace("https://", "").replace("http://", "").rstrip("/")

        session = requests.Session()
        session.verify = False
        session.headers.update({
            "Cookie": session_cookie,
        })

        def list_datastore_files(folder_path: str) -> list[str]:
            search_spec = vim.HostDatastoreBrowserSearchSpec()
            search_spec.matchPattern = ["*"]

            task = datastore.browser.SearchDatastore_Task(
                datastorePath=f"[{datastore_name}] {folder_path}",
                searchSpec=search_spec,
            )

            WaitForTask(task)

            result = task.info.result
            files = []

            for item in result.file:
                files.append(item.path)

            return files

        datastore = None
        for ds in getattr(vm.runtime.host, "datastore", []) or []:
            if ds.name == datastore_name:
                datastore = ds
                break

        if datastore is None:
            raise ValueError(f"Datastore '{datastore_name}' not found on host")

        try:
            os.makedirs(tmp_backup_dir, exist_ok=True)

            files = list_datastore_files(vm_folder)

            if not files:
                raise RuntimeError(f"No files found in datastore folder: [{datastore_name}] {vm_folder}")

            for file_name in files:
                # snapshot lock soubory neber
                if file_name.endswith(".lck"):
                    continue

                remote_path = f"{vm_folder}/{file_name}"
                local_path = os.path.join(tmp_backup_dir, file_name)

                url = (
                    f"https://{esxi_host}/folder/{remote_path}"
                    f"?dcPath=ha-datacenter&dsName={datastore_name}"
                )

                with session.get(url, stream=True, timeout=(30, 600)) as response:
                    response.raise_for_status()

                    with open(local_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)

            os.rename(tmp_backup_dir, backup_dir)

            return {
                "vm_id": vm_id,
                "name": vm_name,
                "path": backup_dir,
                "format": "esxi-folder",
                "status": "completed",
                "datastore": datastore_name,
                "vm_folder": vm_folder,
            }

        except Exception as e:
            if os.path.exists(tmp_backup_dir):
                shutil.rmtree(tmp_backup_dir, ignore_errors=True)

            raise RuntimeError(f"Failed to create ESXi folder backup for VM '{vm_id}': {e}")

    def set_vm_config(self, node: str, vmid: str, optional_params: dict) -> dict:
        """
        Aktualizuje konfiguraci virtuálního stroje.

        Podporované změny:
            - name
            - memory_mb
            - cpu
            - disks
            - cdroms
            - boot

        VM může být automaticky vypnuta a znovu zapnuta.

        Args:
            node: MoID hosta.
            vmid: MoID VM.
            optional_params: Parametry změn.

        Returns:
            dict: Výsledek operace.

        Raises:
            ValueError: Neplatné parametry nebo VM neexistuje.
        """

        vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vmid}' not found")

        config = getattr(vm, "config", None)
        hardware = getattr(config, "hardware", None) if config else None
        runtime = getattr(vm, "runtime", None)

        if not config or not hardware:
            raise ValueError(f"Config for VM '{vmid}' is not available")

        power_state = getattr(runtime, "powerState", None)
        was_running = power_state == vim.VirtualMachinePowerState.poweredOn

        options = optional_params.get("options", {}) or {}
        boot = optional_params.get("boot", {}) or {}

        requires_shutdown = any([
            optional_params.get("memory_mb") is not None,
            bool(optional_params.get("cpu")),
            bool(optional_params.get("disks")),
            bool(optional_params.get("cdroms")),
            bool(boot),
            "graphics" in options,
            optional_params.get("nested_virtualization") is not None,
        ])

        if requires_shutdown and was_running:
            task = vm.PowerOffVM_Task()
            WaitForTask(task)

            vm = self.conn.get_entity_by_moid(vmid, vim.VirtualMachine)
            config = getattr(vm, "config", None)
            hardware = getattr(config, "hardware", None) if config else None
            runtime = getattr(vm, "runtime", None)

            if not config or not hardware:
                raise ValueError(f"Config for VM '{vmid}' is not available after power off")

        spec = vim.vm.ConfigSpec()
        changed = False

        current_num_cpus = getattr(config, "numCpu", None)
        current_cores_per_socket = getattr(config, "numCoresPerSocket", None)
        current_memory_mb = getattr(hardware, "memoryMB", None)
        current_nested_hv = getattr(config, "nestedHVEnabled", None)

        # 1) NAME
        if optional_params.get("name"):
            new_name = str(optional_params["name"])
            if getattr(vm, "name", None) != new_name:
                spec.name = new_name
                changed = True

        # 2) MEMORY
        if optional_params.get("memory_mb") is not None:
            new_memory_mb = int(optional_params["memory_mb"])
            if current_memory_mb != new_memory_mb:
                spec.memoryMB = new_memory_mb
                changed = True

        # 3) CPU
        cpu = optional_params.get("cpu", {}) or {}
        if cpu.get("cores") is not None:
            cores = int(cpu.get("cores", 1))
            sockets = int(cpu.get("sockets", 1))
            vcpus = cores * sockets

            if current_num_cpus != vcpus:
                spec.numCPUs = vcpus
                changed = True

            if current_cores_per_socket != cores:
                spec.numCoresPerSocket = cores
                changed = True

        device_changes = []

        def find_disk_by_slot(slot: str):
            digits = "".join(ch for ch in str(slot) if ch.isdigit())
            if not digits:
                return None

            unit_number = int(digits)

            for device in getattr(hardware, "device", []) or []:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    if getattr(device, "unitNumber", None) == unit_number:
                        return device
            return None

        def find_cdrom_by_slot(slot: str):
            digits = "".join(ch for ch in str(slot) if ch.isdigit())
            if not digits:
                return None

            unit_number = int(digits)

            for device in getattr(hardware, "device", []) or []:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    if getattr(device, "unitNumber", None) == unit_number:
                        return device
            return None

        def find_first_ide_controller():
            for device in getattr(hardware, "device", []) or []:
                if isinstance(device, vim.vm.device.VirtualIDEController):
                    return device
            return None

        def find_first_scsi_controller():
            for device in getattr(hardware, "device", []) or []:
                if isinstance(device, vim.vm.device.VirtualSCSIController):
                    return device
            return None

        # 5) DISKS
        for disk in optional_params.get("disks", []) or []:
            slot = disk.get("slot")
            if not slot:
                continue

            existing_disk = find_disk_by_slot(slot)

            # resize existujícího disku
            if existing_disk:
                new_size_gb = disk.get("size_gb")
                if new_size_gb is None:
                    continue

                current_capacity_kb = int(getattr(existing_disk, "capacityInKB", 0) or 0)
                new_capacity_kb = int(new_size_gb) * 1024 * 1024

                if new_capacity_kb < current_capacity_kb:
                    raise ValueError("Disk shrinking is not supported")

                if new_capacity_kb > current_capacity_kb:
                    disk_spec = vim.vm.device.VirtualDeviceSpec()
                    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                    disk_spec.device = existing_disk
                    disk_spec.device.capacityInKB = new_capacity_kb
                    device_changes.append(disk_spec)
                    changed = True

                continue

            # nový disk
            storage_id = disk.get("storage_id")
            size_gb = disk.get("size_gb")

            if not storage_id:
                raise ValueError(f"New disk '{slot}' requires storage_id")
            if size_gb is None:
                raise ValueError(f"New disk '{slot}' requires size_gb")

            datastore = self.conn.get_entity_by_moid(storage_id, vim.Datastore)
            if not datastore:
                raise ValueError(f"Datastore '{storage_id}' not found")

            controller = find_first_scsi_controller()
            if not controller:
                raise ValueError("No SCSI controller found for new disk")

            used_units = set()
            for device in getattr(hardware, "device", []) or []:
                if getattr(device, "controllerKey", None) == controller.key:
                    unit = getattr(device, "unitNumber", None)
                    if unit is not None:
                        used_units.add(unit)

            unit_number = 0
            while unit_number in used_units or unit_number == 7:
                unit_number += 1

            disk_type = (disk.get("disk_type") or "thin").lower()

            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            disk_spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create

            new_disk = vim.vm.device.VirtualDisk()
            new_disk.key = -1
            new_disk.controllerKey = controller.key
            new_disk.unitNumber = unit_number
            new_disk.capacityInKB = int(size_gb) * 1024 * 1024

            backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
            backing.datastore = datastore
            backing.diskMode = "persistent"

            if disk_type == "thin":
                backing.thinProvisioned = True
                backing.eagerlyScrub = False
            elif disk_type == "thick":
                backing.thinProvisioned = False
                backing.eagerlyScrub = False
            elif disk_type == "eagerzeroedthick":
                backing.thinProvisioned = False
                backing.eagerlyScrub = True
            else:
                raise ValueError("Unsupported disk_type. Use 'thin', 'thick', or 'eagerzeroedthick'")

            new_disk.backing = backing
            disk_spec.device = new_disk
            device_changes.append(disk_spec)
            changed = True

        # 6) CDROMS
        for cdrom in optional_params.get("cdroms", []) or []:
            slot = cdrom.get("slot")
            if not slot:
                continue

            existing_cdrom = find_cdrom_by_slot(slot)
            iso_name = cdrom.get("volume")

            if existing_cdrom:
                if iso_name:
                    datastore = None
                    storage_id = cdrom.get("storage_id")
                    if storage_id:
                        datastore = self.conn.get_entity_by_moid(storage_id, vim.Datastore)
                    else:
                        backing = getattr(existing_cdrom, "backing", None)
                        datastore = getattr(backing, "datastore", None)

                    if not datastore:
                        raise ValueError(f"Datastore for CD-ROM '{slot}' not found")

                    iso_path = f"[{datastore.name}] {iso_name}"

                    cd_spec = vim.vm.device.VirtualDeviceSpec()
                    cd_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                    cd_spec.device = existing_cdrom

                    backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
                    backing.fileName = iso_path
                    backing.datastore = datastore

                    cd_spec.device.backing = backing
                    device_changes.append(cd_spec)
                    changed = True

                continue

            # nový CD-ROM
            storage_id = cdrom.get("storage_id")
            iso_name = cdrom.get("volume") or cdrom.get("path")

            if not storage_id:
                raise ValueError(f"CD-ROM '{slot}' requires storage_id")
            if not iso_name:
                raise ValueError(f"CD-ROM '{slot}' requires volume or path")

            datastore = self.conn.get_entity_by_moid(storage_id, vim.Datastore)
            if not datastore:
                raise ValueError(f"Datastore '{storage_id}' not found")

            controller = find_first_ide_controller()
            if not controller:
                raise ValueError("No IDE controller found for new CD-ROM")

            digits = "".join(ch for ch in str(slot) if ch.isdigit())
            unit_number = int(digits)

            cd_spec = vim.vm.device.VirtualDeviceSpec()
            cd_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

            cdrom_device = vim.vm.device.VirtualCdrom()
            cdrom_device.key = -1
            cdrom_device.controllerKey = controller.key
            cdrom_device.unitNumber = unit_number

            backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            backing.fileName = f"[{datastore.name}] {iso_name}"
            backing.datastore = datastore

            cdrom_device.backing = backing
            cdrom_device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_device.connectable.startConnected = True
            cdrom_device.connectable.allowGuestControl = True
            cdrom_device.connectable.connected = False

            cd_spec.device = cdrom_device
            device_changes.append(cd_spec)
            changed = True

        # 7) BOOT
        boot_changed = False
        boot_options = vim.vm.BootOptions()

        if boot.get("order"):
            order = []
            mapping = {
                "net0": vim.vm.BootOptions.BootableEthernetDevice(),
                "cdrom0": vim.vm.BootOptions.BootableCdromDevice(),
                "scsi0": vim.vm.BootOptions.BootableDiskDevice(),
            }

            for item in boot["order"]:
                boot_dev = mapping.get(item)
                if boot_dev:
                    order.append(boot_dev)

            if order:
                boot_options.bootOrder = order
                boot_changed = True

        if device_changes:
            spec.deviceChange = device_changes

        if changed:
            task = vm.ReconfigVM_Task(spec=spec)
            WaitForTask(task)

        if requires_shutdown and was_running:
            task = vm.PowerOnVM_Task()
            WaitForTask(task)

        return {
            "success": True,
            "required_action": "shutdown" if requires_shutdown else "none",
            "was_running": was_running,
        }
        
    def get_vm_backups(self, node_id, vm_id) -> list[dict]:
        """Vrátí seznam dostupných filesystemových záloh pro zadanou VM.

        Args:
            node_id: MOID uzlu.
            vm_id: MOID virtuálního stroje.

        Returns:
            Seznam záloh nalezených v backup struktuře pro Xen.
        """
        return self._get_fs_vm_backups(vm_id, "esxi")

    def destroy_vm(self, node_id: str, vm_id: str) -> dict:
        """
        Smaže virtuální stroj.

        Pokud běží, nejprve ho vypne.

        Args:
            node_id: ID hosta.
            vm_id: ID VM.

        Raises:
            RuntimeError: Pokud je VM zaneprázdněná nebo smazání selže.
        """
        vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)

        if not vm:
            raise ValueError(f"VM '{vm_id}' not found")

        for running_task in getattr(vm, "recentTask", []) or []:
            info = getattr(running_task, "info", None)
            if not info:
                continue

            if info.state in (vim.TaskInfo.State.running, vim.TaskInfo.State.queued):
                raise RuntimeError(
                    f"VM '{vm_id}' is busy because task '{info.descriptionId}' is still in progress"
                )

        power_state = getattr(getattr(vm, "runtime", None), "powerState", None)

        try:
            if power_state == vim.VirtualMachinePowerState.poweredOn:
                poweroff_task = vm.PowerOffVM_Task()
                WaitForTask(poweroff_task)

            vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)

            destroy_task = vm.Destroy_Task()

            WaitForTask(destroy_task)

        except Exception as e:
            raise RuntimeError(f"Failed to delete VM '{vm_id}': {e}") from e

    
    def open_console(self, node_id: str, vm_id: str, protocol: str = "webmks") -> dict:
        """
        Otevře konzoli k virtuálnímu stroji přes WEBMKS.

        Args:
            node_id: ID hosta.
            vm_id: ID VM.
            protocol: Pouze 'webmks'.

        Returns:
            dict: WebSocket URL + ticket.

        Raises:
            ValueError: Pokud VM neexistuje nebo protokol není podporován.
        """
        vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vm_id}' not found")

        if protocol != "webmks":
            raise ValueError("For ESXi only 'webmks' protocol is supported")

        try:
            ticket_info = vm.AcquireTicket(ticketType="webmks")
        except Exception as e:
            raise RuntimeError(
                f"Failed to acquire WEBMKS ticket for VM '{vm_id}': {e}"
            ) from e

        if not ticket_info:
            raise RuntimeError(f"Empty WEBMKS ticket returned for VM '{vm_id}'")

        ws_url = getattr(ticket_info, "url", None)
        ticket = getattr(ticket_info, "ticket", None)
        host = getattr(ticket_info, "host", None)
        port = getattr(ticket_info, "port", None)

        if not ws_url:
            if host and port and ticket:
                ws_url = f"wss://{host}:{port}/ticket/{ticket}"
            else:
                raise RuntimeError(
                    f"WEBMKS ticket for VM '{vm_id}' does not contain a usable websocket URL"
                )

        return {
            "protocol": "webmks",
            "ws_url": ws_url,
            "ticket": ticket,
        }
    

    def get_vm_logs(
        self,
        node_id: str,
        vm_id: str,
        limit: int = 1000,
    ) -> dict:
        """
        Načte vmware.log soubory virtuálního stroje.

        Args:
            node_id: ID hosta.
            vm_id: ID VM.
            limit: Maximální počet řádků.

        Returns:
            dict: Logy VM.

        Raises:
            ValueError: Pokud VM nebo datastore není nalezen.
            FileNotFoundError: Pokud logy neexistují.
        """
        if not vm_id:
            raise ValueError("vm_id is required")

        if limit < 0:
            raise ValueError("limit must be >= 0")

        vm = self.conn.get_entity_by_moid(vm_id, vim.VirtualMachine)
        if not vm:
            raise ValueError(f"VM '{vm_id}' not found")

        vm_name = getattr(vm, "name", vm_id)
        vmx_path = getattr(getattr(getattr(vm, "config", None), "files", None), "vmPathName", None)

        if not vmx_path or "]" not in vmx_path:
            raise ValueError(f"VM '{vm_id}' has invalid vmPathName")

        datastore_name = vmx_path.split("]", 1)[0].strip("[ ").strip()
        rel_path = vmx_path.split("]", 1)[1].strip()
        vm_dir = rel_path.split("/", 1)[0].strip()

        if not datastore_name or not vm_dir:
            raise ValueError(f"Unable to parse datastore path from '{vmx_path}'")

        datastore = None
        for ds in getattr(vm, "datastore", []) or []:
            ds_name = getattr(getattr(ds, "summary", None), "name", None)
            if ds_name == datastore_name:
                datastore = ds
                break

        if not datastore:
            raise ValueError(f"Datastore '{datastore_name}' for VM '{vm_name}' not found")

        browser = datastore.browser
        datastore_path = f"[{datastore_name}] {vm_dir}"

        search_spec = vim.HostDatastoreBrowser.SearchSpec()
        search_spec.matchPattern = ["vmware.log", "vmware-*.log"]

        task = browser.SearchDatastore_Task(
            datastorePath=datastore_path,
            searchSpec=search_spec,
        )
        WaitForTask(task)

        result = task.info.result
        files = getattr(result, "file", None) or []

        if not files:
            raise FileNotFoundError(
                f"No vmware.log files found for VM '{vm_name}' in '{datastore_path}'"
            )

        file_names = sorted(f.path for f in files)

        selected_file = "vmware.log" if "vmware.log" in file_names else file_names[-1]
        vm_log_rel_path = f"{vm_dir}/{selected_file}"

        session_cookie = getattr(self.conn.si._stub, "cookie", None)
        if not session_cookie:
            raise ValueError("Missing vSphere session cookie")

        url = (
            f"https://{self.conn.host}/folder/"
            f"{requests.utils.quote(vm_log_rel_path, safe='/')}"
            f"?dsName={requests.utils.quote(datastore_name)}"
        )

        session = requests.Session()
        session.verify = False
        session.headers.update({
            "Cookie": session_cookie,
        })

        response = session.get(url, timeout=60)
        response.raise_for_status()

        all_lines = response.text.splitlines()
        selected_lines = all_lines[-limit:] if limit > 0 else all_lines

        normalized_lines = [
            {
                "upid": None,
                "type": "vmware",
                "starttime": None,
                "status": None,
                "line_no": index + 1,
                "text": line,
            }
            for index, line in enumerate(selected_lines)
        ]

        return {
            "lines_count": len(normalized_lines),
            "lines": normalized_lines,
            "source": {
                "vm_id": vm_id,
                "vm_name": vm_name,
                "datastore": datastore_name,
                "path": vm_log_rel_path,
                "file": selected_file,
            },
        }
    
    def _upload_ovf_disks_to_lease(self, lease, disk_files: dict, device_urls: dict):
        session_cookie = self.conn.si._stub.cookie

        session = requests.Session()
        session.verify = False
        session.headers.update({
            "Cookie": session_cookie,
            "Connection": "keep-alive",
        })

        total = len(device_urls)
        index = 0

        for import_key, url in device_urls.items():
            index += 1

            file_path = (
                disk_files.get(import_key)
                or disk_files.get(os.path.basename(import_key))
            )

            if not file_path and len(disk_files) == 1:
                file_path = next(iter(disk_files.values()))

            if not file_path:
                raise ValueError(
                    f"Missing file for import key: {import_key}. "
                    f"Available files: {list(disk_files.keys())}"
                )

            host = self.conn.host.replace("https://", "").replace("http://", "").rstrip("/")
            upload_url = url.replace("*", host)

            file_size = os.path.getsize(file_path)

            with open(file_path, "rb") as f:
                response = session.put(
                    upload_url,
                    data=f,
                    headers={"Content-Length": str(file_size)},
                    timeout=(30, 600),
                )
                response.raise_for_status()

            progress = int(index * 100 / total)
            try:
                lease.HttpNfcLeaseProgress(progress)
            except Exception:
                pass