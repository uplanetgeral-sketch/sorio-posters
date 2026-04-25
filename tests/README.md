# Só Rio · Test Battery

Bateria de testes para validar o pipeline (Decisor → Designer/hero processing → Render → Critique) através de uma matriz de combinações.

## Quick start

```bash
cd sorio-posters

# Battery completa: 1 product × 8 famílias × 3 modes = 24 runs (~15min, ~$1.70 API)
./tests/battery.sh

# Quick: 1 product × 8 famílias × 1 mode (variation) = 8 runs (~5min, ~$0.60 API)
./tests/battery.sh --quick

# Override product (precisa estar em catalogue/produtos/<id>/)
./tests/battery.sh --product caipirinha_de_maracuja

# Format diferente (default 1080x1350)
./tests/battery.sh --format 1080x1920

# Image-first com hero local (passa --hero ao orchestrator)
./tests/battery.sh --hero "/Users/.../my-cocktail.png"
```

## Pré-requisitos

- `ANTHROPIC_API_KEY` no env (ou em `~/.zshrc`)
- `GEMINI_API_KEY` no env (necessária para outpaint F02/F07 e isolate F06/F09/F10)
- Python deps: `anthropic`, `requests`, `playwright`, `Pillow`. Optional: `rembg`.
- Playwright chromium: `python3 -m playwright install chromium`

Se `rembg` não estiver instalado, F06/F09/F10 fazem fallback para Gemini bg-removal (custa mais).

## O que é gerado

Cada run cria uma pasta em `orchestrator/outputs/<timestamp>_<product>/` com:
- `decision_iter0.json` — decisão completa do Decisor
- `poster_iter0.png` — render Playwright
- `critique_iter0.json` — score + violations + suggested fixes
- `run_log.json` — timeline e summary

A battery agrega tudo em `tests/battery_runs/<timestamp>/`:
- `<family>_<mode>.png` — copy do final PNG (acesso rápido)
- `<family>_<mode>.log` — stdout completo do orchestrator
- `<family>_<mode>_run` — symlink para o run dir
- `manifest.json` — array com metadata de cada run
- `index.html` — **grid visual review (open this!)**

## Como ler o `index.html`

Abre no browser: `open tests/battery_runs/<timestamp>/index.html`.

Vês uma grelha agrupada por família. Cada card mostra:
- Thumbnail do poster gerado (4:5 aspect)
- Mode (standard / variation / experimental)
- Score (0-100)
- Badge: PUBLISHABLE (verde) / REVIEW (amarelo) / FAIL (vermelho)
- Link para o log completo

Identifica visualmente:
- **Famílias que falham consistentemente** (vermelho em todos os modes) → template tem bug arquitectural
- **Famílias que funcionam mal em experimental** (review/fail só em experimental) → Decisor está a empurrar params demasiado para os limites
- **Famílias que produzem o mesmo output em standard vs experimental** → mode pipeline não está a impactar design suficientemente

## Custo estimado

Por run (1 iteração, sem auto-fix loop):
- Decisor (Claude Sonnet) — ~$0.025
- Critique (Claude Sonnet com vision) — ~$0.030
- Outpaint Gemini (apenas em F02/F07 quando aspect mismatch) — ~$0.040
- Isolate rembg (F06/F09/F10) — gratis local, fallback Gemini ~$0.040

Battery completa (24 runs): **~$1.50–$2.00**.
Battery quick (8 runs): **~$0.50–$0.70**.

## Adicionar nova família à battery

Em `battery.sh` linha 26, edita a array:

```bash
FAMILIES=("F01" "F02" "F03" "F06" "F07" "F08" "F09" "F10")
```

Adiciona a nova family e re-corre.

## Comparar batteries (regression check)

```bash
# Antes de uma mudança:
./tests/battery.sh --quick
# (anota timestamp_old)

# Depois da mudança:
./tests/battery.sh --quick
# (anota timestamp_new)

# Compara scores manualmente abrindo os dois index.html lado a lado
```

Para automatizar regression: futuramente fazer um script que diff-e os manifest.json e flag-e quedas de score >10 pontos.
