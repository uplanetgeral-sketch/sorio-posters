#!/usr/bin/env python3
"""tests/build_index.py · Gera HTML grid review dos resultados da battery.

Uso:
    python3 tests/build_index.py <battery_dir> <manifest.json>
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("usage: build_index.py <battery_dir> <manifest.json>")
        sys.exit(1)

    battery_dir = Path(sys.argv[1])
    manifest_path = Path(sys.argv[2])

    with open(manifest_path) as f:
        runs = json.load(f)

    # Group by family
    by_family = {}
    for r in runs:
        fam = r.get("family", "?")
        by_family.setdefault(fam, []).append(r)

    cards = []
    for fam in sorted(by_family.keys()):
        cards.append(f'<h2 class="fam">{fam}</h2><div class="row">')
        for r in by_family[fam]:
            label = r.get("label", "?")
            mode = r.get("mode", "?")
            score = r.get("score", "n/a")
            publishable = r.get("publishable", "n/a")
            png = r.get("png", "")
            log = r.get("log", "")
            status = r.get("status", "ok")
            badge_class = "ok" if status == "ok" and publishable == "True" else ("review" if status == "ok" else "fail")
            badge = "PUBLISHABLE" if publishable == "True" else ("REVIEW" if status == "ok" else "FAIL")
            img_tag = f'<img src="{png}" alt="{label}">' if png and (battery_dir / png).exists() else '<div class="missing">no png</div>'
            cards.append(f'''
            <div class="card">
              {img_tag}
              <div class="meta">
                <span class="mode">{mode}</span>
                <span class="score">{score}/100</span>
                <span class="badge {badge_class}">{badge}</span>
              </div>
              <div class="label">{label}</div>
              <a class="log" href="{log}" target="_blank">log</a>
            </div>
            ''')
        cards.append('</div>')

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Só Rio · Battery {battery_dir.name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1C1C1A; color: #F6F1E7; font-family: -apple-system, sans-serif; padding: 32px; }}
  h1 {{ font-size: 28px; margin-bottom: 8px; }}
  h2.fam {{ font-size: 22px; margin: 32px 0 16px; color: #C89853; border-bottom: 1px solid #C8985333; padding-bottom: 8px; }}
  .meta-info {{ opacity: 0.65; font-size: 14px; margin-bottom: 24px; }}
  .row {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .card {{ background: #28282A; border-radius: 8px; overflow: hidden; }}
  .card img {{ width: 100%; aspect-ratio: 4/5; object-fit: cover; display: block; background: #000; }}
  .card .missing {{ aspect-ratio: 4/5; background: #38383A; display: flex; align-items: center; justify-content: center; color: #888; }}
  .meta {{ padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; }}
  .mode {{ text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.85; }}
  .score {{ font-weight: 700; color: #F6F1E7; }}
  .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: 0.05em; }}
  .badge.ok {{ background: #2D5C46; color: #6BD4A1; }}
  .badge.review {{ background: #5C4520; color: #E0A65C; }}
  .badge.fail {{ background: #5C2828; color: #E08080; }}
  .label {{ padding: 0 12px 4px; font-family: monospace; font-size: 11px; opacity: 0.55; }}
  .log {{ display: block; padding: 4px 12px 10px; font-size: 11px; color: #C89853; }}
</style>
</head>
<body>
  <h1>Só Rio · Battery review</h1>
  <div class="meta-info">{battery_dir.name} · {len(runs)} runs · grouped by family</div>
  {chr(10).join(cards)}
</body></html>
'''

    out = battery_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"  index.html · {len(runs)} cards · {out}")


if __name__ == "__main__":
    main()
