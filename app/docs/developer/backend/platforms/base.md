# Base classes

Základní rozhraní pro komunikaci s platformou. Slouží jako kontrakt pro jednotlivé implementace rozhraní virtualních platforem.

---

## BaseConnection
Zajišťuje připojení k platformě a správu session.

::: platforms.base.connection.BaseConnection
    options:
      heading_level: 3
      show_root_heading: true
---

## BaseClusterApi
Operace nad clusterem (topologie, uzly apod.).

::: platforms.base.cluster.BaseClusterApi
    options:
      heading_level: 3
      show_root_heading: true
---

## BaseNodeApi
Operace nad jednotlivými uzly (status, storage, sítě).

::: platforms.base.node.BaseNodeApi
    options:
      heading_level: 3
      show_root_heading: true
---

## BaseVmApi
Správa virtuálních strojů (vytváření, snapshoty, logy).

::: platforms.base.vm.BaseVmApi
    options:
      heading_level: 3
      show_root_heading: true