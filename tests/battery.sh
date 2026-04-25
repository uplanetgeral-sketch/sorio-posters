#!/bin/bash
# Bateria de testes para o pipeline Só Rio.
#
# Itera (product × family × mode) e produz outputs em tests/battery_runs/<timestamp>/.
# Gera um index.html grid review no fim para inspecção visual.
#
# Uso:
#   cd sorio-posters
#   ./tests/battery.sh                    # default: cloud_dance × 8 famílias × 3 modes = 24 runs
#   ./tests/battery.sh --quick            # apenas 1 mode (variation), 8 famílias = 8 runs
#   ./tests/battery.sh --product XYZ      # outro product (precisa estar em catalogue/)
#   ./tests/battery.sh --format 1080x1920 # default 1080x1350
#   ./tests/battery.sh --hero PATH        # override hero (image-first flow)
#
# Requisitos:
#   - ANTHROPIC_API_KEY definida no env
#   - GEMINI_API_KEY definida (para outpaint/isolate)
#   - Python deps: anthropic, requests, playwright, Pillow, rembg (optional)
#   - Playwright chromium installed: python3 -m playwright install chromium

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Defaults
PRODUCT="cloud_dance"
FORMAT="1080x1350"
HERO=""
QUICK=0

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --product) PRODUCT="$2"; shift 2 ;;
        --format) FORMAT="$2"; shift 2 ;;
        --hero) HERO="$2"; shift 2 ;;
        --quick) QUICK=1; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Family list — F05a/b skipped (deprecated until rewritten)
FAMILIES=("F01" "F02" "F03" "F06" "F07" "F08" "F09" "F10")

# Mode list
if [[ $QUICK -eq 1 ]]; then
    MODES=("variation")
else
    MODES=("standard" "variation" "experimental")
fi

# Output dir
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BATTERY_DIR="$REPO_ROOT/tests/battery_runs/$TIMESTAMP"
mkdir -p "$BATTERY_DIR"

echo "=========================================="
echo "Só Rio · Test Battery"
echo "=========================================="
echo "Product:    $PRODUCT"
echo "Format:     $FORMAT"
echo "Families:   ${FAMILIES[*]}"
echo "Modes:      ${MODES[*]}"
[[ -n "$HERO" ]] && echo "Hero:       $HERO"
echo "Output dir: $BATTERY_DIR"
echo "Total runs: $((${#FAMILIES[@]} * ${#MODES[@]}))"
echo "=========================================="
echo ""

# Auto-load API keys from common locations if not in env
if [[ -z "$ANTHROPIC_API_KEY" ]] && [[ -f "$HOME/.zshrc" ]]; then
    eval "$(grep -E '^export (ANTHROPIC_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY)=' "$HOME/.zshrc" || true)"
fi

if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "ERRO: ANTHROPIC_API_KEY não definida"
    exit 1
fi

# Manifest do battery — JSON com cada run
MANIFEST="$BATTERY_DIR/manifest.json"
echo "[" > "$MANIFEST"

run_count=0
total=$((${#FAMILIES[@]} * ${#MODES[@]}))

for family in "${FAMILIES[@]}"; do
    for mode in "${MODES[@]}"; do
        run_count=$((run_count + 1))
        echo ""
        echo "──────────────────────────────────────────"
        echo "[$run_count/$total] $family · $mode · $FORMAT"
        echo "──────────────────────────────────────────"

        run_label="${family}_${mode}"
        run_dir_base="$REPO_ROOT/orchestrator/outputs"

        # Build orchestrator command
        cmd="python3 orchestrator/main.py $PRODUCT --mode $mode --family $family --format $FORMAT --max-iter 1"
        [[ -n "$HERO" ]] && cmd="$cmd --hero \"$HERO\""

        # Run, capturing stdout
        log_file="$BATTERY_DIR/${run_label}.log"
        if eval "$cmd" 2>&1 | tee "$log_file"; then
            # Find the actual run dir from the log — usar sed em vez de grep -oE
            # porque \S+ pára em espaços (paths com "CREATIVE STUDIO" partem-se).
            actual_run_dir=$(grep "^Run dir:" "$log_file" | tail -1 | sed 's/^Run dir:[[:space:]]*//')
            if [[ -n "$actual_run_dir" ]] && [[ -d "$actual_run_dir" ]]; then
                # Symlink it under battery_dir
                ln -sf "$actual_run_dir" "$BATTERY_DIR/${run_label}_run"
                # Find final PNG / score / publishable (mesma lógica sed)
                final_png=$(grep "^Final PNG:" "$log_file" | tail -1 | sed 's/^Final PNG:[[:space:]]*//')
                final_score=$(grep "^Final score:" "$log_file" | tail -1 | sed 's/^Final score:[[:space:]]*//' | sed 's|/100||')
                final_publishable=$(grep "^Final publishable:" "$log_file" | tail -1 | sed 's/^Final publishable:[[:space:]]*//')

                # Copy final PNG to battery_dir for easy access
                if [[ -n "$final_png" ]] && [[ -f "$actual_run_dir/$final_png" ]]; then
                    cp "$actual_run_dir/$final_png" "$BATTERY_DIR/${run_label}.png"
                fi

                # Append to manifest (with comma if not first)
                [[ $run_count -gt 1 ]] && echo "," >> "$MANIFEST"
                cat >> "$MANIFEST" <<EOF
  {
    "label": "$run_label",
    "family": "$family",
    "mode": "$mode",
    "format": "$FORMAT",
    "product": "$PRODUCT",
    "score": "$final_score",
    "publishable": "$final_publishable",
    "png": "${run_label}.png",
    "log": "${run_label}.log",
    "run_dir": "$actual_run_dir"
  }
EOF
            fi
            echo "✓ OK · score $final_score"
        else
            echo "✗ FAIL"
            [[ $run_count -gt 1 ]] && echo "," >> "$MANIFEST"
            cat >> "$MANIFEST" <<EOF
  {
    "label": "$run_label",
    "family": "$family",
    "mode": "$mode",
    "status": "failed",
    "log": "${run_label}.log"
  }
EOF
        fi
    done
done

echo "" >> "$MANIFEST"
echo "]" >> "$MANIFEST"

# Generate index.html
echo ""
echo "Generating index.html..."
python3 "$REPO_ROOT/tests/build_index.py" "$BATTERY_DIR" "$MANIFEST"

echo ""
echo "=========================================="
echo "BATTERY COMPLETO"
echo "=========================================="
echo "Output: $BATTERY_DIR"
echo "Index:  $BATTERY_DIR/index.html"
echo ""
echo "Para ver: open '$BATTERY_DIR/index.html'"
