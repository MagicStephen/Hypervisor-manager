from platforms.base.cluster import BaseClusterApi
import libvirt

class KvmClusterApi(BaseClusterApi):

    def __init__(self, connection):
        self.conn = connection

    def get_cluster_topology(self) -> dict:

        hostname = self.conn.session.getHostname()
        status = bool(self.conn.session.isAlive())

        domains = self.conn.session.listAllDomains(0)

        state_map = {
            libvirt.VIR_DOMAIN_NOSTATE: "unknown",
            libvirt.VIR_DOMAIN_RUNNING: "running",
            libvirt.VIR_DOMAIN_BLOCKED: "blocked",
            libvirt.VIR_DOMAIN_PAUSED: "paused",
            libvirt.VIR_DOMAIN_SHUTDOWN: "shutdown",
            libvirt.VIR_DOMAIN_SHUTOFF: "stopped",
            libvirt.VIR_DOMAIN_CRASHED: "crashed",
            libvirt.VIR_DOMAIN_PMSUSPENDED: "suspended",
        }

        vms = []
        
        for dom in domains:
            try:
                state, _ = dom.state()
                vm_status = state_map.get(state, "unknown")
            except libvirt.libvirtError:
                vm_status = "unknown"

            vms.append({
                "id": dom.name(),
                "uuid": dom.UUIDString(),
                "name": dom.name(),
                "status": vm_status,
            })

        return {
            "clusters": [
                {
                    "cluster": hostname,
                    "nodes": [
                        {
                            "id": hostname,
                            "name": hostname,
                            "status": status,
                            "host": self.conn.host,
                            "vms": vms
                        }
                    ]
                }
            ]
        }