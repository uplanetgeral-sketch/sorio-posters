# SCHEMA · `metadata.json` por referência

Cada `ref_NNN_*/metadata.json` segue este schema. Campos obrigatórios marcados ★.

---

## Estrutura

```json
{
  "id": "ref_007_caipirinha_evening_aprovado",            // ★ slug único
  "title": "Caipirinha de Maracujá · evening · F02",       // ★ descrição curta
  "image": "poster.png",                                   // ★ filename relativo dentro da pasta
  "thumbnail": "thumb.jpg",                                // opcional: 320×400 jpg para previews rápidos

  "source": "own_production",                              // ★ enum: own_production | competitor_study | editorial_external | packaging_external | art_direction_external
  "source_attribution": "Sessão 23 Abril 2026 — Bolder AI",// ★ se external, autor + ano + nome trabalho + URL pública
  "source_url": "https://...",                             // opcional: link à fonte original (refs externas)
  "copyright_notice": "Reference for design study. Not for redistribution.",  // ★ se external

  "added_date": "2026-04-25",                              // ★ YYYY-MM-DD
  "approved_by": "Gonçalo Carvoeiras",                     // ★ curador

  "tags": ["bebida", "F02", "evening", "wood_deck", "selo_dourado"],  // ★ free-form, sem limites

  "family": "F02",                                         // ★ enum: F01 | F02 | F03 | F05a | F05b | external
  "category": "BEBIDA",                                    // ★ enum: PRATO | BEBIDA | AMBIENTE | EDITORIAL
  "mood": "evening_riverside",                             // enum: fresh_midday | aperitivo_18h | evening_riverside | n/a

  "typography_summary": "Oswald Bold 130px + Cormorant italic 46px + Inter 22px tracked",
  "composition_summary": "Hero subject lower-third, masthead simétrico top",
  "color_palette_summary": "Madeira queimada + dourado + off-white",

  "why_good": [                                            // ★ 3-5 razões específicas
    "Tipografia 100% fiel ao Blueprint",
    "Hero off-center (terço inferior)",
    "Restraint decorativo absoluto"
  ],
  "caveats": [                                             // opcional: o que NÃO copiar
    "Não imitar literal — usar para balance, não para layout exacto"
  ],

  "principle_match": ["UNI-01", "TYPO-01", "FAM-F02-01"],  // opcional: lista de principles que esta ref exemplifica
  "principle_violation": []                                // opcional: principles que esta ref VIOLA mas mesmo assim funciona (uso avançado)
}
```

---

## Notas importantes

### `source` enum
- `own_production` — output Bolder AI / Só Rio. Aprovado pelo curador. Tem `poster.png` embebido.
- `competitor_study` — analisado no Blueprint (Comporta Café, Sublime Comporta, Scorpios Mykonos). Texto + tags + URL fonte. Imagem opcional só se uso justificável.
- `editorial_external` — magazines (Kinfolk, Cereal, Drift), packaging fotos, posters de hospitality. Texto + URL. Sem embed por copyright.
- `packaging_external` — bottles, labels, menu cards admiraveis. Idem.
- `art_direction_external` — direcção de arte de campanhas (não posters específicos), film stills, fashion editorials. Idem.

### Tags úteis (não exaustivo)
- Categoria: `bebida`, `prato`, `ambiente`, `lifestyle`
- Mood: `morning`, `midday`, `aperitivo`, `evening`, `night`
- Visual: `motion`, `flat-lay`, `close-up`, `wide`, `editorial-grid`
- Cor: `dark`, `light`, `warm`, `cool`, `monochromatic`
- Tipografia: `display-dominant`, `hero-dominant`, `minimal`, `decorative`
- Composição: `centered`, `off-center`, `symmetric`, `asymmetric`, `rule-of-thirds`
- Material: `wood`, `linen`, `stone`, `water`, `glass`

### `principle_match`
Lista de IDs de princípios em `design_principles_sorio.json` que esta ref exemplifica bem. Útil para o Decisor: "preciso de exemplo de FAM-F03-01 + COLOR-01" → query refs onde principle_match contém ambos.

### `principle_violation`
Uso avançado: refs que **violam** um princípio MAS mesmo assim funcionam (ex: títulos com 25 chars sem quebra que ficam dramáticos). Documentar permite ao Decisor aprender excepções controladas.

---

## Exemplo mínimo válido (ref própria)

```json
{
  "id": "ref_001_caipirinha_aprovado",
  "title": "Caipirinha aprovado 23 Abril",
  "image": "poster.png",
  "source": "own_production",
  "source_attribution": "Bolder AI 2026-04-23",
  "added_date": "2026-04-25",
  "approved_by": "Gonçalo Carvoeiras",
  "tags": ["bebida", "F02", "evening"],
  "family": "F02",
  "category": "BEBIDA",
  "mood": "evening_riverside",
  "why_good": [
    "Tipografia fiel ao Blueprint",
    "Hero off-center"
  ]
}
```

Tudo o resto é opcional. Mais campos = melhor matching, mas mínimo viável é isto.
