# Frontend konfigurace

Frontend používá `.env` soubory pro nastavení prostředí.

| Soubor | Účel |
|---|---|
| `.env` | obecná konfigurace |
| `.env.development` | konfigurace pro vývoj |
| `.env.production` | konfigurace pro produkční build |

## Proměnné

Frontend proměnné musí začínat prefixem `REACT_APP_`.

Příklad:

```env
REACT_APP_API_URL=http://localhost:8000
```