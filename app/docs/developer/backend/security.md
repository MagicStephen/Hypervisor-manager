# Security

Tato část backendu zajišťuje autentizaci, práci s hesly, JWT tokeny a šifrování citlivých údajů.

## Přehled

| Soubor | Účel |
|---|---|
| `JWT_token.py` | vytváření a ověřování JWT tokenů |
| `Hash.py` | konfigurace hashování hesel |
| `Fernet.py` | šifrování a dešifrování citlivých dat |

## JWT tokens

JWT tokeny se používají pro ověření identity uživatele.

Backend používá dva typy tokenů:

| Token | Účel |
|---|---|
| běžný access token | přístup do aplikace |
| console token | krátkodobý přístup ke konzoli VM |

### Access token

Access token obsahuje:

| Pole | Popis |
|---|---|
| `sub` | ID uživatele |
| `exp` | čas expirace tokenu |

### Console token

Console token obsahuje navíc informace potřebné pro přístup ke konzoli:

| Pole | Popis |
|---|---|
| `kind` | typ tokenu, očekává se `console` |
| `server_id` | ID serveru |
| `node_id` | ID nodu |
| `platform` | platforma |
| `host` | adresa serveru |

Console token je krátkodobý a ve výchozím nastavení expiruje po 60 sekundách.

## Password hashing

Hesla uživatelů se neukládají v čitelné podobě.

Pro hashování se používá `passlib` s algoritmem `bcrypt`.

## Fernet encryption

Fernet se používá pro šifrování citlivých údajů, například hesel k platformám.

Šifrovací klíč se načítá z proměnné prostředí `FERNET_KEY`.

Například v `.env` souboru:

```env
FERNET_KEY=your-secret-key