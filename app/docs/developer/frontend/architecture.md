# Frontend – architektura

Frontend je rozdělený podle odpovědnosti.

| Vrstva | Účel |
|---|---|
| `pages/` | skládají obrazovky aplikace |
| `components/` | zobrazují UI a části funkcionality |
| `services/` | volají backend API |

## Data flow

1. Uživatel provede akci v UI
2. Page nebo komponenta zavolá service
3. Service odešle request na backend
4. Backend vrátí data
5. Komponenta aktualizuje state
6. UI se překreslí