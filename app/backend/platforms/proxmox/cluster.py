from platforms.proxmox.connection import ProxmoxConnection

class ProxmoxClusterApi:
    """
    Je třída zajišťující získávání topologie a je otevřena budoucímu rozšíření o operace mezi uzly v clusteru.

    Args:
        connection: objekt zajišťující HTTP komunikaci s Proxmox API.
    """

    def __init__(self, connection: ProxmoxConnection):
        self.conn = connection

    def get_cluster_topology(self) -> dict:
        """
        Načte topologii clusteru včetně uzlů a jejich VM.

        Provádí dva dotazy:
        
        - /cluster/status → informace o clusteru a uzlech
        - /cluster/resources → seznam VM a kontejnerů

        Returns:
            seznamu clusteru a jejich uzlů, virtualních strojů a šablon
        """

        # Načtení základního stavu clusteru (uzly, cluster name)
        status_res = self.conn.request(
            method="GET",
            url=f"https://{self.conn.host}/api2/json/cluster/status"
        )

        # Načtení všech resource (VM, kontejnery, atd.)
        resources_res = self.conn.request(
            method="GET",
            url=f"https://{self.conn.host}/api2/json/cluster/resources"
        )

        status_items = status_res.get("data", [])
        resource_items = resources_res.get("data", [])

        cluster_name = None
        nodes = []
        node_map = {}

        # Zpracování uzlů a clusteru
        for item in status_items:
            if item.get("type") == "cluster":
                cluster_name = item.get("name")
                continue

            if item.get("type") != "node":
                continue

            node_name = item.get("name")
            if not node_name:
                continue

            node_obj = {
                "id": node_name,
                "name": node_name,
                "status": item.get("online") == 1,
                "host": item.get("ip"),
                "vms": [],
                "templates": []
            }

            nodes.append(node_obj)
            node_map[node_name] = node_obj

        # Přiřazení VM a template k jednotlivým uzlům
        for item in resource_items:
            if item.get("type") not in ("qemu", "lxc"):
                continue

            node_name = item.get("node")
            if node_name not in node_map:
                continue

            vm_obj = {
                "id": str(item.get("vmid")),
                "name": item.get("name") or f"vm-{item.get('vmid')}",
                "status": item.get("status")
            }

            # Rozdělení na běžné VM a template
            if item.get("template") == 1:
                node_map[node_name]["templates"].append(vm_obj)
            else:
                node_map[node_name]["vms"].append(vm_obj)

        # Výsledná struktura odpovědi
        return {
            "clusters": [
                {
                    "cluster": cluster_name,
                    "nodes": nodes
                }
            ]
        }