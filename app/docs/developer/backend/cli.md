# CLI (Command Line Interface)

Backend obsahuje CLI vrstvu, která umožňuje ovládat aplikaci přes SSH.

CLI část převádí uživatelské příkazy na volání servisní vrstvy backendu.

## Hlavní účel

`CliSession` reprezentuje jednu přihlášenou CLI session.

Zajišťuje:

1. uchování informací o přihlášeném uživateli
2. kontrolu, zda je uživatel přihlášený
3. vytvoření databázové session
4. volání odpovídajících service metod
5. vrácení výsledku ve formátu vhodném pro CLI

## Zpracování příkazu

Zpracování CLI příkazu probíhá v několika krocích:

1. Uživatel zadá příkaz přes SSH.
2. Příkaz je zpracován command handlerem.
3. Handler zavolá odpovídající metodu v `CliSession`.
4. `CliSession` zavolá service vrstvu.
5. Service vrstva komunikuje s databází nebo platformou.
6. Výsledek se vrátí jako JSON odpověď.

## Dostupné příkazy

CLI podporuje následující příkazy:

### Server

| Příkaz | Popis |
|---|---|
| `server list` | vypíše seznam serverů |
| `server create` | vytvoří nový server (interaktivně) |
| `server reconnect <server_id>` | znovu se připojí k serveru |

---

### Node

| Příkaz | Popis |
|---|---|
| `node show <server_id> <node_id>` | zobrazí detail nodu |

---

### Virtual Machines

| Příkaz | Popis |
|---|---|
| `vm show <server_id> <node_id> <vm_id>` | zobrazí stav VM |
| `vm start <server_id> <node_id> <vm_id>` | spustí VM |
| `vm stop <server_id> <node_id> <vm_id>` | zastaví VM |
| `vm reboot <server_id> <node_id> <vm_id>` | restartuje VM |
| `vm shutdown <server_id> <node_id> <vm_id>` | vypne VM |
| `vm destroy <server_id> <node_id> <vm_id>` | odstraní VM |
| `vm create <server_id> <node_id>` | vytvoří VM (interaktivně) |

---

### System

| Příkaz | Popis |
|---|---|
| `help` | zobrazí dostupné příkazy |
| `exit` / `quit` | ukončí CLI |

---