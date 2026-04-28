# Esxi
Implementace rozhraní pro komunikaci s platformou Esxi. Obsahuje třídy pro připojení, práci s clusterem, uzly a virtuálními stroji.

---

## EsxiConnection
Zajišťuje připojení k platformě a správu session.

::: platforms.esxi.connection.EsxiConnection
    options:
      heading_level: 3
      show_root_heading: true

---

## EsxiClusterApi
Operace nad clusterem.

::: platforms.esxi.cluster.EsxiClusterApi
    options:
      heading_level: 3
      show_root_heading: true

---

## EsxiNodeApi
Operace nad jednotlivými uzly (status, storage, sítě).

::: platforms.esxi.node.EsxiNodeApi
    options:
      heading_level: 3
      show_root_heading: true

---

## EsxiVmApi
Správa virtuálních strojů (vytváření, snapshoty, logy).

::: platforms.esxi.vm.EsxiVmApi
    options:
      heading_level: 3
      show_root_heading: true