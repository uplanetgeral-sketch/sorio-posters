#!/usr/bin/env python3
"""
ingest_object_sheet.py · Recebe um object sheet PNG, corre Claude Vision,
gera produtos/<id>/{product.json, vision_analysis.json}, copia o sheet,
adiciona entry no _index.json.

Uso:
    python3 ingest_object_sheet.py PATH/TO/object_sheet.png
    python3 ingest_object_sheet.py PATH/TO/object_sheet.png --id mojito --name "Mojito"

Requer:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Custos:
    ~$0.005 por object sheet (Sonnet 4.5 vision call)
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("Erro: instala primeiro com `pip install anthropic`")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOGUE_DIR = REPO_ROOT / "catalogue"
INDEX = CATALOGUE_DIR / "_index.json"
PRODUCTS_DIR = CATALOGUE_DIR / "produtos"


VISION_PROMPT = """Analyse this object sheet image of a Só Rio product (a portuguese river beach lounge in Valada do Ribatejo).

The image is a 2x3 grid (6 cells):
- Cells 1-4: 4 angles of the same product (cenital 0°, 3/4 front 35°, side 90°, high 65°)
- Cells 5-6: detail close-ups WITH context (not isolated ingredients on white)

Extract structured data and return ONLY valid JSON (no markdown, no commentary). The schema:

{
  "product_name_inferred": "Caipirinha de Maracujá" or similar PT-PT name,
  "category": "BEBIDA" | "PRATO" | "AMBIENTE" | "RITUAL",
  "subcategory": "cocktail" | "spritz" | "wine" | "snack" | "main" | "dessert" | "sandwich" | "salad" | "other",
  "ingredients_canonical": ["list", "of", "real", "ingredients"],
  "ingredients_display_short": "ing1 · ing2 · ing3 · ing4 (max 36 chars)",
  "garnish_inside_glass_or_plate": ["what is actually IN the glass/on the plate"],
  "garnish_outside": ["what floats around / styling / props that are NOT in the product"],
  "warning_never_inside": ["e.g. thyme, rosemary — anything that decorates the composition but is NOT a real ingredient"],
  "dominant_colors": ["3-5 keyword colors, e.g. amber-yellow, lime-green, warm-wood"],
  "lighting": "1 sentence description, e.g. 'warm directional, golden hour spill'",
  "subject_position_default": "center" | "lower-third" | "upper-third" | "off-center",
  "background_default": "1-2 word description, e.g. 'wood deck blurred', 'flat verde-salgueiro'",
  "texture_keywords": ["3-5 keywords describing surface textures"],
  "mood_inferred": "fresh_midday" | "aperitivo_18h" | "evening_riverside",
  "notes": "1-2 sentences with any signal/observation worth preserving"
}

