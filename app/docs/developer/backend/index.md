# Backend – přehled

Backend je postavený na frameworku FastAPI a zajišťuje:

- správu uživatelů
- správu serverů a virtualizačních platforem
- práci s nody a virtuálními stroji
- automatizaci (scheduler + tasky)
- CLI přístup přes SSH

---

## Architektura

Backend je rozdělen do několika vrstev:

| Vrstva | Popis |
|---|---|
| `routers/` | HTTP API endpointy (FastAPI) |
| `services/` | business logika aplikace |
| `database/` | ORM modely a DB konfigurace |
| `platforms/` | komunikace s virtualizačními platformami |
| `sessions/` | správa aktivních připojení |
| `security/` | autentizace, JWT, šifrování |
| `cli/` | SSH CLI rozhraní |

---

## Tok požadavku

Zpracování požadavku probíhá následovně:

1. Request přijde na FastAPI router
2. Router zavolá service vrstvu
3. Service vrstva pracuje s databází
4. Service vrstva komunikuje s platform gateway
5. Výsledek se vrátí jako JSON odpověď

---

## Platform Gateway

Platformy (např. Proxmox, ESXi) jsou abstrahovány přes jednotné rozhraní.

Díky tomu backend:

- podporuje více platforem
- používá stejné API pro všechny platformy

---

## Session management

Backend udržuje aktivní připojení k platformám pomocí `SessionManager`.

- každé připojení má vlastní session
- session mají expiraci
- probíhá automatický cleanup

---

## Automatizace

Automatizační systém umožňuje:

- plánování úloh (scheduler)
- spouštění akcí nad VM
- řetězení úloh (parent-child)

---

## CLI

Kromě HTTP API backend poskytuje také CLI přes SSH.

CLI:

- používá stejnou service vrstvu jako API
- umožňuje interaktivní správu systému

---

## Související části dokumentace

- Spuštění → jak backend spustit
- Konfigurace → nastavení `.env`
- API → HTTP rozhraní
- Services → business logika
- Platforms → integrace s platformami