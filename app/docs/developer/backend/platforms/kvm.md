# KVM
Implementace rozhraní pro komunikaci s platformou KVM. Obsahuje třídy pro připojení, práci s clusterem, uzly a virtuálními stroji.

---

## KvmConnection
Zajišťuje připojení k platformě a správu session.

::: platforms.kvm.connection.KvmConnection
    options:
      heading_level: 3
      show_root_heading: true

---

## KvmClusterApi
Operace nad clusterem.

::: platforms.kvm.cluster.KvmClusterApi
    options:
      heading_level: 3
      show_root_heading: true

---

## KvmNodeApi
Operace nad jednotlivými uzly (status, storage, sítě).

::: platforms.kvm.node.KvmNodeApi
    options:
      heading_level: 3
      show_root_heading: true

---

## KvmVmApi
Správa virtuálních strojů (vytváření, snapshoty, logy).

::: platforms.kvm.vm.KvmVmApi
    options:
      heading_level: 3
      show_root_heading: true