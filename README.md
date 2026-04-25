# sorio-posters

Templates HTML param-driven para posters Só Rio (1080×1350).
Fonte da verdade do design. Renderizados via screenshot headless (Playwright ou Placid).

---

## Setup rápido (5 min)

```bash
cd sorio-posters
git init -b main
git add .
git commit -m "initial: f02 param-driven + assets"
# criar repo no GitHub: gh repo create sorio-posters --public --source=. --push
# OU: github.com → New repo → copiar URL → git remote add origin URL → git push -u origin main
```

Depois: netlify.com → Add new site → Import from Git → escolher repo → Deploy.
Subdomain sugerido: `sorio-posters.netlify.app` (ou domínio custom).

---

## Estrutura

```
sorio-posters/
├── index.html            ← preview + documentação viva
├── f02.html              ← Full-Color Poster (live)
├── f01.html              ← Product Hero Editorial (TBD)
├── f03.html              ← Action & Motion (TBD)
├── f05a.html             ← Editorial Grid Flat-Lay (TBD)
├── f05b.html             ← Editorial Grid Info-Graphic (TBD)
├── assets/
│   ├── logo.png
│   ├── hero-sample.png   ← placeholder para tests; em prod vem do Gemini via URL
│   ├── selo-default.png
│   └── selos/            ← 18 PNGs (6 selos × 3 variantes cromáticas)
├── netlify.toml
├── .gitignore
└── README.md
```

---

## Convenção URL

Qualquer template aceita os mesmos parâmetros base. Valores com espaços → URL encode.

| Param | Default | Notas |
|-------|---------|-------|
| `hero` | `assets/hero-sample.png` | em prod, URL absoluta de hero gerado |
| `logo` | `assets/logo.png` | |
| `selo` | `assets/selo-default.png` | ex: `assets/selos/sunset-dourado.png` |
| `title` | Caipirinha de Maracujá | `|` = quebra de linha |
| `info_top` | ingredientes default | tracked caps |
| `accent` | Sem pressa. Com rio. | italic Cormorant |
| `info_bottom` | Valada do Ribatejo · sorio.pt | tracked dourado |
| `display_size` | 108 | px |
| `accent_size` | 46 | px |
| `overlay_strength` | 1.0 | 0.0-1.5 multiplica gradient |
| `hero_position` | center | CSS bg-position |
| `show_logo` | 1 | 0 = hide |
| `show_selo` | 1 | 0 = hide |
| `show_accent` | 1 | 0 = hide |
| `show_hairline` | 1 | |
| `show_wave` | 1 | |
| `show_info_top` | 1 | |
| `show_info_bottom` | 1 | |

---

## Render

### Via Playwright (recomendado, self-hosted)

```js
const { chromium } = require('playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 2 });
await page.goto('https://sorio-posters.netlify.app/f02.html?title=Mojito&...');
await page.screenshot({ path: 'out.png', omitBackground: false });
await browser.close();
```

### Via Placid (fallback)

Criar template Placid com 1 picture layer (`picture_main`). API:

```json
{
  "template_uuid": "...",
  "layers": {
    "picture_main": {
      "image": "https://sorio-posters.netlify.app/f02.html?title=Mojito&...",
      "image_viewport": "1080x1350"
    }
  }
}
```

---

## Desenvolvimento local

```bash
# simple server (qualquer um serve, desde que seja localhost real — não file://)
python3 -m http.server 8080
# abrir http://localhost:8080/f02.html?title=Teste
```

Google Fonts pode falhar se file:// — sempre usar servidor.

---

## Próximos passos

1. **[HOJE]** Push inicial + Netlify link
2. **[HOJE]** Escrever f01/f03/f05a/f05b
3. Claude Decisor system prompt (usa `blueprint_sorio.json`)
4. Orchestrator Playwright
5. Gate Vision Critique antes de publicar

---

Bolder AI · Creative Studio · Blueprint Só Rio v1.5
