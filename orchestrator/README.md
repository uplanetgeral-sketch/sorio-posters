# Orchestrator · Pipeline end-to-end self-hosted

Single command que faz: produto → Decisor → Playwright screenshot → Critique → auto-fix loop → poster final.

Substitui o screenshot manual + sips + 2-3 commands separados por uma única chamada.

---

## Estrutura

```
orchestrator/
├── README.md              ← este ficheiro
├── main.py                ← entry point
├── stages/                ← cada stage isolado e testável
│   ├── decisor.py         ← chamada Decisor
│   ├── render.py          ← Playwright screenshot
│   ├── critique.py        ← chamada Critique
│   └── fix.py             ← aplicar suggested_fixes ao decision
├── outputs/               ← poster_TIMESTAMP/ folders
│   └── <run_id>/
│       ├── poster_final.png
│       ├── decision_v1.json
│       ├── decision_v2.json     ← se houve auto-fix iteration
│       ├── critique_v1.json
│       ├── critique_v2.json
│       └── run_log.json         ← timeline + custos
└── examples/
```

---

## Uso

Single command:

```bash
cd sorio-posters
python3 orchestrator/main.py PRODUCT_ID [--mode standard|variation|experimental] [--max-iter 3] [--auto-fix]
```

Defaults: `--mode standard`, `--max-iter 2`, `--auto-fix` ON.

Exemplo:

```bash
python3 orchestrator/main.py cloud_dance --mode standard
```

Output stdout (live progress):

```
[1/4] DECISOR · Cloud Dance · standard · freedom 0.15
      → F02 · inspired by ref_024, ref_026, ref_028
[2/4] RENDER · Playwright headless 1080×1350
      → out/run_20260425_153000/poster_v1.png (5.6 MB → resize to 4.2 MB)
[3/4] CRITIQUE
      → score 78/100 · 1 critical (ANTI-01) · 1 major (COMP-03)
[4/4] AUTO-FIX iter 1
      → applying COMP-03 fix: overlay_strength 1.1 → 1.4
      → re-render
      → critique iter 2: score 85/100 · 1 critical remains
      → human_review_required = TRUE (critical violation persists)
✓ DONE · run_id=20260425_153000 · final score 85
✓ Outputs em outputs/20260425_153000/
```

---

## Custos por run

- Decisor 1 chamada: ~$0.015
- Critique 1 chamada (com vision): ~$0.020
- Auto-fix iter (1-2 extra): ~$0.030-0.040
- **Total por produto:** $0.05–0.08

5 posters por produto × 10 produtos = ~$3-4 / batch completo do feed.

---

## Auto-fix logic

A cada iteração:
1. Filtra `suggested_fixes` por aqueles com `url_param_change != null` (não Designer regen — esse precisa Gemini)
2. Aplica os param changes ao `url_params` da decisão
3. Re-render → re-critique
4. Se score subiu E não há critical violations → publishable
5. Se max-iter atingido OU score plateau → para com human_review_required=true

Designer regen (negative_prompt) não é aplicado automaticamente nesta v1 — fica registado em `human_review_required` para o user trabalhar no Boldy/Gemini manualmente.

---

## Dependências

```
pip3 install anthropic requests jsonschema playwright
playwright install chromium
```

(Já tens anthropic + requests + jsonschema do passo anterior. Falta playwright.)

---

## Como Boldy usa

Boldy chama o orchestrator como subprocess:

```javascript
const { spawn } = require('child_process');
const proc = spawn('python3', ['orchestrator/main.py', productId, '--mode', mode]);
proc.stdout.on('data', (line) => updateUI(line));
proc.on('close', () => {
  const result = JSON.parse(fs.readFileSync(`outputs/${runId}/run_log.json`));
  showPoster(result.final_png, result.final_score, result.violations);
});
```

Ou Boldy importa as stages directamente como Python módulo se for embebido.
