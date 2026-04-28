# API(Application Programming Interface)

Backend poskytuje HTTP API pomocí FastAPI.

API slouží hlavně pro komunikaci mezi frontendem a backendem.

## Hlavní soubor

FastAPI aplikace je definovaná v souboru `app.py`.

Tento soubor zajišťuje:

1. vytvoření FastAPI aplikace
2. registraci routerů
3. nastavení CORS
4. inicializaci sdílených služeb
5. spuštění scheduleru při startu aplikace

## Lifespan

Při startu aplikace proběhne inicializace v `lifespan()`.

| Krok | Popis |
|---:|---|
| 1 | vytvoří se databázové tabulky |
| 2 | do `app.state` se uloží `session_manager` |
| 3 | do `app.state` se uloží `platform_gateway` |
| 4 | do `app.state` se uloží `scheduler` |
| 5 | nastaví se pravidelný cleanup session |
| 6 | spustí se scheduler |

Při ukončení aplikace se scheduler zastaví.

## Sdílené služby

| Objekt | Účel |
|---|---|
| `SessionManager` | správa aktivních připojení k platformám |
| `PlatformGateway` | jednotné rozhraní pro práci s platformami |
| `Scheduler` | plánování a spouštění automatizačních úloh |

## Routery

API je rozdělené do několika routerů podle oblasti systému.

| Router | Prefix | Popis |
|---|---|---|
| `user_router` | `/users` | uživatelé a autentizace |
| `server_router` | `/servers` | správa serverů |
| `node_router` | `/servers/{serverid}/nodes` | práce s nody |
| `vm_router` | `/servers/{serverid}/vms` | správa virtuálních strojů |
| `automation_router` | `/servers/{serverid}/tasks` | automatizační úlohy |

## Request flow

Zpracování HTTP požadavku probíhá takto:

1. Frontend pošle HTTP request.
2. FastAPI vybere odpovídající router.
3. Router zpracuje vstup a zavolá service vrstvu.
4. Service vrstva pracuje s databází nebo platform gateway.
5. API vrátí JSON odpověď frontendu.

## CORS

CORS je nastavený pomocí `CORSMiddleware`.

---

## Endpointy

### Users

| Metoda | Cesta | Popis |
|---|---|---|
| `POST` | `/users/login` | přihlášení uživatele |
| `POST` | `/users/register` | registrace uživatele |
| `GET` | `/users/me` | aktuální uživatel |

---

### Servers

| Metoda | Cesta | Popis |
|---|---|---|
| `GET` | `/servers` | seznam serverů |
| `POST` | `/servers` | vytvoření serveru |
| `POST` | `/servers/{serverid}/reconnect` | reconnect |

---

### Nodes

| Metoda | Cesta | Popis |
|---|---|---|
| `GET` | `/servers/{serverid}/nodes/{node_id}` | detail nodu |

---

### Virtual Machines

| Metoda | Cesta | Popis |
|---|---|---|
| `GET` | `/servers/{serverid}/vms/{vm_id}` | stav VM |
| `POST` | `/servers/{serverid}/vms/{vm_id}/start` | start |
| `POST` | `/servers/{serverid}/vms/{vm_id}/stop` | stop |
| `POST` | `/servers/{serverid}/vms/{vm_id}/reboot` | reboot |
| `POST` | `/servers/{serverid}/vms/{vm_id}/shutdown` | shutdown |
| `DELETE` | `/servers/{serverid}/vms/{vm_id}` | delete |
| `POST` | `/servers/{serverid}/vms` | create |

---

### Automation

| Metoda | Cesta | Popis |
|---|---|---|
| `POST` | `/servers/{serverid}/tasks/automation-auth` | uloží auth |
| `GET` | `/servers/{serverid}/tasks/automation-auth` | načte auth |
| `DELETE` | `/servers/{serverid}/tasks/automation-auth/{auth_id}` | smaže auth |
| `GET` | `/servers/{serverid}/tasks/automation-tasks` | seznam úloh |
| `POST` | `/servers/{serverid}/tasks/automation-task` | vytvoří úlohu |
| `DELETE` | `/servers/{serverid}/tasks/automation-task/{taskid}` | smaže úlohu |

---

## Reference routerů

### Users
::: routers.user_router

### Servers
::: routers.server_router

### Nodes
::: routers.node_router

### Virtual Machines
::: routers.vm_router

### Automation
::: routers.automation_router