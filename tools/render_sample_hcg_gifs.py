#!/usr/bin/env python3
"""Render sample animated GIFs for top H-scenes."""

import os
import glob
import subprocess
import shutil
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER_DIR = os.path.join(BASE, "viewer")
SKEL = os.path.join(BASE, "dump", "hcg_art", "skel")
ATLAS = os.path.join(BASE, "dump", "hcg_art", "atlas")
TEX = os.path.join(BASE, "dump", "hcg_art", "textures")
EXE = os.path.join(VIEWER_DIR, "render_anim.exe")
GALLERY = os.path.join(VIEWER_DIR, "out", "gallery")

# Prominent H-scene targets and preferred animations
TARGETS = {
    "story_free_hcg01": ["Eat_01", "Eat_02"],
    "story_free_hcg02_spine": ["Blowjob_01", "Finishing_01"],
    "story_hcg01_1_Spine": ["Finishing_01", "Finished_01"],
    "a001_01_hcg": ["Finishing", "Insert"],
    "a001_03_hcg1_Spine": ["Finishing_01", "Finished_01"],
    "a002_01_hcg": ["Finishing", "Insert"],
    "a002_02_hcg1_spine": ["Insert_01", "Finishing_01"],
    "a003_01_hcg": ["Finishing", "Insert"],
    "a004_03_hcg1_Spine": ["Insert_01", "Finishing_01"],
    "ct001_hcg1": ["Finishing_01", "Idle_01"],
    "ct002_hcg1": ["Finishing_01", "Idle_01"],
    "ct003_hcg1": ["Finishing_01", "Idle_01"],
    "d002_04_hcg1_Spine": ["Finishing_01", "Insert_01"],
    "b001_03_hcg1_spine": ["Finishing_01", "Idle_01"],
    "b003_02_hcg1": ["Finishing_01", "Hand_01"]
}

# Load animations manifest for exact durations
MANIFEST_PATH = os.path.join(BASE, "dump", "hcg_art", "animations_manifest.json")
ANIM_MANIFEST = {}
if os.path.exists(MANIFEST_PATH):
    try:
        import json
        ANIM_MANIFEST = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    except Exception as e:
        print(f"Warning loading manifest: {e}")

def get_anim_duration(stem, anim_name):
    char_info = ANIM_MANIFEST.get(stem, {})
    for a in char_info.get("animations", []):
        if a.get("name") == anim_name:
            return float(a.get("duration", 2.0))
    return 2.0

def make_gif(frame_dir, out_gif, total_dur):
    frames = sorted(glob.glob(os.path.join(frame_dir, "frame_*.png")))
    if not frames:
        return False
    try:
        imgs = [Image.open(f).convert("RGBA") for f in frames]
        n = len(imgs)
        # Accurately compute frame delay so the GIF total playback time matches real animation duration
        delay_ms = max(20, int(round((total_dur * 1000.0) / n)))
        imgs[0].save(out_gif, save_all=True, append_images=imgs[1:],
                     loop=0, duration=delay_ms, disposal=2, optimize=False)
        return True
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)

def render_anim_gif(stem, anim_name):
    sk = os.path.join(SKEL, f"{stem}.skel")
    atl = os.path.join(ATLAS, f"{stem}.atlas")
    if not os.path.exists(sk) or not os.path.exists(atl):
        return False
    try:
        page = open(atl, encoding="utf-8", errors="ignore").readline().strip()
    except Exception:
        return False
    pagep = os.path.join(TEX, page)
    if not os.path.exists(pagep):
        return False

    dur = get_anim_duration(stem, anim_name)
    if dur <= 0.05:
        # Static pose - render 1 frame with 1.5s display
        frames = 1
        fps = 1
        dur = 1.5
    else:
        # Dynamic frame count matching target framerate (15 fps), clamped between 16 and 36 frames
        frames = max(16, min(36, int(round(dur * 15.0))))
        fps = 15

    char_dir = os.path.join(GALLERY, stem)
    os.makedirs(char_dir, exist_ok=True)
    gif_path = os.path.join(char_dir, f"{stem}_{anim_name}.gif")
    if os.path.exists(gif_path):
        os.remove(gif_path)

    fdir = os.path.join(char_dir, f"tmp_frames_{anim_name}")
    os.makedirs(fdir, exist_ok=True)
    r = subprocess.run([EXE, sk, atl, pagep, fdir, anim_name, str(frames), str(fps)],
                       capture_output=True, text=True, timeout=120)
    if make_gif(fdir, gif_path, dur):
        size_kb = round(os.path.getsize(gif_path) / 1024, 1)
        print(f"  [OK] Rendered {stem}_{anim_name}.gif ({size_kb} KB, dur={dur:.2f}s, {frames} frames)")
        return True
    else:
        print(f"  [FAIL] Failed {stem}_{anim_name}")
        return False

def main():
    print(f"Starting sample HCG GIF render for {len(TARGETS)} models...")
    for stem, anims in TARGETS.items():
        for an in anims:
            render_anim_gif(stem, an)
    print("All sample HCG GIFs rendered successfully!")

if __name__ == "__main__":
    main()
