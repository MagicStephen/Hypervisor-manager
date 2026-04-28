# Servisní vrstva (Services)

Složka `services/` obsahuje funkce pro komunikaci s backend API.  
Tyto funkce zapouzdřují HTTP požadavky a oddělují API logiku od React komponent.

## Účel

Servisní vrstva slouží k:

1. volání backend endpointů  
2. sjednocení práce s API  
3. vracení dat komponentám  
4. oddělení fetch logiky od UI  

---

## Struktura

Servisní vrstva je rozdělena podle domén:

| Soubor | Popis |
|--------|------|
| `UserService.js` | autentizace uživatele |
| `ServerService.js` | správa serverů |
| `VmService.js` | operace nad virtuálními stroji |
| `NodeService.js` | operace nad uzly |
| `AutomationService.js` | automatizační úlohy |

---

## Princip fungování

Typická servisní funkce:

1. odešle HTTP požadavek pomocí `fetch`
2. převede odpověď na JSON
3. v případě chyby vyhodí výjimku

## Autentizace
Backend používá autentizaci pomocí cookie `user_token`.
Aby se tato cookie posílala s každým requestem, musí mít fetch nastaveno:

```js
credentials: 'include'
```