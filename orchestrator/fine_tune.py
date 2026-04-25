#!/usr/bin/env python3
"""
orchestrator/fine_tune.py · Re-render existing decision with diff applied.

Two modes:
  1. NL chat — pass --instruction "PT-PT instruction", agent translates to params_diff
  2. Direct — pass --params-diff JSON inline, no LLM call

In both cases:
  - Loads existing run_dir/decision_iter{N}.json (latest)
  - Applies params_diff to url_params
  - Saves new decision_iter{N+1}.json
  - Re-renders via Playwright (no outpaint, no isolate — preserves processed hero)
  - Optionally re-runs Critique
  - Outputs new poster_iter{N+1}.png

CLI:
    python3 fine_tune.py <run_dir> --instruction "TEXT"
    python3 fine_tune.py <run_dir> --params-diff '{"display_size": 200}'
    python3 fine_tune.py <run_dir> --instruction "..." --skip-critique  # save Anthropic call
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

try:
    from anthropic import Anthropic
except ImportError:
    print("ERRO: anthropic not installed. pip3 install anthropic")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_BASE = "https://sorio-posters.pages.dev"


def log(stage, msg):
    print(f"[{stage}] {msg}", flush=True)


def find_latest_decision(run_dir):
    """Encontra o decision_iter{N}.json com o N mais alto."""
    files = sorted(run_dir.glob("decision_iter*.json"))
    if not files:
        raise FileNotFoundError(f"No decision_iter*.json in {run_dir}")
    return files[-1]


def find_latest_iter_n(run_dir):
    """Encontra o N do iter mais recente."""
    files = sorted(run_dir.glob("decision_iter*.json"))
    if not files:
        return -1
    last = files[-1].stem  # "decision_iter3"
    return int(last.replace("decision_iter", ""))


def deep_merge_params(base_params, diff):
    """Aplica diff a base_params. Devolve novo dict, não modifica originais."""
    new = dict(base_params)
    for k, v in diff.items():
        new[k] = v
    return new


def call_fine_tune_agent(client, current_decision, user_instruction):
    """LLM call para traduzir NL → params_diff."""
    system = (REPO_ROOT / "fine_tune" / "system_prompt.md").read_text(encoding="utf-8")
    payload = {
        "current_decision": current_decision,
        "user_instruction": user_instruction,
    }
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
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


def render_poster(family, url_params, hero_url, output_path, format_wh):
    """Re-render via Playwright. Mesma lógica do main.py mas sem outpaint/isolate."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("RENDER", "ERRO: playwright not installed")
        sys.exit(1)

    try:
        w, h = format_wh.split("x")
        canvas_w, canvas_h = int(w), int(h)
    except Exception:
        canvas_w, canvas_h = 1080, 1350

    full_params = dict(url_params)
    hero_inject_data_url = None

    if hero_url and hero_url != "<HERO_URL>":
        if os.path.exists(hero_url):
            # Local file → data URL
            from PIL import Image
            import io
            p = Path(hero_url)
            suffix = p.suffix.lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/png")
            with open(p, "rb") as f:
                b64 = base64.standard_b64encode(f.read()).decode("ascii")
            hero_inject_data_url = f"data:{mime};base64,{b64}"
        else:
            full_params["hero"] = hero_url

    if full_params.get("hero") == "<HERO_URL>":
        full_params.pop("hero", None)
    full_params["format"] = format_wh

    template_url = f"{TEMPLATES_BASE}/{family.lower()}.html?{urlencode(full_params)}"
    log("RENDER", f"URL: {template_url[:120]}{'...' if len(template_url) > 120 else ''}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": canvas_w, "height": canvas_h}, device_scale_factor=2)
        page.goto(template_url, wait_until="networkidle")
        if hero_inject_data_url:
            page.evaluate(
                """(dataUrl) => {
                    const heroEl = document.getElementById('hero');
                    if (heroEl) heroEl.style.backgroundImage = 'url("' + dataUrl + '")';
                }""",
                hero_inject_data_url,
            )
            page.wait_for_timeout(800)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(output_path), omit_background=False, clip={
            "x": 0, "y": 0, "width": canvas_w, "height": canvas_h
        })
        browser.close()
    return template_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Existing orchestrator run_dir to fine-tune")
    parser.add_argument("--instruction", default=None,
                        help="PT-PT NL instruction (chat mode). Triggers Fine-Tune Agent LLM call.")
    parser.add_argument("--params-diff", default=None,
                        help='JSON inline params diff (direct mode, no LLM). Ex: \'{"display_size": 200}\'')
    parser.add_argument("--format", default=None,
                        help="Override format WxH. Default: read from existing decision URL params.")
    parser.add_argument("--skip-critique", action="store_true",
                        help="Skip Critique re-run (save Anthropic call). Default: re-critique.")
    parser.add_argument("--hero", default=None,
                        help="Override hero path (default: read from previous run/decision).")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        log("FT", f"ERRO: run_dir não existe: {run_dir}")
        sys.exit(1)

    if not args.instruction and not args.params_diff:
        log("FT", "ERRO: passa --instruction OU --params-diff")
        sys.exit(1)

    # Load latest decision
    iter_n = find_latest_iter_n(run_dir)
    if iter_n < 0:
        log("FT", f"ERRO: sem decision_iter*.json em {run_dir}")
        sys.exit(1)
    decision_path = run_dir / f"decision_iter{iter_n}.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    log("FT", f"Loaded {decision_path.name} (family={decision.get('family')})")

    # Determine params_diff
    if args.params_diff:
        params_diff = json.loads(args.params_diff)
        rationale = "Direct param edit (no LLM)"
        log("FT", f"Direct diff: {params_diff}")
    else:
        # Chat mode — call Fine-Tune Agent
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("FT", "ERRO: ANTHROPIC_API_KEY required for --instruction mode")
            sys.exit(1)
        client = Anthropic()
        log("FT", f"Fine-Tune Agent: {args.instruction}")
        try:
            agent_result = call_fine_tune_agent(client, decision, args.instruction)
        except Exception as e:
            log("FT", f"Agent call failed: {e}")
            sys.exit(1)
        if "error" in agent_result:
            log("FT", f"Agent error: {agent_result['error']} · {agent_result.get('reason', '')}")
            print(json.dumps(agent_result, ensure_ascii=False))
            sys.exit(2)
        params_diff = agent_result.get("params_diff", {})
        rationale = agent_result.get("rationale", "")
        log("FT", f"Agent params_diff: {params_diff}")
        log("FT", f"Rationale: {rationale}")

    if not params_diff:
        log("FT", "Sem changes a aplicar — abort")
        sys.exit(0)

    # Apply diff to decision
    new_decision = json.loads(json.dumps(decision))  # deep copy
    new_decision["url_params"] = deep_merge_params(decision["url_params"], params_diff)
    new_decision["fine_tune_history"] = decision.get("fine_tune_history", []) + [{
        "iter_from": iter_n,
        "instruction": args.instruction,
        "params_diff": params_diff,
        "rationale": rationale,
    }]

    # Save new decision
    new_iter = iter_n + 1
    new_decision_path = run_dir / f"decision_iter{new_iter}.json"
    new_decision_path.write_text(json.dumps(new_decision, ensure_ascii=False, indent=2), encoding="utf-8")
    log("FT", f"Saved {new_decision_path.name}")

    # Hero — find from previous run
    # Priority:
    #   1. --hero CLI override
    #   2. decision._hero_url_used (gravado por main.py post-outpaint/isolate)
    #   3. Last iteration's hero_url_used em run_log.json
    #   4. Processed file no run_dir (*.outpainted.png / *.isolated.png)
    #   5. url_params.hero (se não for placeholder)
    hero_url = args.hero
    if not hero_url:
        # 2. Decision-level hint
        prev_hero = decision.get("_hero_url_used")
        if prev_hero:
            hero_url = prev_hero
            log("FT", f"Hero from decision._hero_url_used: {hero_url}")
    if not hero_url:
        # 3. Run log timeline
        run_log_path = run_dir / "run_log.json"
        if run_log_path.exists():
            try:
                rl = json.loads(run_log_path.read_text(encoding="utf-8"))
                iterations = rl.get("iterations", [])
                for it in reversed(iterations):
                    h = it.get("hero_url_used")
                    if h:
                        hero_url = h
                        log("FT", f"Hero from run_log iter {it.get('iter')}: {hero_url}")
                        break
            except Exception as e:
                log("FT", f"WARN couldn't read run_log for hero: {e}")
    if not hero_url:
        # 4. Processed file already in run_dir
        for candidate in ["*.outpainted.png", "*.isolated.png"]:
            matches = list(run_dir.glob(candidate))
            if matches:
                hero_url = str(matches[0])
                log("FT", f"Reusing processed hero: {hero_url}")
                break
    if not hero_url:
        # 5. Last resort: catalogue path em url_params (se não placeholder)
        url_hero = new_decision["url_params"].get("hero")
        if url_hero and url_hero != "<HERO_URL>":
            hero_url = url_hero
            log("FT", f"Hero from url_params: {hero_url}")
    if not hero_url:
        log("FT", "ERRO: não consigo recuperar hero do run anterior. Abort para evitar render com fallback errado.")
        sys.exit(3)

    # Persist for next iteration
    new_decision["_hero_url_used"] = hero_url

    # Format — preserve from previous run.
    # Priority: --format CLI override → decision.url_params.format → run_log timeline URL → default
    format_wh = args.format
    if not format_wh:
        format_wh = new_decision["url_params"].get("format")
    if not format_wh:
        # Fallback: parse from the last rendered URL in run_log.json
        run_log_path = run_dir / "run_log.json"
        if run_log_path.exists():
            try:
                rl = json.loads(run_log_path.read_text(encoding="utf-8"))
                iterations = rl.get("iterations", [])
                if iterations:
                    last_url = iterations[-1].get("url", "")
                    import re
                    m = re.search(r'format=(\d+x\d+)', last_url)
                    if m:
                        format_wh = m.group(1)
                        log("FT", f"Format recovered from run_log: {format_wh}")
            except Exception as e:
                log("FT", f"WARN couldn't parse run_log for format: {e}")
    if not format_wh:
        format_wh = "1080x1350"
        log("FT", "WARN format not found anywhere, defaulting to 1080x1350")
    # Persist format in url_params for future iterations
    new_decision["url_params"]["format"] = format_wh
    new_decision_path.write_text(json.dumps(new_decision, ensure_ascii=False, indent=2), encoding="utf-8")

    # Re-render
    output_png = run_dir / f"poster_iter{new_iter}.png"
    render_poster(
        family=new_decision["family"],
        url_params=new_decision["url_params"],
        hero_url=hero_url,
        output_path=output_png,
        format_wh=format_wh,
    )
    log("FT", f"Rendered {output_png.name}")

    # Optionally re-critique
    final_score = None
    if not args.skip_critique:
        try:
            sys.path.insert(0, str(REPO_ROOT / "orchestrator"))
            from main import call_critique, resize_if_needed
            import requests

            # Need principles + refs
            principles = requests.get(f"{TEMPLATES_BASE}/design/design_principles_sorio.json", timeout=10).json()
            refs_index = requests.get(f"{TEMPLATES_BASE}/design/design_references/_index.json", timeout=10).json()

            client = Anthropic()
            critique_input = resize_if_needed(output_png)
            log("FT", "Critique...")
            critique = call_critique(client, critique_input, new_decision, principles, refs_index)
            crit_path = run_dir / f"critique_iter{new_iter}.json"
            crit_path.write_text(json.dumps(critique, ensure_ascii=False, indent=2), encoding="utf-8")
            final_score = critique.get("score", 0)
            log("FT", f"Score {final_score}/100 · publishable={critique.get('publishable')}")
        except Exception as e:
            log("FT", f"Critique skipped (error): {e}")

    # Output summary JSON for Boldy IPC consumer
    summary = {
        "run_dir": str(run_dir),
        "new_iter": new_iter,
        "new_decision": str(new_decision_path),
        "new_png": str(output_png),
        "params_diff_applied": params_diff,
        "rationale": rationale,
        "score": final_score,
    }
    print()
    print("=" * 60)
    print("FINE-TUNE COMPLETO")
    print("=" * 60)
    print(f"New iter:     {new_iter}")
    print(f"New PNG:      {output_png}")
    if final_score is not None:
        print(f"Score:        {final_score}/100")
    print()
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
