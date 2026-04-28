from platforms.base.cluster import BaseClusterApi
from platforms.xen.connection import XenConnection

class XenClusterApi(BaseClusterApi):
    """
    Je třída zajišťující získávání topologie a je otevřena budoucímu rozšíření o operace mezi uzly v clusteru.

    Args:
        connection: objekt zajišťující HTTP komunikaci s Xen API.
    """

    def __init__(self, connection: XenConnection):
        self.conn = connection

    def get_cluster_topology(self) -> dict:
        """
        Načte topologii Xen clusteru včetně uzlů, běžících VM, vypnutých VM a šablon.

        Provádí dotazy:

        - `pool.get_all_records` → informace o poolu / clusteru
        - `host.get_all_records` → seznam hostů
        - `VM.get_all_records` → seznam virtuálních strojů

        Returns:
            Struktura clusteru ve formátu:
        """
        # Načtení základních informací o poolu, hostech a VM
        pool_records = self.conn.request(
            "POST",
            "pool.get_all_records",
            [self.conn.session]
        )

        host_records = self.conn.request(
            "POST",
            "host.get_all_records",
            [self.conn.session]
        )

        vm_records = self.conn.request(
            "POST",
            "VM.get_all_records",
            [self.conn.session]
        )

        # Zjištění názvu clusteru / poolu
        cluster_name = ""
        if pool_records:
            pool = next(iter(pool_records.values()))
            cluster_name = pool.get("name_label") or ""

        nodes = []
        host_map = {}

        # Převod hostů na interní reprezentaci uzlů
        for host_ref, host in host_records.items():
            node_obj = {
                "id": host.get("uuid"),
                "ref": host_ref,
                "name": host.get("name_label") or host_ref,
                "status": bool(host.get("enabled", False)),
                "host": host.get("address") or "",
                "vms": []
            }
            nodes.append(node_obj)
            host_map[host_ref] = node_obj

        stopped_vms = []
        templates = []

        # Zpracování VM a jejich rozdělení na:
        # - běžící VM přiřazené ke konkrétním hostům
        # - vypnuté VM
        # - template
        for vm_ref, vm in vm_records.items():
            if vm.get("is_control_domain"):
                continue

            if vm.get("is_a_snapshot"):
                continue

            if vm.get("is_default_template"):
                continue

            is_template = bool(vm.get("is_a_template"))
            power_state = (vm.get("power_state") or "").lower()
            resident_on = vm.get("resident_on")
            affinity = vm.get("affinity")

            vm_obj = {
                "id": vm.get("uuid"),
                "name": vm.get("name_label"),
                "status": power_state,
            }

            if is_template:
                templates.append(vm_obj)
                continue

            if power_state == "running":
                if resident_on in host_map:
                    host_map[resident_on]["vms"].append(vm_obj)
            else:
                # U vypnutých VM zkusíme určit preferovaný uzel
                if affinity != "OpaqueRef:NULL" and affinity in host_map:
                    vm_obj["preferred_node"] = {
                        "id": host_map[affinity]["id"],
                        "name": host_map[affinity]["name"]
                    }
                else:
                    vm_obj["preferred_node"] = None

                stopped_vms.append(vm_obj)

        # Odstranění interního reference ID z výsledku
        for node in nodes:
            node.pop("ref", None)

        cluster = {
            "cluster": cluster_name,
            "nodes": nodes,
            "stopped_vms": stopped_vms,
            "templates": templates
        }

        # Výsledná struktura topologie clusteru
        return {
            "clusters": [cluster]
        }