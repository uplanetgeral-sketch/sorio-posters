# Design System · Só Rio

Dois artefactos que tornam o Claude Decisor + Vision Critique inteligentes.

```
design/
├── design_principles_sorio.json   ← 25 regras universais (defensivo)
└── design_references/             ← biblioteca de refs validadas (aspiracional)
    ├── _index.json                ← catálogo
    ├── _inbox/                    ← drop zone para novas refs
    ├── _docs/                     ← schema + how-to-add
    ├── _scripts/                  ← add_reference.py helper
    └── ref_NNN_*/                 ← refs individuais (poster.png + metadata.json)
```

---

## Como o pipeline usa estes ficheiros

### Claude Decisor (Fase D)

System prompt do Decisor recebe DOIS inputs:
1. `blueprint_sorio.json` — o que a marca É (paleta, tipografia, claims, selos, famílias)
2. `design_principles_sorio.json` + `design_references/_index.json` — COMO tomar boas decisões

Ao decidir layout para um produto, o Decisor:
- Aplica os 25 princípios como guardrails (rejeita decisões que violam principles críticos)
- Faz query no `_index.json` por refs com tags compatíveis (`{family: F02, mood: evening_riverside, category: BEBIDA}`) → puxa 2-3 refs como inspiration visual
- Output: JSON de decisão com `principle_match` (que princípios respeita) + `inspired_by` (que refs orientaram a decisão)

### Vision Critique Loop (Fase E)

Recebe o PNG renderizado + os 25 princípios como rubric. Output:
- `score`: 0-100 (calculado pelos pesos definidos em `scoring_rubric`)
- `violations`: lista de IDs de princípios violados + severidade
- `closest_ref`: ref mais próxima da biblioteca (similarity match)
- `suggested_fixes`: cada violação tem fix concreto (ex: "TYPO-01: display_size 180→110 para 16 chars")

### Boldy

Os mesmos JSONs alimentam:
- Sliders com warnings em tempo real ("violação TYPO-03 detectada")
- Botão "Add to refs library" que escreve metadata directamente no _index.json + push
- "Why this layout?" que mostra refs e principles que justificaram a decisão do Decisor

---

## Curadoria

A biblioteca de refs é estritamente curada pelo Gonçalo. Não auto-popula. Quantidade < qualidade.

Para adicionar refs: ver `design_references/_docs/HOW_TO_ADD.md`.

---

## Versionamento

`design_principles_sorio.json` tem `schema_version`. Bumpar quando houver breaking changes ao schema (não quando se adiciona regras — isso só altera `last_updated`).

`_index.json/references` cresce monotonicamente. Refs nunca são apagadas — quando deprecadas, ficam com tag `deprecated` em vez de remoção (preserva histórico).
