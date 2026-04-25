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

# Outpaint module (opcional — só usado quando GEMINI_API_KEY definida)
try:
    from outpaint import maybe_outpaint
    HAS_OUTPAINT = True
except ImportError:
    HAS_OUTPAINT = False

# Isolate module (rembg + Gemini bg removal)
try:
    from isolate import maybe_isolate, ISOLATE_FAMILIES
    HAS_ISOLATE = True
except ImportError:
    HAS_ISOLATE = False
    ISOLATE_FAMILIES = set()


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCH_DIR = Path(__file__).resolve().parent
# Static host serving HTML templates + design refs + catalogue JSON.
# Migrated from Netlify (Apr 2026) → Cloudflare Pages (unlimited bandwidth + 500 builds free).
TEMPLATES_BASE = "https://sorio-posters.pages.dev"
NETLIFY_BASE = TEMPLATES_BASE  # alias para retrocompatibilidade — referências antigas continuam a funcionar

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


def _is_local_path(s):
    """True se s parece um caminho local (não URL com protocolo)."""
    if not s:
        return False
    if s.startswith(("http://", "https://", "data:", "file://")):
        return False
    return s.startswith("/") or s.startswith("./") or s.startswith("../") or os.path.exists(s)


def _local_file_to_data_url(path):
    """Lê ficheiro local e devolve data URL base64. Se for muito grande, faz downsize via sips."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Hero local não encontrado: {path}")

    # Se > 1.5MB, faz downsize para ~1500px de largura (mantém qualidade hero, evita data URL gigante)
    MAX_BYTES = 1_500_000
    if p.stat().st_size > MAX_BYTES:
        smaller = p.with_name(p.stem + ".compressed.png")
        try:
            subprocess.run(
                ["sips", "-Z", "1500", str(p), "--out", str(smaller)],
                capture_output=True, check=True
            )
            p = smaller
            log("HERO", f"Hero comprimido: {p.stat().st_size/1024:.0f}KB")
        except Exception as e:
            log("HERO", f"WARN: sips falhou ({e}) · usando original")

    suffix = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/png")
    with open(p, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def render_url(family, url_params, hero_url, output_path, format_wh="1080x1350"):
    """Playwright headless screenshot do template HTML param-driven.
    format_wh: 'WxH' string. Determina viewport + URL param `format=...`.

    Hero injection:
    - URL pública (http/https) → passa via URL param `hero=...`
    - Caminho local absoluto → converte para data URL base64 e injecta via page.evaluate()
      (evita mixed-content blocking quando template está em HTTPS e hero em file://)
    - Path relativo (catalogue/...) → passa como URL param (resolvido relativamente ao template)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("RENDER", "ERRO: playwright não instalado. `pip3 install playwright && playwright install chromium`")
        sys.exit(1)

    try:
        w, h = format_wh.split("x")
        canvas_w, canvas_h = int(w), int(h)
    except Exception:
        canvas_w, canvas_h = 1080, 1350

    # --- Hero handling ---
    full_params = dict(url_params)
    hero_inject_data_url = None  # se preenchido, injecta após page load

    if hero_url and hero_url != "<HERO_URL>":
        if _is_local_path(hero_url):
            # Local file → convert to data URL, inject via JS post-load (não cabe / é frágil em URL param)
            try:
                hero_inject_data_url = _local_file_to_data_url(hero_url)
                log("HERO", f"Local → data URL ({len(hero_inject_data_url)//1024}KB base64)")
            except Exception as e:
                log("HERO", f"ERRO converter local→data URL: {e}")
                # fallback: ainda passa por URL param (vai falhar mas pelo menos render continua)
                full_params["hero"] = hero_url
        else:
            # URL pública ou path relativo → passa por URL param normalmente
            full_params["hero"] = hero_url

    # Remove placeholder
    if full_params.get("hero") == "<HERO_URL>":
        full_params.pop("hero", None)
    # Format param para template responder ao tamanho
    full_params["format"] = format_wh

    template_url = f"{NETLIFY_BASE}/{family.lower()}.html?{urlencode(full_params)}"
    log("RENDER", f"URL: {template_url[:120]}{'...' if len(template_url) > 120 else ''}")
    log("RENDER", f"Canvas: {canvas_w}x{canvas_h}")
    if hero_inject_data_url:
        log("RENDER", "Hero será injectado via JS após page load (evita mixed-content)")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": canvas_w, "height": canvas_h}, device_scale_factor=2)
        page.goto(template_url, wait_until="networkidle")

        # Inject local hero as data URL (post-load) — bypassa CORS/mixed-content
        if hero_inject_data_url:
            page.evaluate(
                """(dataUrl) => {
                    const heroEl = document.getElementById('hero');
                    if (heroEl) {
                        heroEl.style.backgroundImage = 'url("' + dataUrl + '")';
                    }
                }""",
                hero_inject_data_url,
            )
            # Esperar o decode da imagem antes do screenshot
            page.wait_for_timeout(800)

        page.wait_for_timeout(2500)
        page.screenshot(path=str(output_path), omit_background=False, clip={
            "x": 0, "y": 0, "width": canvas_w, "height": canvas_h
        })
        browser.close()
    return template_url


def resize_if_needed(image_path, max_bytes=4_000_000):
    """Prepare image for Critique API (5MB limit). Always produce a JPEG q90 ≤1080 longest edge.

    A versão anterior só fazia resize condicional e usava sips -Z 1350 que mantinha PNG.
    Em 9:16 com device_scale_factor=2 a renderização é 2160×3840 que mesmo após resize
    para 1350 longest edge ainda dava ~5.3MB em PNG. Solução: forçar JPEG q90 ≤1080 →
    resultado garantido <500KB."""
    size = image_path.stat().st_size

    # Sempre produzir versão segura (mesmo que <max_bytes pode ser PNG enorme)
    safe = image_path.with_suffix(".critique.jpg")
    try:
        result = subprocess.run(
            ["sips", "-Z", "1080",
             "-s", "format", "jpeg",
             "-s", "formatOptions", "85",
             str(image_path), "--out", str(safe)],
            capture_output=True, check=True, text=True
        )
        new_size = safe.stat().st_size
        log("RESIZE", f"PNG {size/1024/1024:.1f}MB → JPEG {new_size/1024:.0f}KB (1080 longest, q85)")
        if new_size > max_bytes:
            # Plano B — segunda passagem mais agressiva
            log("RESIZE", f"Ainda >{max_bytes/1024/1024:.1f}MB · segunda passagem q70 ≤900px")
            subprocess.run(
                ["sips", "-Z", "900",
                 "-s", "format", "jpeg",
                 "-s", "formatOptions", "70",
                 str(image_path), "--out", str(safe)],
                capture_output=True, check=True
            )
        return safe
    except subprocess.CalledProcessError as e:
        log("RESIZE", f"WARN sips falhou ({e.stderr if hasattr(e, 'stderr') else e}) · usar original")
        return image_path


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
    parser.add_argument("--family", default=None,
                        choices=["F01", "F02", "F03", "F05a", "F05b", "F06", "F07", "F08", "F09", "F10"])
    parser.add_argument("--hero", default=None,
                        help="Override hero — caminho local ou URL pública. "
                             "Quando passado, ignora product.approved_heroes[0].")
    parser.add_argument("--product-json", default=None,
                        help="Caminho para product.json ad-hoc (ignora catalogue/produtos/<id>/product.json). "
                             "Útil para produtos que ainda não estão no catálogo.")
    parser.add_argument("--format", default="1080x1350",
                        help="Output format WxH px. Defaults: 1080x1080 (1:1), 1080x1350 (4:5), 1080x1920 (9:16)")
    parser.add_argument("--no-outpaint", action="store_true",
                        help="Desactiva outpaint Gemini condicional (mesmo se GEMINI_API_KEY estiver definida).")
    parser.add_argument("--no-isolate", action="store_true",
                        help="Desactiva subject isolation (rembg + Gemini fallback) mesmo em famílias F06/F09/F10.")
    parser.add_argument("--force-isolate", action="store_true",
                        help="Força subject isolation mesmo em famílias que não exigem.")
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
    if args.product_json:
        # Ad-hoc product (não está no catalogue Netlify, vem inline da Boldy)
        try:
            with open(args.product_json, "r", encoding="utf-8") as f:
                product = json.load(f)
            log("LOAD", f"Product (ad-hoc): {product.get('name', args.product_id)}")
        except Exception as e:
            log("LOAD", f"ERRO ao ler product.json ad-hoc: {e}")
            sys.exit(1)
    else:
        try:
            product = fetch_json(f"{NETLIFY_BASE}/catalogue/produtos/{args.product_id}/product.json")
        except Exception:
            log("LOAD", f"ERRO: produto '{args.product_id}' não está no catálogo Netlify ainda")
            sys.exit(1)
    principles = fetch_json(f"{NETLIFY_BASE}/design/design_principles_sorio.json")
    creative_modes = fetch_json(f"{NETLIFY_BASE}/design/creative_modes.json")
    refs_index = fetch_json(f"{NETLIFY_BASE}/design/design_references/_index.json")

    # Hero URL resolution priority:
    # 1) --hero CLI override (from Boldy drop-image flow ou manual)
    # 2) product.approved_heroes[0] do catalogue
    # 3) None (Designer/Gemini gera novo — fora do scope deste orchestrator v1)
    hero_url = None
    if args.hero:
        hero_url = args.hero
        log("HERO", f"Override: {hero_url}")
    elif product.get("approved_heroes"):
        hero_path = product["approved_heroes"][0]
        hero_url = f"catalogue/produtos/{args.product_id}/{hero_path}"
        log("HERO", f"Catalogue approved: {hero_url}")

    # === Outpaint condicional ===
    # Aplicar APENAS se: hero é local + family aceita outpaint (não F03/F05a/F05b) +
    # format aspect mismatch significativo + GEMINI_API_KEY + flag não desactivada
    # NOTA: Decisor escolhe family ANTES desta secção, mas a chamada ao Decisor está mais abaixo.
    # Por isso fazemos outpaint LAZILY — só após o Decisor decidir.
    # Em alternativa simples: deixar maybe_outpaint() receber family=None aqui e a lib decide.
    # Mas como queremos saber a family ANTES de outpaint para poupar Gemini calls em F03/F05*,
    # vamos mover esta secção para DEPOIS do Decisor (no início do iter loop).
    # Por agora, NÃO outpaint aqui — adiamos para depois da decisão.
    pre_outpaint_hero = hero_url

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

    # === Hero processing AGORA que sabemos a family ===
    # Outpaint (F01/F02/F07) ou Isolate (F06/F09/F10) — exclusivos.
    # Outras families (F03/F05a/F05b/F08) skip ambos (cover-crop ou clip-path nativo).
    chosen_family = decision.get('family')
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    hero_url = pre_outpaint_hero  # default

    if pre_outpaint_hero and os.path.exists(pre_outpaint_hero):
        # Decide qual processing aplicar
        do_isolate = (
            HAS_ISOLATE and not args.no_isolate and
            (args.force_isolate or chosen_family in ISOLATE_FAMILIES)
        )
        do_outpaint = (
            not do_isolate and  # mutually exclusive
            HAS_OUTPAINT and not args.no_outpaint
        )

        if do_isolate:
            log("HERO", f"Family {chosen_family} → ISOLATE (subject cutout)")
            try:
                new_hero = maybe_isolate(
                    source_path=Path(pre_outpaint_hero),
                    out_dir=run_dir,
                    gemini_key=gemini_key,
                    family=chosen_family,
                    force=args.force_isolate,
                )
                if str(new_hero) != pre_outpaint_hero:
                    hero_url = str(new_hero)
                    log("HERO", f"Isolated → {hero_url}")
            except Exception as e:
                log("HERO", f"WARN isolation falhou · {e}")

        elif do_outpaint and gemini_key:
            log("HERO", f"Family {chosen_family} → OUTPAINT (extend para canvas)")
            hint = f"{product.get('name', args.product_id)} · Só Rio · Valada do Ribatejo · river beach lounge food/drink photography"
            try:
                new_hero = maybe_outpaint(
                    source_path=Path(pre_outpaint_hero),
                    target_format=args.format,
                    out_dir=run_dir,
                    api_key=gemini_key,
                    hint=hint,
                    family=chosen_family,
                )
                if str(new_hero) != pre_outpaint_hero:
                    hero_url = str(new_hero)
                    log("HERO", f"Outpainted → {hero_url}")
            except Exception as e:
                log("HERO", f"WARN outpaint falhou — usar source · {e}")
        else:
            log("HERO", f"Family {chosen_family} → cover-crop nativo (sem processing)")

    while True:
        # Render
        log(f"ITER {iter_n}", "RENDER")
        png_path = run_dir / f"poster_iter{iter_n}.png"
        url = render_url(decision["family"], decision["url_params"], hero_url, png_path, format_wh=args.format)

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
