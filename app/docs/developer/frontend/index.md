# Frontend

Frontend je postavený na Reactu a slouží jako uživatelské rozhraní pro správu serverů, nodů, virtuálních strojů a automatizací.

## Architektura

Aplikace je rozdělena podle odpovědnosti:

| Vrstva | Účel |
|---|---|
| `pages/` | skládají obrazovky aplikace |
| `components/` | zobrazují UI a části funkcionality |
| `services/` | komunikace s backend API |

## Tok dat (Data Flow)

1. Uživatel provede akci v UI  
2. Komponenta nebo page zavolá service  
3. Service odešle požadavek na backend  
4. Backend vrátí data  
5. Aktualizuje se stav aplikace  
6. UI se překreslí