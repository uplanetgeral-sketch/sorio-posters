#!/usr/bin/env python3
"""tests/rebuild_index.py · Reconstrói manifest.json e index.html a partir dos logs.

Útil quando uma battery correu mas o post-processing falhou (ex: bug no parser
de paths com espaços). Não precisa de re-correr — lê os *.log existentes.

Uso:
    python3 tests/rebuild_index.py <battery_dir>

Ex:
    python3 tests/rebuild_index.py tests/battery_runs/20260425_191358
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def parse_log(log_path):
    """Extrai metadata do log do orchestrator. Devolve dict ou None se falhou."""
    text = log_path.read_text(encoding='utf-8', errors='replace')
    label = log_path.stem  # ex "F01_variation"

    parts = label.split('_')
    family = parts[0] if parts else '?'
    mode = parts[1] if len(parts) > 1 else '?'

    # Padrões de extracção (multi-linha aceita paths com espaços)
    m_rundir = re.search(r'^Run dir:\s+(.+)$', text, re.MULTILINE)
    m_score = re.search(r'^Final score:\s+(\d+)', text, re.MULTILINE)
    m_pub = re.search(r'^Final publishable:\s+(\S+)', text, re.MULTILINE)
    m_png = re.search(r'^Final PNG:\s+(\S+)', text, re.MULTILINE)

    if not m_rundir:
        # Run não chegou ao fim
        return {
            'label': label,
            'family': family,
            'mode': mode,
            'status': 'failed',
            'log': log_path.name,
        }

    return {
        'label': label,
        'family': family,
        'mode': mode,
        'status': 'ok',
        'run_dir': m_rundir.group(1).strip(),
        'score': m_score.group(1) if m_score else 'n/a',
        'publishable': m_pub.group(1) if m_pub else 'n/a',
        'png_name': m_png.group(1) if m_png else None,
        'log': log_path.name,
    }


def main():
    if len(sys.argv) != 2:
        print('usage: rebuild_index.py <battery_dir>')
        sys.exit(1)

    battery_dir = Path(sys.argv[1]).resolve()
    if not battery_dir.is_dir():
        print(f'ERRO: {battery_dir} não existe')
        sys.exit(1)

    logs = sorted(battery_dir.glob('*.log'))
    if not logs:
        print(f'ERRO: sem *.log em {battery_dir}')
        sys.exit(1)

    print(f'Rebuilding index from {len(logs)} logs in {battery_dir}')

    runs = []
    for log in logs:
        run = parse_log(log)
        runs.append(run)

        if run['status'] == 'ok':
            # Copy PNG + symlink run_dir
            run_dir = Path(run['run_dir'])
            png_name = run.get('png_name')
            if png_name:
                src_png = run_dir / png_name
                if src_png.exists():
                    dest_png = battery_dir / f"{run['label']}.png"
                    shutil.copy2(src_png, dest_png)
                    run['png'] = dest_png.name
                    print(f"  ✓ {run['label']:30}  score {run.get('score', '?'):>3}  png copiado")
                else:
                    print(f"  ⚠ {run['label']:30}  PNG não existe: {src_png}")

            # Symlink to run dir
            symlink = battery_dir / f"{run['label']}_run"
            if symlink.exists() or symlink.is_symlink():
                symlink.unlink()
            try:
                symlink.symlink_to(run_dir)
            except Exception as e:
                print(f"  ⚠ symlink falhou: {e}")
        else:
            print(f"  ✗ {run['label']:30}  status=failed")

    # Write manifest
    manifest = battery_dir / 'manifest.json'
    manifest.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nManifest: {manifest}')

    # Build index.html
    script_dir = Path(__file__).parent
    build_script = script_dir / 'build_index.py'
    subprocess.run(['python3', str(build_script), str(battery_dir), str(manifest)], check=True)

    print(f'\nIndex: {battery_dir / "index.html"}')
    print(f'Para abrir: open "{battery_dir / "index.html"}"')


if __name__ == '__main__':
    main()
