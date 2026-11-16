#!/usr/bin/env python3
"""Batch render setup poses (frame 0) for all newly extracted HCG spine models."""

import os
import glob
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKEL_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "skel")
ATLAS_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "atlas")
TEX_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "textures")
OUT_DIR = os.path.join(BASE_DIR, "viewer", "out")
EXE = os.path.join(BASE_DIR, "viewer", "render_anim.exe")

def render_one(stem, force=True):
    out_png = os.path.join(OUT_DIR, f"{stem}.png")
    if not force and os.path.exists(out_png) and os.path.getsize(out_png) > 1024:
        return stem, "cached"

    skel = os.path.join(SKEL_DIR, f"{stem}.skel")
    atlas = os.path.join(ATLAS_DIR, f"{stem}.atlas")
    if not os.path.exists(skel) or not os.path.exists(atlas):
        return stem, "missing_files"

    try:
        page = open(atlas, encoding="utf-8", errors="ignore").readline().strip()
    except Exception:
        return stem, "atlas_read_error"

    pagep = os.path.join(TEX_DIR, page)
    if not os.path.exists(pagep):
        return stem, f"missing_texture_{page}"

    r = subprocess.run([EXE, skel, atlas, pagep, out_png], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and os.path.exists(out_png):
        return stem, "ok"
    return stem, f"render_error: {r.stderr[:80] if r.stderr else 'rc'+str(r.returncode)}"

def main():
    skel_files = sorted(glob.glob(os.path.join(SKEL_DIR, "*hcg*.skel")))
    stems = [os.path.splitext(os.path.basename(s))[0] for s in skel_files if not os.path.basename(s).startswith("assets_")]
    print(f"Total HCG models to render: {len(stems)}")

    done = 0
    ok_count = 0
    cached_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(render_one, stem): stem for stem in stems}
        for future in as_completed(futures):
            stem, status = future.result()
            done += 1
            if status == "ok":
                ok_count += 1
            elif status == "cached":
                cached_count += 1
            else:
                fail_count += 1
            if done % 20 == 0 or done == len(stems):
                print(f"  [{done}/{len(stems)}] (ok={ok_count}, cached={cached_count}, fail={fail_count})")

    print(f"\n[DONE] Finished rendering HCG models: ok={ok_count}, cached={cached_count}, fail={fail_count}")

if __name__ == "__main__":
    main()
