# Database

Tato část backendu zajišťuje:

- konfiguraci databázového připojení
- správu databázových session
- definici ORM modelů

## Database configuration

Konfigurace databáze je definována v `database/database.py`.

Používá se SQLAlchemy pro práci s databází a správu session.

::: database.database

---

## Models

Databázové modely definují strukturu uložených dat.

### Přehled modelů

| Model | Popis |
|---|---|
| `User` | uživatel aplikace |
| `Platform` | typ platformy (např. Proxmox, Esxi) |
| `Server` | připojený server |
| `Node` | node v rámci serveru |
| `ServerNode` | vazba server ↔ node |
| `ServerAutomationAuth` | autentizace pro automatizaci |
| `AutomationTask` | definice automatizační úlohy |
| `AutomationTaskRun` | běh konkrétní úlohy |

---

## Model reference

::: database.models.platform_model

::: database.models.user_model

::: database.models.server_model

::: database.models.node_model

::: database.models.server_node_model

::: database.models.server_automation_auth_model

::: database.models.automation_task_model

::: database.models.automation_task_run_model