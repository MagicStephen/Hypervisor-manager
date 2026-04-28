# Xen
Implementace rozhraní pro komunikaci s platformou XCP-ng. Obsahuje třídy pro připojení, práci s clusterem, uzly a virtuálními stroji.

---

## XenConnection
Zajišťuje připojení k platformě a správu session.

::: platforms.xen.connection.XenConnection
    options:
      heading_level: 3
      show_root_heading: true

---

## XenClusterApi
Operace nad clusterem.

::: platforms.xen.cluster.XenClusterApi
    options:
      heading_level: 3
      show_root_heading: true

---

## XenNodeApi
Operace nad jednotlivými uzly (status, storage, sítě).

::: platforms.xen.node.XenNodeApi
    options:
      heading_level: 3
      show_root_heading: true

---

## XenVmApi
Správa virtuálních strojů (vytváření, snapshoty, logy).

::: platforms.xen.vm.XenVmApi
    options:
      heading_level: 3
      show_root_heading: true