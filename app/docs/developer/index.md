# Vývojářská dokumentace

Tato dokumentace popisuje strukturu a fungování aplikace Hypervisor Manager.

## Architektura

Aplikace je rozdělena na dvě hlavní části:

- **Frontend** – React aplikace zajišťující uživatelské rozhraní
- **Backend** – FastAPI aplikace poskytující API a integraci s hypervizory

## Struktura dokumentace

### Frontend

Dokumentace frontend části obsahuje:

- strukturu stránek a komponent
- práci se službami (API komunikace)
- konfiguraci aplikace

  Viz sekce *Frontend*

---

### Backend

Dokumentace backend části obsahuje:

- API a jeho strukturu
- práci s databází a sessions
- bezpečnostní mechanismy
- integrace s jednotlivými platformami (Proxmox, ESXi, KVM, Xen)
- servisní vrstvy aplikace

  Viz sekce *Backend*

---

## Podporované platformy

Aplikace umožňuje správu různých hypervizorů:

- Proxmox
- VMware ESXi
- KVM
- Xen

Každá platforma má vlastní implementaci v backendu.

---
