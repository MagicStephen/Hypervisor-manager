# Spuštění frontendu

Frontend je implementován jako React aplikace a vyžaduje prostředí Node.js a správce balíčků npm.

## Instalace závislostí

Po stažení projektu je nutné nainstalovat závislosti:

```bash
npm install
```

## Spuštění aplikace

Aplikaci lze spustit ve vývojovém režimu pomocí:

```bash
npm start
```

Frontend bude dostupný na adrese: http://localhost:3000

## Build pro produkci

Pro vytvoření produkční verze aplikace slouží:

```bash
npm run build
```

Výsledné soubory jsou uloženy ve složce `build/`.

## Napojení na backend

Frontend komunikuje s backendem prostřednictvím REST API běžícího na portu `8000`.  