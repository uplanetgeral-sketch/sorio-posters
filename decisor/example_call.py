#!/usr/bin/env python3
"""
example_call.py · End-to-end exemplo de como chamar o Decisor.

Uso:
    pip install anthropic requests jsonschema
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 example_call.py [product_id] [creative_freedom]

Defaults:
    product_id = caipirinha_maracuja
    creative_freedom = 0.15  (Daily Drop preset)
"""

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
DECISOR_DIR = Path(__file__).resolve().parent


def fetch_json(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    product_id = sys.argv[1] if len(sys.argv) > 1 else "caipirinha_maracuja"
    creative_freedom = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definido")
        sys.exit(1)

    print(f"→ Decisor call · product={product_id} · creative_freedom={creative_freedom}")

    # 1. Fetch all knowledge bases
    print("→ A carregar knowledge bases...")
    try:
        product = fetch_json(f"{BASE}/catalogue/produtos/{product_id}/product.json")
    except Exception as e:
        print(f"  product.json não encontrado em catalogue/produtos/{product_id}/")
        print(f"  Adicione o produto via catalogue/_inbox/ ou ingest_object_sheet.py")
        sys.exit(1)

    principles = fetch_json(f"{BASE}/design/design_principles_sorio.json")
    creative_modes = fetch_json(f"{BASE}/design/creative_modes.json")
    refs_index = fetch_json(f"{BASE}/design/design_references/_index.json")

    # 2. Read system prompt + output schema
    system_prompt = (DECISOR_DIR / "system_prompt.md").read_text(encoding="utf-8")
    output_schema = json.loads((DECISOR_DIR / "output_schema.json").read_text(encoding="utf-8"))

    # 3. Build user payload
    user_payload = {
        "product_id": product_id,
        "product": product,
        "creative_freedom": creative_freedom,
        "principles": principles,
        "creative_modes": creative_modes,
        "refs_index": refs_index,
        "format": "instagram_post_1080x1350",
        "previous_decisions": [],  # populate from session history in production
    }

    # 4. Call Claude
    print("→ A chamar Claude Sonnet 4.5...")
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False)
        }],
    )

    raw_text = response.content[0].text.strip()
    # Strip optional markdown fence
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"ERRO parse JSON: {e}")
        print(f"Raw text:\n{raw_text}")
        sys.exit(1)

    # 5. Validate output schema
    try:
        validate(instance=decision, schema=output_schema)
        print("  ✓ Output schema válido")
    except ValidationError as e:
        print(f"  ⚠ Schema validation failed: {e.message}")

    # 6. Build URL preview
    family = decision.get("family", "f02").lower()
    params = decision.get("url_params", {})
    from urllib.parse import urlencode
    url_params = {k: v for k, v in params.items() if v is not None and v != "<HERO_URL>"}
    poster_url = f"{BASE}/{family}.html?{urlencode(url_params)}"

    print()
    print("=" * 60)
    print("DECISÃO")
    print("=" * 60)
    print(f"Family:   {decision.get('family')}")
    print(f"Mode:     {decision.get('mode')}")
    print(f"Rationale: {decision.get('rationale')}")
    print(f"Inspired by: {', '.join(decision.get('inspired_by', []))}")
    print(f"Human review: {decision.get('human_review_required')}")
    print()
    print(f"Poster URL preview (sem hero):")
    print(f"  {poster_url}")
    print()
    print(f"Designer brief:")
    db = decision.get("designer_brief", {})
    print(f"  subject: {db.get('subject')}")
    print(f"  warning_never_inside: {db.get('warning_never_inside')}")
    print(f"  negative_prompt: {db.get('negative_prompt')}")
    print()

    # 7. Save full decision
    out_dir = DECISOR_DIR / "examples"
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"output_{product_id}_{timestamp}.json"
    out_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Decisão guardada em {out_file.relative_to(DECISOR_DIR)}")


if __name__ == "__main__":
    main()
