# Vision Critique Loop · O guardião

Recebe o PNG renderizado + a decisão do Decisor + a knowledge base. Devolve score + violations + closest ref + suggested fixes accionáveis.

É o gate de qualidade antes de publicar.

---

## Estrutura

```
critique/
├── README.md              ← este ficheiro
├── system_prompt.md       ← prompt para Claude com vision
├── output_schema.json     ← JSON schema do output
├── example_call.py        ← script Python end-to-end
└── examples/
    ├── critique_input_cloud_dance.json
    └── critique_output_cloud_dance.json
```

---

## Inputs

| Recurso | De onde vem |
|---|---|
| PNG do poster | local file (output Playwright/screenshot) ou URL pública |
| Decisão Decisor | output da chamada anterior (todo o JSON) |
| Principles | `https://sorio-posters.netlify.app/design/design_principles_sorio.json` |
| Refs index | `https://sorio-posters.netlify.app/design/design_references/_index.json` |

---

## Output

```json
{
  "critique_id": "20260425_140530_cloud_dance",
  "decision_id": "...",
  "product_id": "cloud_dance",
  "family_critiqued": "F03",
  "mode_evaluated": "standard",

  "score": 87,
  "publishable": true,
  "publishable_threshold": 75,

  "violations": [
    {
      "principle_id": "TYPO-04",
      "severity_in_mode": "major",
      "evidence": "info_top tem 32 chars · respeitado",
      "score_impact": 0
    }
  ],
  "principles_passed": ["UNI-01", "UNI-04", "TYPO-01", "FAM-F03-01", "ANTI-01", ...],

  "closest_ref": "ref_010_negroni_week_mombasa_editorial",
  "closest_ref_similarity": 0.78,
  "closest_ref_notes": "Hero subject lower-third + tracked caps subtitle + dark bg + restraint absoluta",

  "suggested_fixes": [
    {
      "issue": "string",
      "fix_action": "string",
      "url_param_change": {"param": "value"}
    }
  ],

  "vision_summary": "Texto curto descrevendo o que o critic viu",
  "human_review_required": false
}
```

---

## Como chamar

```python
from anthropic import Anthropic
import base64, json, requests

# 1. Load PNG (local file ou fetch URL)
with open("poster_final.png", "rb") as f:
    image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

# 2. Load decision (do Decisor anterior)
with open("decision.json") as f:
    decision = json.load(f)

# 3. Fetch principles + refs index
def fetch(url): return requests.get(url).json()
principles = fetch("https://sorio-posters.netlify.app/design/design_principles_sorio.json")
refs = fetch("https://sorio-posters.netlify.app/design/design_references/_index.json")

# 4. Read system prompt
with open("critique/system_prompt.md") as f: SYSTEM = f.read()

# 5. Build payload + call
client = Anthropic()
response = client.messages.create(
  model="claude-sonnet-4-5",
  max_tokens=4096,
  system=SYSTEM,
  messages=[{
    "role": "user",
    "content": [
      {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
      {"type": "text", "text": json.dumps({
        "decision": decision,
        "principles": principles,
        "refs_index": refs,
      }, ensure_ascii=False)}
    ]
  }]
)
critique = json.loads(response.content[0].text)
```

---

## Como Boldy usa

1. Decisor produz decisão → URL para template HTML
2. Designer (Gemini) gera hero → injectado no URL
3. Playwright screenshota URL @ 1080×1350 → poster.png local
4. **Critique chamado com poster.png + decision JSON**
5. Critic returns:
   - `score >= publishable_threshold` (75 standard, 70 variation, 60 experimental) → publish-ready, mostra o poster ao user
   - `score < threshold` → mostra issues + suggested_fixes; user decide: aplicar fix automaticamente OU re-gerar OU ignorar
6. Se `human_review_required: true` (modo experimental) → sempre passa por user antes de publicar

Boldy mostra o critique **lado a lado** com o poster:
- Score badge (verde/amarelo/vermelho)
- Lista de issues clicáveis (cada um liga ao slider/param que pode ajustar)
- Botão "Apply all fixes" + "Re-generate" + "Approve as is"

---

## Custo esperado

Por critique (Sonnet 4.5 com vision):
- ~3-4k input tokens (system + decision + principles + refs index)
- ~500 output tokens (critique JSON)
- 1 imagem 1080×1350 ≈ ~1500 tokens
- ~$0.020 por critique

5 posters × 1 critique cada = $0.10/produto
+ Decisor $0.10/produto = $0.20 total/produto

Para 10 produtos × 5 posters = ~$2 total feed completo (worst case).

---

## Versionamento

`system_prompt.md` tem `version`. Bump quando output schema mude breaking ou quando rubric weights mudarem significativamente.
