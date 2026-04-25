#!/usr/bin/env python3
"""
orchestrator/main.py · End-to-end pipeline single-command.

Uso:
    python3 orchestrator/main.py PRODUCT_ID [opts]

Opções:
    --mode standard|variation|experimental   (default: standard)
    --freedom FLOAT                          (override creative_freedom; default per mode)
    --max-iter N                             (default: 2)
    --no-auto-fix                            (disable auto-fix loop)
    --family F01|F02|F03|F05a|F05b           (override Decisor family choice)

Requer:
    pip3 install anthropic requests jsonschema playwright
    playwright install chromium
    export ANTHROPIC_API_KEY=sk-ant-...
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

try:
    from anthropic import Anthropic
    import requests
except ImportError as e:
    print(f"Erro: faltam libs. {e}\nInstala: pip3 install anthropic requests jsonschema playwright")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCH_DIR = Path(__file__).resolve().parent
NETLIFY_BASE = "https://sorio-posters.netlify.app"

MODE_PRESETS = {
    "standard": {"freedom": 0.15, "threshold": 75},
    "variation": {"freedom": 0.45, "threshold": 70},
    "experimental": {"freedom": 0.80, "threshold": 60},
}


def fetch_json(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def log(stage, msg):
    print(f"[{stage}] {msg}", flush=True)


def call_decisor(client, payload):
    system = (REPO_ROOT / "decisor" / "system_prompt.md").read_text(encoding="utf-8")
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


def call_critique(client, image_path, decision, principles, refs_index):
    system = (REPO_ROOT / "critique" / "system_prompt.md").read_text(encoding="utf-8")
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(suffix, "image/png")

    text_payload = {"decision": decision, "principles": principles, "refs_index": refs_index}
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": json.dumps(text_payload, ensure_ascii=False)},
            ],
        }],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


def render_url(family, url_params, hero_url, output_path):
    """Playwright headless screenshot do template HTML param-driven."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("RENDER", "ERRO: playwright não instalado. `pip3 install playwright && playwright install chromium`")
        sys.exit(1)

    # Inject hero URL
    full_params = dict(url_params)
    if hero_url:
        full_params["hero"] = hero_url
    # Remove placeholder
    if full_params.get("hero") == "<HERO_URL>":
        full_params.pop("hero", None)

    template_url = f"{NETLIFY_BASE}/{family.lower()}.html?{urlencode(full_params)}"
    log("RENDER", f"URL: {template_url[:120]}{'...' if len(template_url) > 120 else ''}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
        page.goto(template_url, wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(output_path), omit_background=False)
        browser.close()
    return template_url


def resize_if_needed(image_path, max_bytes=4_500_000):
    """Resize image to fit under API 5MB limit (with margin)."""
    size = image_path.stat().st_size
    if size <= max_bytes:
        return image_path

    log("RESIZE", f"PNG {size/1024/1024:.1f}MB > 4.5MB · a fazer downsize")
    smaller = image_path.with_suffix(".small.png")
    subprocess.run(["sips", "-Z", "1350", str(image_path), "--out", str(smaller)], capture_output=True, check=True)
    return smaller


def apply_url_fixes(decision, suggested_fixes):
    """Aplica suggested_fixes que sejam url_param_change ao decision (não regen Designer)."""
    new_decision = json.loads(json.dumps(decision))  # deep copy
    applied = []
    for fix in suggested_fixes:
        change = fix.get("url_param_change")
        if not change:
            continue
        for key, value in change.items():
            new_decision["url_params"][key] = value
            applied.append({"principle": fix.get("principle_id"), "param": key, "value": value})
    return new_decision, applied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id")
    parser.add_argument("--mode", default="standard", choices=["standard", "variation", "experimental"])
    parser.add_argument("--freedom", type=float, default=None)
    parser.add_argument("--max-iter", type=int, default=2)
    parser.add_argument("--no-auto-fix", action="store_true")
    parser.add_argument("--family", default=None, choices=["F01", "F02", "F03", "F05a", "F05b"])
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definido")
        sys.exit(1)

    creative_freedom = args.freedom if args.freedom is not None else MODE_PRESETS[args.mode]["freedom"]
    threshold = MODE_PRESETS[args.mode]["threshold"]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ORCH_DIR / "outputs" / f"{run_id}_{args.product_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    timeline = {"run_id": run_id, "product_id": args.product_id, "mode": args.mode, "freedom": creative_freedom, "iterations": []}
    t0 = time.time()

    # Load knowledge bases (cached for the run)
    log("LOAD", "Knowledge bases...")
    try:
        product = fetch_json(f"{NETLIFY_BASE}/catalogue/produtos/{args.product_id}/product.json")
    except Exception:
        log("LOAD", f"ERRO: produto '{args.product_id}' não está no catálogo Netlify ainda")
        sys.exit(1)
    principles = fetch_json(f"{NETLIFY_BASE}/design/design_principles_sorio.json")
    creative_modes = fetch_json(f"{NETLIFY_BASE}/design/creative_modes.json")
    refs_index = fetch_json(f"{NETLIFY_BASE}/design/design_references/_index.json")

    # Hero URL: pick first approved_heroes if exists
    hero_url = None
    if product.get("approved_heroes"):
        hero_path = product["approved_heroes"][0]
        hero_url = f"catalogue/produtos/{args.product_id}/{hero_path}"

    client = Anthropic()

    # ===== Iteration 0 (initial) =====
    iter_n = 0
    log(f"ITER {iter_n}", "DECISOR")
    payload = {
        "product_id": args.product_id,
        "product": product,
        "creative_freedom": creative_freedom,
        "principles": principles,
        "creative_modes": creative_modes,
        "refs_index": refs_index,
        "format": "instagram_post_1080x1350",
        "previous_decisions": [],
    }
    if args.family:
        payload["family_preference"] = args.family

    decision = call_decisor(client, payload)
    (run_dir / f"decision_iter{iter_n}.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"ITER {iter_n}", f"family={decision.get('family')} · inspired_by={decision.get('inspired_by', [])[:2]}")

    while True:
        # Render
        log(f"ITER {iter_n}", "RENDER")
        png_path = run_dir / f"poster_iter{iter_n}.png"
        url = render_url(decision["family"], decision["url_params"], hero_url, png_path)

        # Resize if needed
        critique_input = resize_if_needed(png_path)

        # Critique
        log(f"ITER {iter_n}", "CRITIQUE")
        critique = call_critique(client, critique_input, decision, principles, refs_index)
        (run_dir / f"critique_iter{iter_n}.json").write_text(json.dumps(critique, ensure_ascii=False, indent=2), encoding="utf-8")
        score = critique.get("score", 0)
        crit_violations = [v for v in critique.get("violations", []) if v.get("severity_in_mode") == "critical"]
        publishable = critique.get("publishable", False) and not crit_violations
        log(f"ITER {iter_n}", f"score={score}/100 · publishable={publishable} · critical={len(crit_violations)} · major={sum(1 for v in critique.get('violations', []) if v.get('severity_in_mode') == 'major')}")

        timeline["iterations"].append({
            "iter": iter_n,
            "url": url,
            "png": str(png_path.name),
            "score": score,
            "publishable": publishable,
            "violations": critique.get("violations", []),
            "human_review": critique.get("human_review_required", False),
        })

        # Stop conditions
        if publishable:
            log("DONE", f"Score {score} publishable · final iter {iter_n}")
            break
        if iter_n >= args.max_iter:
            log("DONE", f"Max-iter {args.max_iter} atingido · score {score} · human_review_required")
            break
        if args.no_auto_fix:
            log("DONE", "Auto-fix off · um único iter")
            break

        # Auto-fix: apply only url_param fixes
        url_fixes = [f for f in critique.get("suggested_fixes", []) if f.get("url_param_change")]
        if not url_fixes:
            log("DONE", "Sem url-fixes accionáveis (só Designer regen) · human_review_required")
            break

        log(f"FIX iter {iter_n}", f"applying {len(url_fixes)} url_param_change(s)")
        new_decision, applied = apply_url_fixes(decision, url_fixes)
        decision = new_decision
        iter_n += 1
        (run_dir / f"decision_iter{iter_n}.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed = time.time() - t0
    timeline["elapsed_seconds"] = round(elapsed, 1)
    timeline["final_score"] = timeline["iterations"][-1]["score"]
    timeline["final_publishable"] = timeline["iterations"][-1]["publishable"]
    timeline["final_png"] = timeline["iterations"][-1]["png"]
    (run_dir / "run_log.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"RUN COMPLETO · {elapsed:.1f}s")
    print("=" * 60)
    print(f"Run dir:           {run_dir}")
    print(f"Iterações:         {len(timeline['iterations'])}")
    print(f"Final score:       {timeline['final_score']}/100")
    print(f"Final publishable: {timeline['final_publishable']}")
    print(f"Final PNG:         {timeline['final_png']}")
    print()


if __name__ == "__main__":
    main()
