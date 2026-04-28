# Proxmox
Implementace rozhraní pro komunikaci s platformou Proxmox. Obsahuje třídy pro připojení, práci s clusterem, uzly a virtuálními stroji.

---

## ProxmoxConnection
Zajišťuje připojení k platformě a správu session.

::: platforms.proxmox.connection.ProxmoxConnection
    options:
      heading_level: 3
      show_root_heading: true

---

## ProxmoxClusterApi
Operace nad clusterem.

::: platforms.proxmox.cluster.ProxmoxClusterApi
    options:
      heading_level: 3
      show_root_heading: true

---

## ProxmoxNodeApi
Operace nad jednotlivými uzly (status, storage, sítě).

::: platforms.proxmox.node.ProxmoxNodeApi
    options:
      heading_level: 3
      show_root_heading: true

---

## ProxmoxVmApi
Správa virtuálních strojů (vytváření, snapshoty, logy).

::: platforms.proxmox.vm.ProxmoxVmApi
    options:
      heading_level: 3
      show_root_heading: true