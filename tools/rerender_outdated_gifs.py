import os
import sys
import glob
import json
import shutil
import subprocess
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(PROJECT_ROOT, "viewer", "render_anim.exe")
GALLERY_DIR = os.path.join(PROJECT_ROOT, "viewer", "out", "gallery")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "animations_manifest.json")

manifest = json.load(open(MANIFEST_PATH, "r", encoding="utf-8"))

def get_skel_files(stem):
    # Try dump/hcg_art/skel and atlas
    sk = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "skel", f"{stem}.skel")
    at = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "atlas", f"{stem}.atlas")
    # Texture
    # Read atlas for texture page
    if os.path.exists(sk) and os.path.exists(at):
        try:
            with open(at, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            tex = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "textures", first_line)
            if os.path.exists(tex):
                return sk, at, tex
        except Exception:
            pass
            
    # Try dump/hcg_spine/<stem>/
    spine_dir = os.path.join(PROJECT_ROOT, "dump", "hcg_spine", stem)
    if os.path.isdir(spine_dir):
        sk = os.path.join(spine_dir, f"{stem}.skel")
        at = os.path.join(spine_dir, f"{stem}.atlas")
        if os.path.exists(sk) and os.path.exists(at):
            with open(at, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            tex = os.path.join(spine_dir, first_line)
            if not os.path.exists(tex):
                tex = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "textures", first_line)
            if os.path.exists(tex):
                return sk, at, tex
                
    # Search recursively for skel
    sk_matches = glob.glob(os.path.join(PROJECT_ROOT, "dump", "**", f"{stem}.skel"), recursive=True)
    if sk_matches:
        sk = sk_matches[0]
        s_dir = os.path.dirname(sk)
        at = os.path.join(s_dir, f"{stem}.atlas")
        if not os.path.exists(at):
            at = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "atlas", f"{stem}.atlas")
        if os.path.exists(at):
            with open(at, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            for cand in [os.path.join(s_dir, first_line), os.path.join(PROJECT_ROOT, "dump", "hcg_art", "textures", first_line)]:
                if os.path.exists(cand):
                    return sk, at, cand
    return None, None, None

def make_gif(frame_dir, out_gif, dur):
    pngs = sorted(glob.glob(os.path.join(frame_dir, "*.png")))
    if not pngs:
        return False
    imgs = [Image.open(p).convert("RGBA") for p in pngs]
    dur_ms = max(20, int(round((dur * 1000.0) / len(imgs))))
    imgs[0].save(
        out_gif,
        save_all=True,
        append_images=imgs[1:],
        duration=dur_ms,
        loop=0,
        optimize=True,
        disposal=2
    )
    return True

all_gifs = glob.glob(os.path.join(GALLERY_DIR, "*", "*.gif"))
outdated = []
for gif in all_gifs:
    stem = os.path.basename(os.path.dirname(gif))
    gif_name = os.path.basename(gif)
    anim_name = gif_name.replace(stem + "_", "").replace(".gif", "")
    im = Image.open(gif)
    curr_dur = round(im.n_frames * im.info.get("duration", 0) / 1000.0, 2)
    entry = manifest.get(stem, {})
    anim_dur = None
    for a in entry.get("animations", []):
        if a["name"] == anim_name:
            anim_dur = a.get("duration", 0)
            break
    if anim_dur and anim_dur > 0.05:
        ratio = curr_dur / anim_dur
        if ratio < 0.7 or ratio > 1.3:
            outdated.append((stem, anim_name, curr_dur, anim_dur, gif))

print(f"Total GIFs to update: {len(outdated)}")

for idx, (stem, anim, old_dur, real_dur, gif_path) in enumerate(outdated, 1):
    print(f"[{idx}/{len(outdated)}] Re-rendering {stem} / {anim} (old={old_dur}s -> real={real_dur:.2f}s)...")
    sk, at, tex = get_skel_files(stem)
    if not sk or not at or not tex:
        print(f"  [SKIP] Missing spine assets for {stem}")
        continue
        
    fdir = os.path.join(os.path.dirname(gif_path), f"frames_tmp_{anim}")
    if os.path.exists(fdir):
        shutil.rmtree(fdir, ignore_errors=True)
    os.makedirs(fdir, exist_ok=True)
    
    num_frames = max(16, min(36, int(round(real_dur * 15.0))))
    fps = 15
    cmd = [EXE, sk, at, tex, fdir, anim, str(num_frames), str(fps)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    if make_gif(fdir, gif_path, real_dur):
        new_im = Image.open(gif_path)
        actual_dur = round(new_im.n_frames * new_im.info.get("duration", 0) / 1000.0, 2)
        print(f"  [OK] Saved {os.path.basename(gif_path)} ({new_im.n_frames} frames @ {new_im.info.get('duration')}ms = {actual_dur}s)")
    else:
        print(f"  [FAIL] Failed to make gif for {stem} / {anim}")
        
    shutil.rmtree(fdir, ignore_errors=True)

print("Done! All outdated GIFs re-rendered.")