CRITICAL RULES:
- Output JSON ONLY. No prose before or after.
- Use Portuguese-PT for ingredient names (Maracujá not Passionfruit, Hortelã not Mint)
- "warning_never_inside" is critical — list any decorative element that LOOKS like an ingredient but is just styling
- Be conservative: if unsure of an ingredient, omit rather than guess
"""


def slugify(text):
    text = text.lower()
    repls = [("á","a"),("à","a"),("â","a"),("ã","a"),("ä","a"),
             ("é","e"),("è","e"),("ê","e"),("ë","e"),
             ("í","i"),("ì","i"),("î","i"),("ï","i"),
             ("ó","o"),("ò","o"),("ô","o"),("õ","o"),("ö","o"),
             ("ú","u"),("ù","u"),("û","u"),("ü","u"),
             ("ç","c"),("ñ","n")]
    for a, b in repls:
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")[:60]


def ask(prompt, default=None, options=None):
    suffix = ""
    if options:
        suffix = f" [{'/'.join(options)}]"
    if default:
        suffix += f" (default: {default})"
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        if options and val and val not in options:
            print(f"  → opção inválida")
            continue
        if val:
            return val


def call_vision(image_path):
    """Chama Claude Vision sobre o object sheet."""
    client = Anthropic()
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/png")

    print("→ A enviar object sheet para Claude Vision...")
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": VISION_PROMPT},
            ],
        }],
    )
    text = msg.content[0].text.strip()
    # Strip markdown fence if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Erro a parsear resposta JSON do Vision: {e}")
        print(f"Texto recebido:\n{text}")
        sys.exit(1)


def build_product_json(vision_data, product_id, name, editorial):
    today = date.today().isoformat()
    return {
        "id": product_id,
        "name": name,
        "category": vision_data.get("category", "BEBIDA"),
        "subcategory": vision_data.get("subcategory", "cocktail"),
        "active": True,
        "ingredients": {
            "canonical": vision_data.get("ingredients_canonical", []),
            "display_short": vision_data.get("ingredients_display_short", ""),
            "display_long": " · ".join(vision_data.get("ingredients_canonical", [])),
            "highlight": vision_data.get("ingredients_canonical", [""])[-1] if vision_data.get("ingredients_canonical") else "",
        },
        "garnish": {
            "inside_glass": vision_data.get("garnish_inside_glass_or_plate", []),
            "outside_glass": vision_data.get("garnish_outside", []),
            "warning_never_inside": vision_data.get("warning_never_inside", []),
            "warning_never_present": [],
        },
        "mood_default": editorial["mood_default"],
        "mood_alternatives": editorial["mood_alternatives"],
        "selo_recommendation": editorial["selo_recommendation"],
        "selo_color_pref": editorial["selo_color_pref"],
        "claim_recommendations": editorial["claim_recommendations"],
        "visual_dna": {
            "dominant_colors": vision_data.get("dominant_colors", []),
            "lighting": vision_data.get("lighting", ""),
            "subject_position_default": vision_data.get("subject_position_default", "lower-third"),
            "background_default": vision_data.get("background_default", ""),
            "texture_keywords": vision_data.get("texture_keywords", []),
        },
        "family_compatibility": editorial["family_compatibility"],
        "object_sheet": "object_sheet.png",
        "vision_analysis": "vision_analysis.json",
        "approved_heroes": [],
        "notes": vision_data.get("notes", ""),
        "season": editorial["season"],
        "price": None,
        "added_date": today,
        "last_updated": today,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Path para object sheet PNG/JPG")
    parser.add_argument("--id", type=str, help="Product slug (default: derivado do nome)")
    parser.add_argument("--name", type=str, help="Nome PT (default: inferido pelo Vision)")
    parser.add_argument("--skip-vision", action="store_true", help="Não correr Vision (usar defaults)")
    args = parser.parse_args()

    if not args.image.exists():
        print(f"Erro: ficheiro não existe: {args.image}")
        sys.exit(1)

    if not INDEX.exists():
        print(f"Erro: _index.json não existe em {INDEX}")
        sys.exit(1)

    # Vision
    if args.skip_vision:
        vision_data = {}
        print("⚠ A saltar Claude Vision (--skip-vision).")
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Erro: ANTHROPIC_API_KEY não está definido. Faz `export ANTHROPIC_API_KEY=sk-ant-...`")
            sys.exit(1)
        vision_data = call_vision(args.image)
        print("\n✓ Vision data recebido:")
        print(json.dumps(vision_data, ensure_ascii=False, indent=2)[:600] + "...\n")

    # Name + ID
    name = args.name or vision_data.get("product_name_inferred") or ask("Nome PT do produto")
    product_id = args.id or slugify(name)

    # Confirmar id
    confirm_id = ask(f"Slug ID", default=product_id)
    product_id = slugify(confirm_id)

    folder = PRODUCTS_DIR / product_id
    if folder.exists():
        print(f"Erro: pasta já existe: {folder}")
        sys.exit(1)

    # Editorial fields (que Vision não infere bem)
    print("\n=== Campos editoriais ===")
    mood_default = ask("Mood default", default=vision_data.get("mood_inferred", "evening_riverside"),
                       options=["fresh_midday", "aperitivo_18h", "evening_riverside"])
    selo_raw = ask("Selos recomendados (comma-separated)", default="ritual_so_rio")
    selo_recommendation = [s.strip() for s in selo_raw.split(",") if s.strip()]
    selo_color = ask("Cor do selo preferida", default="auto", options=["dourado", "creme", "verde", "auto"])
    claim_text = ask("Claim principal", default="Sem pressa. Com rio.")
    season = ask("Season", default="all-year", options=["all-year", "summer", "autumn", "winter", "spring"])

    # Family compatibility
    print("\nFamily compatibility (ideal/good/acceptable/avoid):")
    fam_compat = {}
    for fam in ["F01", "F02", "F03", "F05a", "F05b"]:
        fam_compat[fam] = ask(f"  {fam}", default="good", options=["ideal", "good", "acceptable", "avoid"])

    editorial = {
        "mood_default": mood_default,
        "mood_alternatives": [],
        "selo_recommendation": selo_recommendation,
        "selo_color_pref": selo_color,
        "claim_recommendations": [{"text": claim_text, "context": "default", "weight": 1.0}],
        "family_compatibility": fam_compat,
        "season": season,
    }

    # Build product
    product = build_product_json(vision_data, product_id, name, editorial)

    # Write files
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.image, folder / "object_sheet.png")
    with open(folder / "product.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    if vision_data:
        with open(folder / "vision_analysis.json", "w", encoding="utf-8") as f:
            json.dump(vision_data, f, ensure_ascii=False, indent=2)

    # Update index
    with open(INDEX, "r", encoding="utf-8") as f:
        index = json.load(f)
    summary = {
        "id": product_id,
        "name": name,
        "folder": f"produtos/{product_id}/",
        "object_sheet": f"produtos/{product_id}/object_sheet.png",
        "category": product["category"],
        "subcategory": product["subcategory"],
        "mood_default": mood_default,
        "ingredients_short": product["ingredients"]["display_short"],
        "approved_heroes_count": 0,
        "added_date": product["added_date"],
        "last_updated": product["last_updated"],
    }
    index["products"].append(summary)
    index["stats"]["total_products"] += 1
    cat = product["category"]
    sub = product["subcategory"]
    if cat in index["stats"]["by_category"]:
        index["stats"]["by_category"][cat] += 1
    if sub in index["stats"]["by_subcategory"]:
        index["stats"]["by_subcategory"][sub] += 1
    index["last_updated"] = date.today().isoformat()
    index.pop("schema_example", None)
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Produto criado: produtos/{product_id}/")
    print(f"\nPara push:")
    print(f"  cd {REPO_ROOT}")
    print(f"  git add . && git commit -m 'catalogue: {name}' && git push")


if __name__ == "__main__":
    main()
