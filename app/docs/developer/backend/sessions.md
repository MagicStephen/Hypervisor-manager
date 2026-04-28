# Sessions

Složka `sessions` řeší dočasné backendové relace pro připojení k platformám.

Session zde neznamená přihlášení uživatele do webové aplikace, ale aktivní spojení na konkrétní platformu/server.

## Účel

`SessionManager` ukládá aktivní connection objekty v paměti aplikace.

Používá se pro:

1. vytvoření nové session po připojení k platformě
2. vyhledání existující session podle uživatele, platformy a hosta
3. získání connection objektu podle `session_id`
4. odstranění expirovaných session
5. pravidelný cleanup starých session

## SessionContext

`SessionContext` obsahuje informace o jedné aktivní session:

| Pole | Popis |
|---|---|
| `user_id` | ID uživatele |
| `platform` | typ platformy |
| `host` | adresa serveru |
| `connection` | aktivní connection objekt |
| `expires_at` | čas expirace session |

## Životní cyklus session

1. Uživatel se připojí k platformě.
2. Backend vytvoří `SessionContext`.
3. `SessionManager.create()` uloží session do paměti.
4. Další požadavky používají existující session.
5. Po expiraci je session odstraněna pomocí `cleanup()`.

## Thread safety

`SessionManager` používá `threading.RLock`, aby byl přístup k internímu seznamu session bezpečný při paralelním používání.

## Chování při chybě

| Situace | Výsledek |
|---|---|
| session neexistuje | `404 Session not found` |
| neplatné `session_id` | `404 Invalid session id` |
| session expirovala | `410 Session expired` |

## Automaticky generovaná reference

::: sessions.session_manager