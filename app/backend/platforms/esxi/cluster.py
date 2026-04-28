from platforms.base.cluster import BaseClusterApi
from pyVmomi import vim
from platforms.esxi.connection import EsxiConnection

class EsxiClusterApi(BaseClusterApi):
    """
    Třída zajišťující získávání topologie ESXi/vSphere prostředí.

    Načítá clustery, hosty a virtuální stroje z vSphere inventory
    pomocí pyVmomi API.

    Args:
        connection: Objekt zajišťující komunikaci s ESXi/vSphere API.
    """

    def __init__(self, connection: EsxiConnection):
        """
        Inicializuje API klienta pro práci s ESXi/vSphere cluster topologií.

        Args:
            connection: Připojení k ESXi/vSphere.
        """
        self.conn = connection

    def get_cluster_topology(self) -> dict:
        """
        Načte topologii ESXi/vSphere prostředí včetně clusterů, hostů a VM.

        Pokud jsou dostupné objekty typu `ClusterComputeResource`, metoda
        vrátí hosty seskupené podle clusterů. Pokud žádný cluster neexistuje,
        vrátí samostatné ESXi hosty v prázdném clusteru.

        Returns:
            Slovník obsahující seznam clusterů, jejich uzlů a virtuálních strojů.
        """

        clusters = list(self.conn.get_container_view([vim.ClusterComputeResource]))

        result = []

        if clusters:
            for cluster in clusters:
                nodes = []

                for host in cluster.host:
                    nodes.append(self._host_conn_data(host))

                result.append({
                    "cluster": cluster.name,
                    "nodes": nodes
                })

            return {
                "clusters": result
            }

        hosts = list(self.conn.get_container_view([vim.HostSystem]))

        nodes = []
        for host in hosts:
            nodes.append(self._host_conn_data(host))

        return {
            "clusters": [
                {
                    "cluster": "",
                    "nodes": nodes
                }
            ]
        }

    def _host_conn_data(self, host) -> dict:
        """
        Převede ESXi host objekt do normalizované struktury pro frontend/API.

        Args:
            host: Objekt typu `vim.HostSystem`.

        Returns:
            Slovník obsahující identifikátor hosta, název, stav připojení,
            IP adresu a seznam VM běžících na daném hostu.
        """
        runtime = getattr(host, "runtime", None)

        status = False
        if runtime and getattr(runtime, "connectionState", None) == "connected":
            status = True

        ip = None
        try:
            if host.config and host.config.network and host.config.network.vnic:
                ip = host.config.network.vnic[0].spec.ip.ipAddress
        except Exception:
            pass

        vms = []
        for vm in getattr(host, "vm", []):
            vm_runtime = getattr(vm, "runtime", None)

            vms.append({
                "id": getattr(vm, "_moId", None),
                "name": getattr(vm, "name", None),
                "status": "running" if vm_runtime and vm_runtime.powerState == "poweredOn" else "stopped",
            })

        return {
            "id": host._moId,
            "name": host.name,
            "status": status,
            "host": ip,
            "vms": vms,
        }