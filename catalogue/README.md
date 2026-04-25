# Catalogue · Só Rio Menu DNA

Catálogo de produtos do menu Só Rio. Complemento essencial ao Blueprint (que tem brand DNA mas não menu).

```
catalogue/
├── README.md                     ← este ficheiro
├── _index.json                   ← lista de produtos (consumida pelo Decisor)
├── _inbox/                       ← drop zone para object sheets de novos produtos
├── _docs/
│   ├── SCHEMA.md                 ← schema product.json
│   └── HOW_TO_ADD.md             ← 4 caminhos para adicionar produtos
├── _scripts/
│   └── ingest_object_sheet.py    ← Vision-powered helper
└── produtos/                     ← produtos individuais
    └── <product_id>/
        ├── product.json          ← canonical menu info
        ├── object_sheet.png      ← grelha 2×3 visual
        ├── vision_analysis.json  ← Claude Vision cached output
        └── approved_heroes/      ← bons heroes aprovados
```

---

## Filosofia

- **Blueprint** (em `blueprint_sorio.json`) = Brand DNA · paleta, tipografia, claims, selos, famílias visuais.
- **Catalogue** (esta pasta) = Menu DNA · que produtos existem, ingredientes reais, garnish, mood, family compatibility.
- **Design system** (em `design/`) = Gosto e regras · principles, refs, creative_modes.

Os 3 são consumidos pelo Decisor em runtime via HTTPS (Netlify deployment).

---

## Como adicionar um produto

Ver `_docs/HOW_TO_ADD.md` para 4 caminhos:

1. **Boldy UI** (recomendado quando estiver pronto, Fase E backlog)
2. **Drop object sheet em `_inbox/`** (próxima sessão Claude processa)
3. **Script `ingest_object_sheet.py`** (semi-auto, ~2-3 min)
4. **Manual** (sem object sheet, info textual mínima)

---

## Como o Decisor usa

```javascript
// 1. Carrega catálogo
const idx = await fetch('/catalogue/_index.json').then(r => r.json());

// 2. User selecciona produto
const prod = await fetch(`/catalogue/produtos/${id}/product.json`).then(r => r.json());

// 3. Decisor recebe TUDO
const decision = await callDecisor({
  product: prod,                     // ← menu DNA
  blueprint: this.blueprint,         // ← brand DNA
  principles: this.principles,       // ← regras
  refs: this.refs,                   // ← gosto
  creative_freedom: 0.3,             // ← modo
});
```

Decisor agora pode escrever:
> "F02 evening_riverside, selo sunset-dourado, ingredientes: Maracujá · Lima · Cachaça · Mel.
> Garnish da composição: passionfruit shell + ice spray AO REDOR do copo (NUNCA dentro:
> warning_never_inside informa que não há thyme/rosemary). Hero subject lower-third
> conforme visual_dna.subject_position_default."

Outputs deixam de ser genéricos e passam a ser fiéis à casa.

---

## Versionamento

`schema_version` no `_index.json`. Bump em breaking changes.
Produtos descontinuados ficam `active: false`, não são apagados.
