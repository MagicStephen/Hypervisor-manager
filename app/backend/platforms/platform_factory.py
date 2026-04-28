# registry.py
from platforms.proxmox.connection import ProxmoxConnection
from platforms.proxmox.cluster import ProxmoxClusterApi
from platforms.proxmox.node import ProxmoxNodeApi
from platforms.proxmox.vm import ProxmoxVmApi


from platforms.xen.connection import XenConnection
from platforms.xen.cluster import XenClusterApi
from platforms.xen.node import XenNodeApi
from platforms.xen.vm import XenVmApi

from platforms.kvm.connection import KvmConnection
from platforms.kvm.cluster import KvmClusterApi
from platforms.kvm.node import KvmNodeApi
from platforms.kvm.vm import KvmVmApi

from platforms.esxi.connection import EsxiConnection
from platforms.esxi.cluster import EsxiClusterApi
from platforms.esxi.node import EsxiNodeApi
from platforms.esxi.vm import EsxiVmApi
from dataclasses import dataclass

@dataclass(frozen=True)
class PlatformAdapter:
    connection: type
    cluster: type
    node: type
    vm: type

class PlatformFactory:

    def __init__(self):
        self.registry = {
            "proxmox": PlatformAdapter(
                connection = ProxmoxConnection,
                cluster = ProxmoxClusterApi,
                node = ProxmoxNodeApi,
                vm = ProxmoxVmApi
            ),
            "xen": PlatformAdapter(
                connection = XenConnection,
                cluster = XenClusterApi,
                node = XenNodeApi,
                vm = XenVmApi
            ),
            "kvm": PlatformAdapter(
                connection = KvmConnection,
                cluster = KvmClusterApi,
                node = KvmNodeApi,
                vm = KvmVmApi
            ),
            "esxi": PlatformAdapter(
                connection = EsxiConnection,
                cluster = EsxiClusterApi,
                node = EsxiNodeApi,
                vm = EsxiVmApi
            )
        }

    def _get_adapter(self, platform: str) -> PlatformAdapter:
        try:
            return self.registry[platform.lower()]
        except KeyError:
            raise ValueError(f"Unsupported platform: {platform}")

    # ---------- CONNECTION ----------
    def create_connection(self, platform: str, host: str, port: int | None):
        adapter = self._get_adapter(platform)

        if port is not None:
            return adapter.connection(host=host, port=str(port))
        return adapter.connection(host=host)

    # ---------- VM API ----------
    def create_vm_api(self, platform: str, connection):
        adapter = self._get_adapter(platform)
        return adapter.vm(connection)

    # ---------- NODE API ----------
    def create_node_api(self, platform: str, connection):
        adapter = self._get_adapter(platform)
        return adapter.node(connection)
    
    def create_cluster_api(self, platform: str, connection):
        adapter = self._get_adapter(platform)
        return adapter.cluster(connection)