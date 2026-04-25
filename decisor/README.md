# Decisor · O cérebro

Recebe um produto + brief criativo. Devolve JSON layout-ready que qualquer dos 5 templates HTML (F01/F02/F03/F05a/F05b) renderiza directamente.

---

## Estrutura

```
decisor/
├── README.md              ← este ficheiro
├── system_prompt.md       ← prompt completo para Claude API
├── output_schema.json     ← JSON schema do output (validação)
├── example_call.py        ← exemplo Python end-to-end
└── examples/
    ├── input_caipirinha_standard.json
    ├── output_caipirinha_standard.json
    ├── input_mojito_variation.json
    └── output_mojito_variation.json
```

---

## Inputs do Decisor

Carregados como contexto (system + tool_use) ou descritos como links no system prompt:

| Recurso | URL |
|---|---|
| Blueprint | `https://sorio-posters.netlify.app/design/blueprint_sorio.json` (a deployar) |
| Principles | `https://sorio-posters.netlify.app/design/design_principles_sorio.json` |
| Creative modes | `https://sorio-posters.netlify.app/design/creative_modes.json` |
| Refs library | `https://sorio-posters.netlify.app/design/design_references/_index.json` |
| Catalogue | `https://sorio-posters.netlify.app/catalogue/_index.json` |
| Per produto | `https://sorio-posters.netlify.app/catalogue/produtos/<id>/product.json` |

---

## User message format

Cada chamada ao Decisor recebe:

```json
{
  "product_id": "caipirinha_maracuja",
  "creative_freedom": 0.15,
  "format": "instagram_post_1080x1350",
  "brief_extra": "Post para Sexta · meio de tarde",
  "previous_decisions": ["ref_010", "ref_024"]
}
```

`previous_decisions` é a lista de refs usadas nas decisões anteriores recentes — usado pelo Decisor para `diversity_sampling` (não puxar sempre as mesmas refs).

---

## Output

Ver `output_schema.json` para schema completo. Estrutura sumária:

```json
{
  "decision_id": "20260425_133015_caipirinha",
  "product_id": "caipirinha_maracuja",
  "mode": "standard",
  "creative_freedom": 0.15,
  "family": "F02",
  "rationale": "string · porque esta família",
  "url_params": { /* todos os params para o template HTML */ },
  "inspired_by": ["ref_024", "ref_026"],
  "principles_applied": ["UNI-01", "TYPO-01", ...],
  "principles_relaxed": [],
  "experimentation_log": null,
  "vision_critique_brief": "...",
  "human_review_required": false
}
```

---

## Como chamar (Python)

```python
from anthropic import Anthropic
import json, requests

# Carrega inputs
def fetch(url): return requests.get(url).json()
product = fetch(f"https://sorio-posters.netlify.app/catalogue/produtos/caipirinha_maracuja/product.json")
principles = fetch(f"https://sorio-posters.netlify.app/design/design_principles_sorio.json")
modes = fetch(f"https://sorio-posters.netlify.app/design/creative_modes.json")
refs = fetch(f"https://sorio-posters.netlify.app/design/design_references/_index.json")

# Read system prompt
with open("decisor/system_prompt.md") as f: SYSTEM = f.read()

# Build user message
user_payload = {
  "product_id": "caipirinha_maracuja",
  "creative_freedom": 0.15,
  "product": product,
  "principles": principles,
  "creative_modes": modes,
  "refs_index": refs
}

client = Anthropic()
response = client.messages.create(
  model="claude-sonnet-4-5",
  max_tokens=4096,
  system=SYSTEM,
  messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}]
)
decision = json.loads(response.content[0].text)
```

---

## Como Boldy usa

1. User abre Boldy, escolhe produto da catalogue (UI shows `_index.json` cards)
2. Slider creative_freedom (Daily Drop / Fresh Take / Bold Move presets)
3. User clica "Generate posters" — Boldy chama Decisor (uma chamada por slot, e.g. 5 slots = 5 chamadas paralelas com `previous_decisions` partilhado para diversity)
4. Cada decisão returned → Boldy:
   a. Compõe URL com `url_params` para o template HTML correcto
   b. Pede ao Designer (Gemini) para gerar hero usando `product.object_sheet` como visual reference + garnish constraints
   c. Hero pronto → Boldy substitui `hero=` no URL
   d. Playwright screenshota URL @ 1080×1350 → PNG final
5. Vision Critique Loop (Fase E) avalia cada PNG contra principles
6. Se score < threshold do mode → re-gera ou pede revisão humana

---

## Custos esperados

Por decisão (Sonnet 4.5):
- ~3-5k input tokens (system + product + refs index + principles)
- ~1k output tokens (decision JSON)
- ~$0.015-0.020 por chamada

Para 5 posters por produto: ~$0.10
Para 10 produtos × 5 posters/cada: ~$1.00 total

Bem abaixo do custo de criar manualmente.

---

## Versionamento

`system_prompt.md` tem header com `version` e `last_updated`. Bump quando o output schema mude breaking.

A1 (Decisor v1) é Standard-mode-first. A2 acrescentará lógica refined para Variation/Experimental quando experimentation_log tiver dados suficientes (~50 decisions).
