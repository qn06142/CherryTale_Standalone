#!/usr/bin/env python3
"""Scan all 205 rendered models and build animations_manifest.json."""

import os
import glob
import json
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKEL = os.path.join(BASE, 'dump', 'hcg_art', 'skel')
ATLAS = os.path.join(BASE, 'dump', 'hcg_art', 'atlas')
TEX = os.path.join(BASE, 'dump', 'hcg_art', 'textures')
EXE = os.path.join(BASE, 'viewer', 'render_anim.exe')
OUT_JSON = os.path.join(BASE, 'dump', 'hcg_art', 'animations_manifest.json')

models = sorted([os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(BASE, 'viewer', 'out', '*.png'))])
manifest = {}

print(f"Scanning animations for {len(models)} models...")

for i, stem in enumerate(models):
    sk = os.path.join(SKEL, stem + '.skel')
    atl = os.path.join(ATLAS, stem + '.atlas')
    if not os.path.exists(sk) or not os.path.exists(atl):
        continue
    page = open(atl, encoding='utf-8', errors='ignore').readline().strip()
    pagep = os.path.join(TEX, page)
    if not os.path.exists(pagep):
        continue
    r = subprocess.run([EXE, sk, atl, pagep, 'list'], capture_output=True, text=True)
    anims = []
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if line.startswith("  anim '"):
                name = line.split("'")[1]
                dur_str = line.split("dur=")[1] if "dur=" in line else "0"
                try:
                    dur = float(dur_str)
                except ValueError:
                    dur = 0.0
                anims.append({'name': name, 'duration': dur})
    manifest[stem] = {
        'stem': stem,
        'page': page,
        'frame0_png': f"{stem}.png",
        'animations': anims
    }
    if (i + 1) % 50 == 0 or (i + 1) == len(models):
        print(f"  [{i+1}/{len(models)}] scanned...")

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)

total_anims = sum(len(v['animations']) for v in manifest.values())
print(f"Done! Scanned {len(manifest)} models, found {total_anims} total animations.")
