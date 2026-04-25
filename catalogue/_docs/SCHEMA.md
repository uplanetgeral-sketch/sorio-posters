# SCHEMA · `product.json` por produto

Cada `produtos/<id>/product.json` segue este schema. Campos obrigatórios marcados ★.

---

## Estrutura completa

```json
{
  "id": "caipirinha_maracuja",                  // ★ slug ASCII, snake_case, único
  "name": "Caipirinha de Maracujá",             // ★ display name PT-PT com acentos
  "category": "BEBIDA",                          // ★ BEBIDA | PRATO | AMBIENTE | RITUAL
  "subcategory": "cocktail",                     // ★ cocktail | spritz | wine | snack | main | dessert | sandwich | salad
  "active": true,                                // ★ boolean — false = sazonal/descontinuado mas guardado

  "ingredients": {                               // ★
    "canonical": [                               // lista canónica (todos os ingredientes reais)
      "Maracujá fresco",
      "Lima",
      "Cachaça reserva",
      "Mel do Ribatejo"
    ],
    "display_short": "Maracujá · Lima · Cachaça · Mel",   // ≤36 chars (TYPO-04)
    "display_long": "Maracujá fresco · Lima · Cachaça reserva · Mel do Ribatejo",
    "highlight": "Mel do Ribatejo"               // o ingrediente "story" — destaque
  },

  "garnish": {                                   // crítico para Designer + Vision Critique
    "inside_glass": ["lime wheel", "passionfruit pulp"],
    "outside_glass": ["passionfruit shell", "ice spray"],
    "warning_never_inside": ["thyme leaf", "rosemary"],   // explícito — anti-pattern ANTI-01
    "warning_never_present": []                  // ingredientes que nunca aparecem (ex: "umbrella")
  },

  "mood_default": "evening_riverside",           // ★ fresh_midday | aperitivo_18h | evening_riverside
  "mood_alternatives": ["aperitivo_18h"],

  "selo_recommendation": ["sunset", "ritual_so_rio"],   // ★ ranked, primeira é primary
  "selo_color_pref": "dourado",                  // dourado | creme | verde | auto (auto = COLOR-02 logic)

  "claim_recommendations": [                     // ★ pelo menos 1
    {"text": "Sem pressa. Com rio.", "context": "evening", "weight": 1.0},
    {"text": "O verão tem ritmo.", "context": "midday", "weight": 0.7}
  ],

  "visual_dna": {                                // ★ output Claude Vision sobre object sheet
    "dominant_colors": ["amber-yellow", "lime-green", "warm-wood"],
    "lighting": "warm directional, golden hour spill",
    "subject_position_default": "lower-third",
    "background_default": "wood deck blurred",
    "texture_keywords": ["glass condensation", "ice crystals", "fruit pulp seeds visible"]
  },

  "family_compatibility": {                      // ★ que famílias de poster funcionam
    "F01": "ideal",                              // ideal | good | acceptable | avoid
    "F02": "ideal",
    "F03": "good",
    "F05a": "acceptable",
    "F05b": "good"
  },

  "object_sheet": "object_sheet.png",            // ★ filename relativo à pasta do produto
  "vision_analysis": "vision_analysis.json",     // opcional: cache do Claude Vision output

  "approved_heroes": [                           // bons heroes aprovados (referenciados pelo Designer)
    "approved_heroes/caipirinha_evening_01.png"
  ],

  "notes": "Signature. Hero deve mostrar sementes do maracujá visíveis no copo.",
  "season": "all-year",                          // all-year | summer | autumn | winter | spring
  "price": null,                                 // opcional, em EUR
  "added_date": "2026-04-25",                    // ★ YYYY-MM-DD
  "last_updated": "2026-04-25"                   // ★
}
```

---

## Notas críticas

### `ingredients.display_short`
Máximo 36 caracteres (princípio TYPO-04). Vai diretamente para `info_top` nos templates HTML. Se canonical tem 5+ items, omite os secundários no display_short.

### `garnish.warning_never_inside`
Lista explícita de elementos que NUNCA aparecem dentro do copo/prato. Lição da sessão Esmeralda 24 Abril 2026 — sem este campo, Gemini introduzia folha de tomilho dentro do cocktail. Decisor passa esta lista ao Designer prompt como negative constraint.

### `garnish.inside_glass` vs `outside_glass`
- `inside_glass`: o que está realmente dentro (slices, pulp, ice). Designer deve incluir.
- `outside_glass`: o que pode flutuar à volta (shells, splashes, leaves não-comestíveis). Designer pode incluir, sempre fora do copo.
- Vision Analyst v2.3 (Weavy) já produz esta separação — copiar campo direto.

### `family_compatibility`
Não é "que famílias estão disponíveis" — é "que famílias funcionam BEM para este produto". Decisor usa para pré-filtrar opções:
- Caipirinha de Maracujá: F01/F02 ideal (cor vibrante, hero forte). F05b avoid (info-graphic não exalta cocktail bonito).
- Philly Cheesesteak: F03 ideal (motion de queijo derretido), F05b good (ingredientes destacáveis).

### `visual_dna`
Idealmente preenchido por Claude Vision sobre o `object_sheet.png`. Se preenchido manual, mais sintético é melhor — 4-6 keywords descrevem 80% do produto.

### `approved_heroes[]`
Cresce ao longo do tempo. Cada hero aprovado pelo curador (manual via Boldy "Approve" button) é guardado aqui. Designer pode fetch um destes para reuso (não regerar) OU usá-los como reference para gerar variações.

---

## Schema mínimo válido

Para um produto novo onde ainda não tens object sheet:

```json
{
  "id": "novo_produto",
  "name": "Nome do Produto",
  "category": "BEBIDA",
  "subcategory": "cocktail",
  "active": true,
  "ingredients": {
    "canonical": ["a", "b", "c"],
    "display_short": "A · B · C"
  },
  "mood_default": "evening_riverside",
  "selo_recommendation": ["ritual_so_rio"],
  "claim_recommendations": [{"text": "Sem pressa. Com rio.", "context": "default"}],
  "family_compatibility": {"F01":"good","F02":"good","F03":"good","F05a":"good","F05b":"good"},
  "object_sheet": null,
  "added_date": "2026-04-25",
  "last_updated": "2026-04-25"
}
```

Restante (visual_dna, garnish detail, approved_heroes) preenche-se à medida que se faz output.

---

## Versionamento

`schema_version` está no `_index.json`. Bump quando houver breaking changes. Adições compatíveis (novo campo opcional) não bumpam.

Produtos descontinuados ficam com `active: false` em vez de serem apagados — preserva histórico para refs futuras.
