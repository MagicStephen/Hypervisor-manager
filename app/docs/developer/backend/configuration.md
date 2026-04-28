# Konfigurace

Backend používá konfigurační hodnoty z environment variables.

Tyto hodnoty se typicky definují v `.env` souboru.

## Přehled proměnných

| Proměnná | Popis |
|---|---|
| `DATABASE_URL` | připojení k databázi (SQLAlchemy format) |
| `SECRET_KEY` | klíč pro podepisování JWT tokenů |
| `ALGORITHM` | algoritmus pro JWT (např. HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | doba platnosti JWT tokenu |
| `FERNET_KEY` | klíč pro šifrování citlivých dat |
| `CORS_ORIGINS` | povolené frontend URL |
| `COOKIE_SECURE` | zda se cookies posílají jen přes HTTPS |
| `COOKIE_SAMESITE` | politika cookies (lax / strict / none) |
| `COOKIE_MAX_AGE` | doba platnosti cookie |

## .env soubor

Projekt používá `.env` soubor pro konfiguraci.

Bez správně nastaveného `.env` souboru se backend nespustí,
protože chybí povinné proměnné (např. `SECRET_KEY`, `FERNET_KEY`).

Pro vytvoření vlastního `.env` souboru použij `.env.example`: