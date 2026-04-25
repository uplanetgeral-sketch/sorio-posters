# Como adicionar um produto · 4 caminhos

---

## Caminho 1 · Via Boldy (recomendado quando estiver pronto)

**Estado:** backlog Boldy — Fase E.

**UX prevista:**

1. Boldy → tab **Catalogue**
2. Botão **+ Add Product**
3. Form steps:
   - Step 1: Drop / select object sheet PNG (gerado anteriormente via Object Sheet Maker prompt)
     - OU Step 1 alternativo: "Don't have object sheet → start blank" → entra direto no form manual
   - Step 2: (auto-correu Claude Vision sobre o object sheet) — preenchimento prévio dos campos: name, ingredients canonical, garnish inside/outside, dominant colors. Tu validas e ajustas.
   - Step 3: Mood, selo recommendation, claim recommendations (multi-input)
   - Step 4: Family compatibility (5 sliders ideal/good/acceptable/avoid)
   - Step 5: Notes, season, preview
4. Save → cria `produtos/<id>/` com tudo, commita ao repo, push automático
5. Netlify rebuild ~30s, Decisor já tem acesso

**Impacto:** zero fricção, < 2 min por produto, base de dados cresce com o trabalho.

---

## Caminho 2 · Drop object sheet no `_inbox/`

**Quando usar:** já criaste o object sheet (na Boldy ou via Gemini directo) e queres adicionar agora sem esperar pela UI da Boldy.

```
1. arrastar object_sheet PNG → catalogue/_inbox/
2. (opcional) renomear: caipirinha_maracuja.png ou mojito.png — slug do produto
3. (opcional) escrever caipirinha_maracuja.txt com 2-3 linhas de notas
4. próxima sessão Claude: dizer "processa o catalogue inbox"
```

Eu (Claude) corro Vision sobre cada PNG, extraio metadata, peço-te confirmação dos campos críticos via tool de questions, gero `produtos/<id>/` completo e movo o object sheet para lá. Tu validas no fim.

---

## Caminho 3 · Script Python `ingest_object_sheet.py` (semi-auto)

**Quando usar:** queres adicionar 1-3 produtos imediatamente, sem esperar uma sessão.

Pré-requisito (uma vez): `pip install anthropic` e `export ANTHROPIC_API_KEY=sk-ant-...`

```bash
cd sorio-posters
python3 catalogue/_scripts/ingest_object_sheet.py PATH/TO/object_sheet.png
```

O script:
1. Envia o PNG ao Claude Vision com prompt de extracção
2. Recebe JSON estruturado (ingredientes, garnish, visual_dna, dominant colors)
3. Pergunta-te interactivamente os campos editoriais (mood, selo, claims, family compat)
4. Cria `produtos/<id>/product.json` + `vision_analysis.json` + copia object sheet
5. Adiciona entry em `_index.json` + actualiza stats
6. Imprime comando git para fazeres push

Tempo médio: 2-3 min por produto. ~$0.005 por produto em custos Claude API.

---

## Caminho 4 · Manual full-control (sem Vision)

**Quando usar:** ainda não tens object sheet mas queres registar o produto na catalogue para o Decisor já ter info textual. Útil para produtos novos que aparecem em menus antes de serem fotografados.

```
1. Criar produtos/<id>/ manualmente (id = slug ASCII snake_case)
2. Criar product.json com schema mínimo válido (ver SCHEMA.md)
3. Adicionar entry em _index.json
4. Increment stats
5. git push
```

Mais tarde, quando criares o object sheet, fazes update incremental: drop em `_inbox/` ou corre o script direccionado àquele product id.

---

## Object Sheet — o que é e como é gerado

Object Sheet = grelha 2×3 (6 cells) padronizada que documenta visualmente um produto:
- **Cells 1-4** · 4 ângulos do produto (cenital 0° / 3/4 front 35° / side 90° / high 65°)
- **Cells 5-6** · close-ups detalhe **com contexto** (não ingredientes isolados em fundo branco — antes plano próximo do produto a mostrar texturas/sementes/garnish)

Geração:
- **Via Boldy** — botão "Object Sheet" usa o Object Sheet Maker prompt em `bolder-creative-studio/main.js` (versão refinada na sessão 24 Abril)
- **Manual** — copiar prompt de `bolder-creative-studio/main.js` para Gemini Flash directamente

Output: PNG/JPG ~1024×1536 (proporção 2×3 cells). Nome sugerido: `<product_id>.png`.

---

## Numeração / IDs de produtos

`id` = slug ASCII snake_case. Sem acentos. Sem espaços.

Exemplos:
- `caipirinha_maracuja` (não `caipirinha-de-maracujá`)
- `philly_cheesesteak`
- `ginja_spritz`
- `mesa_chef_set` (para sets/ofertas)

Não é numerado (ao contrário das refs em `design_references/ref_NNN_*`). O id descritivo é a chave.

---

## Onde os assets vivem

```
catalogue/
├── _index.json
├── _inbox/                          ← drop zone temporária (PNGs object sheets)
├── _docs/                           ← schema, how-to, este doc
├── _scripts/                        ← ingest_object_sheet.py
└── produtos/
    └── <product_id>/
        ├── product.json             ← ★ canonical info
        ├── object_sheet.png         ← (opcional, mas ideal) grelha 2×3 visual
        ├── vision_analysis.json     ← cache Claude Vision output
        ├── thumb.jpg                ← opcional, 240x180 para previews UI
        └── approved_heroes/         ← bons heroes aprovados (cresce ao longo do tempo)
            ├── caipirinha_evening_01.png
            └── caipirinha_midday_01.png
```

---

## Integração com Boldy (para devs)

Quando a Boldy precisa de saber o que existe na catalogue:

```javascript
// Boldy startup
const idx = await fetch('https://sorio-posters.netlify.app/catalogue/_index.json').then(r => r.json());
this.products = idx.products;

// User selects product
const prod = await fetch(`https://sorio-posters.netlify.app/catalogue/produtos/${id}/product.json`).then(r => r.json());

// Decisor call inclui prod no payload
const decision = await callDecisor({
  product: prod,
  blueprint: this.blueprint,
  principles: this.principles,
  refs_pool: this.refs,
  creative_freedom: this.creativeFreedom,
});
```

Para Boldy "Add product" UI, ver task #32 backlog.

---

## TL;DR

Tens object sheet pronto → Caminho 2 (drop inbox) ou 3 (script).
Não tens object sheet ainda → Caminho 4 (manual mínimo) e enriqueces depois.
A Boldy estiver pronta → Caminho 1 (UI completa, zero fricção).
