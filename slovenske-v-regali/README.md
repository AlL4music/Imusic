# Slovenské v regáli

Statická webová stránka v slovenčine, ktorá pomáha bežnému zákazníkovi rozoznať
slovenské značky v obchode podľa kategórií. Postavená na [Astro](https://astro.build/).

## Štart

Predpoklad: Node.js 20+ a npm.

```bash
cd slovenske-v-regali
npm install
npm run dev
```

Web bude dostupný na `http://localhost:4321`.

## Build

```bash
npm run build      # vygeneruje statickú stránku do dist/
npm run preview    # lokálne náhľad zostaveného webu
```

## Pridanie značky

Každá značka je samostatný markdown súbor v `src/content/brands/`. Pridanie
novej značky vyžaduje len vytvorenie nového súboru – netreba meniť kód.

```yaml
---
name: "Rajo"
category: "mliecne-vyrobky"
ownership: "made-in-sk-foreign-owned"
website: "https://www.rajo.sk"
region: "Bratislava"
founded: 1949
logo: "/logos/rajo.png"     # voliteľne, súbor v public/logos/
---

Krátky popis značky v slovenčine (2–3 vety).
```

### Povinné polia

- `name` – názov značky
- `category` – slug jednej z 16 kategórií (pozri `src/data/categories.ts`)
- `ownership` – jedna z troch hodnôt:
  - `slovak` – slovenská značka, slovenský vlastník, vyrobené v SR
  - `made-in-sk-foreign-owned` – vyrobené v SR, zahraničný vlastník
  - `slovak-brand-made-abroad` – slovenská značka, vyrobené v zahraničí

### Voliteľné polia

- `website` – URL výrobcu
- `region` – mesto / kraj
- `founded` – rok založenia
- `logo` – cesta k logu (relatívne k `public/`)
- `featured` – `true` / `false`

### Kategórie

Kategórie sú definované v `src/data/categories.ts`. Pridanie novej kategórie
vyžaduje úpravu tohto súboru (a content schema sa o slug postará automaticky
po reštarte dev servera).

## Štruktúra projektu

```
slovenske-v-regali/
├── public/                   # statické súbory (favicon, logá, robots.txt)
├── src/
│   ├── components/           # Astro komponenty (BrandCard, Header, ...)
│   ├── content/
│   │   ├── config.ts         # schema content collections
│   │   └── brands/           # markdown súbory so značkami
│   ├── data/
│   │   ├── categories.ts     # zoznam kategórií
│   │   └── ownership.ts      # 3 typy pôvodu / vlastníctva
│   ├── layouts/
│   ├── pages/
│   │   ├── index.astro
│   │   ├── ako-citat-etiketu.astro
│   │   ├── o-projekte.astro
│   │   ├── 404.astro
│   │   └── kategoria/[slug].astro
│   └── styles/global.css
├── astro.config.mjs
└── package.json
```

## Deploy na GitHub Pages

V repozitári je workflow `.github/workflows/deploy-slovenske-v-regali.yml`,
ktorý buildne web a publikuje ho na GitHub Pages pri pushi do `main`.

Pred prvým deployom:

1. V Settings → Pages nastav „Build and deployment / Source" na
   **GitHub Actions**.
2. Workflow pri builde automaticky nastaví `BASE_PATH` na
   `/<repo-name>/`, aby cesty fungovali pri publikovaní na
   `https://<user>.github.io/<repo-name>/`.

Ak chceš deploy na vlastnú doménu (root path), nastav repository variable
`BASE_PATH=/` v Settings → Secrets and variables → Actions a uprav workflow,
aby ho použil.

## Licencia

Obsah na webe je informatívny a údaje môžu obsahovať chyby. Vždy si pôvod
výrobku over priamo na obale.
