# Components

Složka `components/` obsahuje UI komponenty rozdělené podle účelu a domény.

| Složka | Účel |
|---|---|
| `charts/` | grafy a vizualizace metrik |
| `common/` | obecné komponenty, např. spinner nebo button |
| `consoles/` | komponenty pro konzole |
| `forms/` | formuláře a formulářové prvky |
| `infrastructure/` | stromová sestava infrastruktury |
| `node/` | komponenty pro nody |
| `server/` | komponenty pro servery |
| `vm/` | komponenty pro virtuální stroje |

## Typy komponent

| Typ | Popis |
|---|---|
| Sdílené komponenty | obecné komponenty použitelné napříč aplikací |
| Doménové komponenty | komponenty navázané na konkrétní část systému |
| Kontejnerové komponenty | načítají data, drží stav a skládají menší komponenty |
| Prezentační komponenty | hlavně zobrazují data |

## Aktualizace dat

Kontejnerové komponenty pro získávání metrik z uzlů a virtuálních strojů (ve složkách `node/` a `vm/`) obsahují logiku pro automatickou aktualizaci dat.

- dynamická data (např. CPU, RAM, disk nebo status) se periodicky obnovují
- aktualizace probíhá pouze za určitých podmínek (pokud je VM ve stavu `running`)
- polling se automaticky zastaví při změně stavu nebo unmountu komponenty

**Typické chování:**

- statická data se načtou jednorázově při inicializaci
- runtime metriky se pravidelně obnovují