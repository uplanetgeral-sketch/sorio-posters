#!/usr/bin/env python3
"""
example_call.py · Vision Critique end-to-end example.

Uso:
    pip install anthropic requests jsonschema
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 example_call.py PATH/TO/poster.png PATH/TO/decision.json

Defaults:
    Se decision.json não for passado, faz scaffold mínimo do decision para teste.
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from anthropic import Anthropic
    import requests
    from jsonschema import validate, ValidationError
except ImportError:
    print("Instala: pip install anthropic requests jsonschema")
    sys.exit(1)


BASE = "https://sorio-posters.netlify.app"
CRITIQUE_DIR = Path(__file__).resolve().parent


def fetch_json(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("decision", type=Path, nargs="?", default=None)
    args = parser.parse_args()

    if not args.image.exists():
        print(f"Erro: imagem não existe: {args.image}")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definido")
        sys.exit(1)

    # 1. Load image
    with open(args.image, "rb") as f:
        image_data = f.read()
    image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
    suffix = args.image.suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/png")

    # 2. Load decision (or scaffold)
    if args.decision and args.decision.exists():
        decision = json.loads(args.decision.read_text(encoding="utf-8"))
    else:
        print("⚠ decision.json não fornecido — usando scaffold mínimo")
        decision = {
            "decision_id": "scaffold",
            "product_id": "unknown",
            "mode": "standard",
            "creative_freedom": 0.15,
            "family": "F02",
            "url_params": {},
            "designer_brief": {
                "warning_never_inside": [],
                "negative_prompt": ""
            },
            "principles_applied": [],
            "vision_critique_brief": "Generic critique — scaffold input"
        }

    # 3. Fetch knowledge bases
    print("→ A carregar principles + refs...")
    principles = fetch_json(f"{BASE}/design/design_principles_sorio.json")
    refs_index = fetch_json(f"{BASE}/design/design_references/_index.json")

    # 4. Read system prompt + schema
    system_prompt = (CRITIQUE_DIR / "system_prompt.md").read_text(encoding="utf-8")
    output_schema = json.loads((CRITIQUE_DIR / "output_schema.json").read_text(encoding="utf-8"))

    # 5. Build payload
    text_payload = {
        "decision": decision,
        "principles": principles,
        "refs_index": refs_index,
    }

    print("→ A chamar Claude Sonnet 4.5 com vision...")
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": json.dumps(text_payload, ensure_ascii=False)},
            ],
        }],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        critique = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"ERRO parse JSON: {e}")
        print(f"Raw:\n{raw_text}")
        sys.exit(1)

    try:
        validate(instance=critique, schema=output_schema)
        print("  ✓ Schema válido")
    except ValidationError as e:
        print(f"  ⚠ Schema validation: {e.message}")

    # 6. Pretty print
    print()
    print("=" * 60)
    print(f"CRITIQUE · {critique.get('product_id')} · {critique.get('family_critiqued')}")
    print("=" * 60)
    print(f"Score:        {critique.get('score')}/100  (threshold {critique.get('publishable_threshold')})")
    print(f"Publishable:  {critique.get('publishable')}")
    print(f"Human review: {critique.get('human_review_required')}")
    print(f"Closest ref:  {critique.get('closest_ref')} (sim {critique.get('closest_ref_similarity')})")
    print()
    print("Vision summary:")
    print(f"  {critique.get('vision_summary')}")
    print()
    if critique.get('violations'):
        print("Violations:")
        for v in critique['violations']:
            print(f"  [{v['severity_in_mode']:8s}] {v['principle_id']} ({v['score_impact']}): {v['evidence']}")
        print()
    if critique.get('suggested_fixes'):
        print("Suggested fixes:")
        for f in critique['suggested_fixes']:
            print(f"  • {f['issue']}")
            print(f"    → {f['fix_action']}")
            if f.get('url_param_change'):
                print(f"    URL: {f['url_param_change']}")
            if f.get('designer_negative_prompt_addition'):
                print(f"    DESIGNER NEG: {f['designer_negative_prompt_addition']}")
        print()

    # 7. Save full critique
    out_dir = CRITIQUE_DIR / "examples"
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = critique.get("product_id", "unknown")
    out_file = out_dir / f"critique_{pid}_{timestamp}.json"
    out_file.write_text(json.dumps(critique, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Critique guardada em {out_file.relative_to(CRITIQUE_DIR)}")


if __name__ == "__main__":
    main()
