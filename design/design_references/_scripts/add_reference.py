#!/usr/bin/env python3
"""
add_reference.py · Helper interactivo para adicionar refs à biblioteca.

Uso:
    python3 add_reference.py PATH/TO/poster.png

Faz:
    1. Pergunta metadata interactivamente
    2. Cria ref_NNN_slug/ com poster.png + metadata.json
    3. Actualiza _index.json + stats
    4. Imprime comando git para push

Requer Python 3.8+. Sem dependências externas.
"""

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "design" / "design_references"
INDEX = LIB_DIR / "_index.json"


SOURCE_OPTIONS = [
    "own_production",
    "competitor_study",
    "editorial_external",
    "packaging_external",
    "art_direction_external",
]
FAMILY_OPTIONS = ["F01", "F02", "F03", "F05a", "F05b", "external"]
CATEGORY_OPTIONS = ["PRATO", "BEBIDA", "AMBIENTE", "EDITORIAL"]
MOOD_OPTIONS = ["fresh_midday", "aperitivo_18h", "evening_riverside", "n/a"]


def ask(prompt, options=None, default=None, allow_empty=False):
    suffix = ""
    if options:
        suffix = f" [{'/'.join(options)}]"
    if default:
        suffix += f" (default: {default})"
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        if not val and allow_empty:
            return ""
        if options and val not in options:
            print(f"  → opção inválida. Escolhas: {options}")
            continue
        if val:
            return val


def ask_list(prompt, min_items=1):
    print(f"{prompt} (linha vazia para terminar; mínimo {min_items}):")
    items = []
    while True:
        val = input(f"  {len(items) + 1}. ").strip()
        if not val:
            if len(items) < min_items:
                print(f"  → precisas de pelo menos {min_items}.")
                continue
            return items
        items.append(val)


def slugify(text):
    text = text.lower()
    text = re.sub(r"[áàâãä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[íìîï]", "i", text)
    text = re.sub(r"[óòôõö]", "o", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:60]


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_reference.py PATH/TO/poster.png")
        sys.exit(1)

    src = Path(sys.argv[1]).resolve()
    if not src.exists():
        print(f"Erro: ficheiro não existe: {src}")
        sys.exit(1)

    if not INDEX.exists():
        print(f"Erro: _index.json não existe em {INDEX}")
        sys.exit(1)

    with open(INDEX, "r", encoding="utf-8") as f:
        index = json.load(f)

    next_n = index["stats"]["total_refs"] + 1
    ref_id_num = f"{next_n:03d}"

    print(f"\n=== Nova referência · ref_{ref_id_num} ===\n")

    title = ask("Título curto (ex: 'Caipirinha evening · Só Rio')")
    source = ask("Source", options=SOURCE_OPTIONS, default="own_production")
    source_attribution = ask("Source attribution (autor + ano + projecto)", default="Bolder AI Creative Studio")
    family = ask("Family", options=FAMILY_OPTIONS, default="F02")
    category = ask("Category", options=CATEGORY_OPTIONS, default="BEBIDA")
    mood = ask("Mood", options=MOOD_OPTIONS, default="evening_riverside")

    tags_raw = ask("Tags (comma-separated, ex: 'bebida,F02,evening,wood_deck,selo_dourado')")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    typography_summary = ask("Typography summary (1 linha)", default="", allow_empty=True)
    composition_summary = ask("Composition summary (1 linha)", default="", allow_empty=True)
    color_summary = ask("Color palette summary (1 linha)", default="", allow_empty=True)

    why_good = ask_list("Why good (razões específicas, 3+)", min_items=3)
    caveats_raw = ask("Caveats (o que NÃO copiar, opcional, separado por ; )", default="", allow_empty=True)
    caveats = [c.strip() for c in caveats_raw.split(";") if c.strip()]

    principle_match_raw = ask("Principle match (IDs separados por comma, ex: 'UNI-01,TYPO-01')", default="", allow_empty=True)
    principle_match = [p.strip().upper() for p in principle_match_raw.split(",") if p.strip()]

    # Build folder
    slug = slugify(title)
    folder_name = f"ref_{ref_id_num}_{slug}"
    folder = LIB_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=False)

    # Copy poster
    ext = src.suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        print(f"Erro: extensão {ext} não suportada.")
        shutil.rmtree(folder)
        sys.exit(1)
    dst_image = folder / f"poster{ext}"
    shutil.copy2(src, dst_image)

    # Build metadata
    metadata = {
        "id": folder_name,
        "title": title,
        "image": dst_image.name,
        "source": source,
        "source_attribution": source_attribution,
        "added_date": date.today().isoformat(),
        "approved_by": "Gonçalo Carvoeiras",
        "tags": tags,
        "family": family,
        "category": category,
        "mood": mood,
        "typography_summary": typography_summary,
        "composition_summary": composition_summary,
        "color_palette_summary": color_summary,
        "why_good": why_good,
        "caveats": caveats,
        "principle_match": principle_match,
        "principle_violation": [],
    }
    if source != "own_production":
        metadata["copyright_notice"] = "Reference for design study. Not for redistribution."

    with open(folder / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Update index
    summary_entry = {
        "id": folder_name,
        "title": title,
        "folder": f"{folder_name}/",
        "image": f"{folder_name}/{dst_image.name}",
        "source": source,
        "family": family,
        "category": category,
        "mood": mood,
        "tags": tags,
    }
    index["references"].append(summary_entry)
    index["stats"]["total_refs"] += 1
    index["stats"]["by_source"][source] += 1
    if family in index["stats"]["by_family"]:
        index["stats"]["by_family"][family] += 1
    index["last_updated"] = date.today().isoformat()
    # Drop schema_example after first real ref
    index.pop("schema_example", None)

    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Referência criada: {folder_name}")
    print(f"  Image: {dst_image}")
    print(f"  Metadata: {folder / 'metadata.json'}")
    print(f"\nPara fazer push:")
    print(f"  cd {REPO_ROOT}")
    print(f"  git add . && git commit -m 'ref: {title}' && git push")


if __name__ == "__main__":
    main()
