#!/usr/bin/env python3
"""Build the upgraded CherryTale Datamine Web Viewer & Gallery with Full Audio and Enhanced UX.

Generates viewer/index.html with:
- All 456 distinct Spine models (251 H-Scenes / HCG and 205 Character CGs)
- 90 CherryTale Original BGM Tracks with floating / docked BGM player & playlist drawer
- Over 20,000 authentic Character & H-scene voice lines (Touch, Intimacy, Favorability, Combat)
- Clickable 🔊 voice buttons next to every voiced English dialogue line in Visual Novel mode
- "▶ Auto-Play Story" interactive reader that plays voices sequentially
- Modern glassmorphism UI with Sakura/Obsidian dark aesthetic
- Complete character selector dropdown (60+ characters) + quick popular character chips
- Dynamic sorting (A-Z, Most Animations, Most GIFs, Category)
- Grid density toggle (Standard, Compact, Large Showcards)
- Stage background switcher (Obsidian, Studio Navy, Transparent Checkerboard, Spotlight White)
- Fullscreen mode (⛶) and Zoom/Pan controls for fine Spine detail inspection
- Left/Right keyboard arrow navigation across models in modal
- 1-click audio downloads and animated GIF downloads with toast feedback
"""

import os
import sys
import glob
import json
import html
import re
from typing import Union

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER_DIR = os.path.join(BASE_DIR, "viewer")
OUT_DIR = os.path.join(VIEWER_DIR, "out")
THUMBS_DIR = os.path.join(VIEWER_DIR, "thumbs")
DATA_DIR = os.path.join(VIEWER_DIR, "data")
GALLERY_DIR = os.path.join(OUT_DIR, "gallery")
DUMP_DIR = os.path.join(BASE_DIR, "dump")
TEXT_DIR = os.path.join(DUMP_DIR, "textassets")

for d in [OUT_DIR, THUMBS_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)

def write_if_changed(path: str, content: Union[str, bytes], encoding: str = "utf-8") -> bool:
    """Write content to path only if the file does not exist or its content differs.

    Returns:
        bool: True if the file was written, False if skipped because content was identical.
    """
    data = content.encode(encoding) if isinstance(content, str) else content
    path_str = os.fspath(path)
    if os.path.exists(path_str):
        try:
            if os.path.getsize(path_str) == len(data):
                with open(path_str, "rb") as f:
                    if f.read() == data:
                        return False
        except OSError:
            pass
    parent = os.path.dirname(path_str)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path_str, "wb") as f:
        f.write(data)
    return True

sys.path.insert(0, VIEWER_DIR)
import gallery_server

sys.path.insert(0, BASE_DIR)
from tools.audio_manager import audio_manager

print("🚀 Building CherryTale Datamine Web Gallery with Audio & Enhanced UX...")

# 1. Load English translation dictionary
enus_path = os.path.join(TEXT_DIR, "LanguageSettings_enus.txt")
trans_map = {}
if os.path.exists(enus_path):
    with open(enus_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "|" in line and "\u2524" in line:
                k, v = line.split("|", 1)
                zh = k.strip()
                en = v.split("\u2524")[0].strip()
                if zh and en:
                    trans_map[zh] = en
print(f"[1/6] Loaded {len(trans_map):,} English localization entries.")

def tr(text):
    if not text or text in ("NULL", "-1"):
        return ""
    text_clean = re.sub(r'<[^>]+>', '', text).strip().rstrip("\u2524").strip()
    if not text_clean:
        return ""
    if text_clean in trans_map:
        return trans_map[text_clean]
    for p in ["\uff01", "\uff1f", "\uff0c", "\u3002", "……", "♥", "…", "！", "？", "，", "。"]:
        if text_clean.endswith(p) and text_clean[:-len(p)] in trans_map:
            return trans_map[text_clean[:-len(p)]]
    return text_clean

# 2. Load Character Registry
char_index_file = os.path.join(DUMP_DIR, "characters_index.json")
char_registry = {}
if os.path.exists(char_index_file):
    try:
        char_registry = json.load(open(char_index_file, encoding="utf-8"))
    except Exception as e:
        print(f"Warning loading characters_index.json: {e}")
print(f"[2/6] Loaded {len(char_registry)} characters from registry.")

# 3. Load Animations Manifest
anim_manifest_file = os.path.join(DUMP_DIR, "hcg_art", "animations_manifest.json")
anim_manifest = {}
if os.path.exists(anim_manifest_file):
    try:
        anim_manifest = json.load(open(anim_manifest_file, encoding="utf-8"))
    except Exception as e:
        print(f"Warning loading animations_manifest.json: {e}")
print(f"[3/6] Loaded animations manifest for {len(anim_manifest)} models.")

# 4. Load Role Dialogues
role_dialogs_by_pfx = {}
role_dialog_file = os.path.join(TEXT_DIR, "RoleDialogHomePageData.txt")
if not os.path.exists(role_dialog_file):
    role_dialog_file = os.path.join(TEXT_DIR, "RoleDialogHomePageData.bytes")
if os.path.exists(role_dialog_file):
    with open(role_dialog_file, "r", encoding="utf-8", errors="ignore") as f:
        rlines = f.read().splitlines()
    rheader = [h.strip().rstrip("┤") for h in rlines[0].split("|")]
    v_idx = rheader.index("roleVoive") if "roleVoive" in rheader else -1
    t_idx = rheader.index("roleDialogText") if "roleDialogText" in rheader else -1
    tag_idx = rheader.index("lineTag") if "lineTag" in rheader else -1

    for line in rlines[1:]:
        row = [c.strip().rstrip("┤") for c in line.split("|")]
        if len(row) <= max(v_idx, t_idx):
            continue
        v_clip = row[v_idx] if v_idx >= 0 else ""
        text_zh = row[t_idx] if t_idx >= 0 else ""
        tag = row[tag_idx] if tag_idx >= 0 else "Voice"
        if v_clip and v_clip not in ("-1", "NULL", ""):
            m = re.search(r"vic_([a-z]\d{3}(?:_\d{2})?|ct\d+|[a-z]{2}\d+)", v_clip)
            if m:
                pfx = m.group(1)
                text_en = tr(text_zh) or text_zh
                role_dialogs_by_pfx.setdefault(pfx, []).append({
                    "tag": tag,
                    "clip": v_clip,
                    "text_zh": text_zh,
                    "text_en": text_en,
                    "url": f"/audio/voice/{v_clip}"
                })
print(f"[4/6] Loaded role dialogues across {len(role_dialogs_by_pfx)} character prefixes.")

# 5. Load StoryHData dialogues & English localized lines
storyh_file = os.path.join(TEXT_DIR, "StoryHData.txt")
if not os.path.exists(storyh_file):
    storyh_file = os.path.join(TEXT_DIR, "StoryHData.bytes")
en_full_file = os.path.join(DUMP_DIR, "hscene_en", "storyhdata_EN_full.txt")
scene_dialogues = {}
scene_bgm_map = {}

if os.path.exists(storyh_file) and os.path.exists(en_full_file):
    with open(storyh_file, "r", encoding="utf-8", errors="ignore") as f_raw, \
         open(en_full_file, "r", encoding="utf-8", errors="ignore") as f_en:
        raw_lines = f_raw.read().splitlines()[1:]
        en_lines = f_en.read().splitlines()

        sheader = [h.strip().rstrip("┤") for h in open(storyh_file, encoding="utf-8", errors="ignore").readline().split("|")]
        id_col = sheader.index("id")
        text_col = sheader.index("text")
        spk_col = sheader.index("speakerNote") if "speakerNote" in sheader else -1
        snd_col = sheader.index("charSound") if "charSound" in sheader else -1
        bgm_col = sheader.index("music") if "music" in sheader else -1
        se_col = sheader.index("sceneSound") if "sceneSound" in sheader else -1
        se_times_col = sheader.index("sceneSoundTimes") if "sceneSoundTimes" in sheader else -1
        se_intv_col = sheader.index("sceneSoundInterval") if "sceneSoundInterval" in sheader else -1
        succ_col = sheader.index("successiveSound") if "successiveSound" in sheader else -1
        anim_col = sheader.index("spineAnimName") if "spineAnimName" in sheader else -1

        for idx, (raw_l, en_l) in enumerate(zip(raw_lines, en_lines)):
            row = [c.strip().rstrip("┤") for c in raw_l.split("|")]
            if len(row) <= text_col:
                continue
            sid = row[id_col]
            text_zh = row[text_col]
            if not text_zh or text_zh in ("-1", "NULL"):
                continue

            spk_raw = row[spk_col] if spk_col >= 0 else ""
            spk_clean = re.sub(r'<[^>]+>', '', spk_raw).strip()
            speaker_en = ""
            text_en = en_l.strip()
            if text_en.startswith("[") and "]" in text_en:
                speaker_en, text_en = text_en[1:].split("]", 1)
                text_en = text_en.strip()

            v_clip = row[snd_col] if snd_col >= 0 else None
            if v_clip in ("-1", "NULL", ""):
                v_clip = None

            bgm_val = row[bgm_col] if bgm_col >= 0 else None
            if bgm_val in ("-1", "NULL", ""):
                bgm_val = None
            elif sid not in scene_bgm_map and bgm_val:
                scene_bgm_map[sid] = bgm_val

            se_val = row[se_col] if se_col >= 0 else None
            if se_val in ("-1", "NULL", ""):
                se_val = None

            sfx_tracks = []
            if se_val:
                se_parts = se_val.split('$')
                times_parts = row[se_times_col].split('$') if se_times_col >= 0 and row[se_times_col] != '-1' else []
                intv_parts = row[se_intv_col].split('$') if se_intv_col >= 0 and row[se_intv_col] != '-1' else []
                for p_idx, p in enumerate(se_parts):
                    p = p.strip()
                    if not p or p == '-1':
                        continue
                    sub_parts = re.findall(r'(se_hstory\d+(?:_\d+)?|vic_[A-Za-z0-9_\-]+)', p, re.IGNORECASE)
                    if not sub_parts:
                        sub_parts = [p]
                    for sp in sub_parts:
                        t = times_parts[p_idx].strip() if p_idx < len(times_parts) else '1'
                        inv = float(intv_parts[p_idx].strip()) if p_idx < len(intv_parts) and intv_parts[p_idx] not in ('-1', '') else 0.0
                        is_loop = (t == '0')
                        if sp.startswith('se_'):
                            sfx_tracks.append({
                                'type': 'se',
                                'clip': sp,
                                'url': f'/audio/se/{sp}',
                                'loop': is_loop,
                                'interval': inv
                            })
                        elif 'loop' in sp.lower() or sp.startswith('vic_'):
                            sfx_tracks.append({
                                'type': 'moan',
                                'clip': sp,
                                'url': f'/audio/voice/{sp}',
                                'loop': is_loop,
                                'interval': inv
                            })

            anim_val = row[anim_col] if anim_col >= 0 else None
            if anim_val in ("-1", "NULL", "", "0"):
                anim_val = None

            scene_dialogues.setdefault(sid, []).append({
                "speaker": speaker_en,
                "speaker_zh": spk_clean,
                "text": text_en,
                "text_zh": text_zh,
                "voice_clip": v_clip,
                "voice_url": f"/audio/voice/{v_clip}" if v_clip else None,
                "bgm": bgm_val,
                "anim": anim_val,
                "sfx_tracks": sfx_tracks
            })
print(f"[5/6] Indexed {len(scene_dialogues)} H-Scenes with dialogue & voice links.")

# 6. Gather all models from OUT_DIR and dump/hcg_art/skel
stems_set = set()
for p in glob.glob(os.path.join(OUT_DIR, "*.png")):
    stems_set.add(os.path.splitext(os.path.basename(p))[0])
for p in glob.glob(os.path.join(DUMP_DIR, "hcg_art", "skel", "*.skel")):
    stems_set.add(os.path.splitext(os.path.basename(p))[0])
if not stems_set:
    for p in glob.glob(os.path.join(DUMP_DIR, "hcg_art", "textures", "*.png")):
        stems_set.add(os.path.splitext(os.path.basename(p))[0])

model_stems = sorted(list(stems_set))
print(f"[6/6] Processing {len(model_stems)} models...")

import subprocess
_RENDER_EXE = os.path.join(VIEWER_DIR, "render_anim.exe")
def scan_animations(stem):
    sk = os.path.join(DUMP_DIR, "hcg_art", "skel", stem + ".skel")
    atl = os.path.join(DUMP_DIR, "hcg_art", "atlas", stem + ".atlas")
    if not (os.path.exists(sk) and os.path.exists(atl) and os.path.exists(_RENDER_EXE)):
        return []
    try:
        page = open(atl, encoding="utf-8", errors="ignore").readline().strip()
        r = subprocess.run([_RENDER_EXE, sk, atl, os.path.join(DUMP_DIR, "hcg_art", "textures", page), "list"],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        if line.startswith("  anim '"):
            try:
                dur = float(line.split("dur=")[1])
            except Exception:
                dur = 0.0
            out.append({"name": line.split("'")[1], "duration": dur})
    return out

# Concurrently scan any models missing from animations_manifest.json and persist
from concurrent.futures import ThreadPoolExecutor

missing_stems = [s for s in model_stems if s not in anim_manifest or anim_manifest[s].get("animations") is None]
if missing_stems:
    print(f"  Scanning Spine animations concurrently for {len(missing_stems)} missing models...")
    max_workers = min(16, os.cpu_count() or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        scanned_results = list(pool.map(lambda s: (s, scan_animations(s)), missing_stems))

    for s, anims in scanned_results:
        anim_manifest[s] = {
            "stem": s,
            "page": f"{s}.png",
            "frame0_png": f"{s}.png",
            "animations": anims
        }

    try:
        os.makedirs(os.path.dirname(anim_manifest_file), exist_ok=True)
        tmp_manifest = anim_manifest_file + ".tmp"
        with open(tmp_manifest, "w", encoding="utf-8") as f_manifest:
            json.dump(anim_manifest, f_manifest, indent=2, ensure_ascii=False)
        os.replace(tmp_manifest, anim_manifest_file)
        print(f"  ✓ Persisted {len(missing_stems)} newly scanned models to {anim_manifest_file}")
    except Exception as e:
        print(f"  Warning: Failed to persist animations_manifest.json: {e}")

detail_files_written = 0
detail_files_skipped = 0
models_data = []
all_character_names = set()

# Touch voice mapping helper
touch_voices_by_stem = {}
for clip_name in audio_manager.clip_to_bundle:
    if clip_name.startswith("assets_"):
        continue
    if "tou_" in clip_name.lower():
        # e.g. vic_a001_03_tou_01
        m = re.search(r"vic_([a-z0-9_]+?)_tou_([a-z0-9_]+)", clip_name, re.IGNORECASE)
        if m:
            stem_key = m.group(1).lower()
            t_type = m.group(2).lower()
            name_map = {
                "01": "Touch Dialogue 1",
                "02": "Touch Dialogue 2",
                "bom": "Special Intimate Touch",
                "bon": "Bond Touch",
                "bon_end": "Bond Climax & Release",
                "fin": "Max Affection Finish",
                "par": "Party Greeting"
            }
            entry = {
                "name": name_map.get(t_type, f"Touch {t_type.title()}"),
                "clip": clip_name,
                "url": f"/audio/voice/{clip_name}",
                "tag": "Touch"
            }
            touch_voices_by_stem.setdefault(stem_key, []).append(entry)
            pfx_key = stem_key.split("_")[0]
            if pfx_key != stem_key:
                touch_voices_by_stem.setdefault(pfx_key, []).append(entry)

for stem in model_stems:
    filename = f"{stem}.png"
    is_hcg = "hcg" in stem.lower()

    # Prefix extraction
    m = re.match(r"^([a-z]\d{3}|ct\d+|[a-z]{2}\d+|story_free_hcg\d+|story_hcg\d+|teaching_hcg\d+)", stem)
    if m:
        pfx = m.group(1)
    elif "story_free_hcg" in stem:
        pfx = "story_free_hcg" + stem.split("story_free_hcg")[1][:2]
    elif "story_hcg" in stem:
        pfx = "story_hcg" + stem.split("story_hcg")[1][:2]
    else:
        pfx = stem[:6]

    # Character metadata
    char_info = char_registry.get(pfx, {})
    name_en = char_info.get("name_en", "")
    name_zh = char_info.get("name_zh", "")

    if not name_en or name_en == pfx.upper():
        name_en = stem.replace("_", " ").title()
        name_zh = ""

    all_character_names.add(name_en)

    # Animations
    anim_entry = anim_manifest.get(stem, {})
    animations = anim_entry.get("animations")
    if animations is None:
        animations = scan_animations(stem)
    animations = animations or []

    # Pre-rendered GIFs
    char_gallery_dir = os.path.join(GALLERY_DIR, stem)
    gifs = []
    anim_dur_map = {a["name"]: a.get("duration", 0) for a in animations}
    if os.path.exists(char_gallery_dir):
        for gif_path in sorted(glob.glob(os.path.join(char_gallery_dir, "*.gif"))):
            gif_name = os.path.basename(gif_path)
            an_name = gif_name.replace(f"{stem}_", "").replace(".gif", "")
            d_val = anim_dur_map.get(an_name, 0)
            gifs.append({
                "anim": an_name,
                "duration": d_val,
                "url": f"out/gallery/{stem}/{gif_name}",
                "size_mb": round(os.path.getsize(gif_path) / (1024 * 1024), 2)
            })

    # Dialogues Resolution with comprehensive smart key matching
    dialogues = []
    default_bgm = None
    s_low = stem.lower()
    candidate_scene_keys = [
        stem + "_sh",
        s_low + "_sh",
        re.sub(r'hcg.*', 'hcg01_sh', s_low),
        re.sub(r'hcg.*', 'hcg1_sh', s_low),
        re.sub(r'(_spine|_spine_.*|_\d+)$', '', s_low) + '_sh',
        re.sub(r'(_spine|_spine_.*|_\d+)$', '', re.sub(r'hcg.*', 'hcg01', s_low)) + '_sh',
        re.sub(r'(_spine|_spine_.*|_\d+)$', '', re.sub(r'hcg.*', 'hcg1', s_low)) + '_sh',
    ]
    m_pfx = re.match(r'^([a-z]\d{3}_\d{2})', s_low)
    if m_pfx:
        candidate_scene_keys.extend([
            m_pfx.group(1) + '_hcg01_sh',
            m_pfx.group(1) + '_hcg02_sh'
        ])
    m_ct = re.match(r'^(ct\d+)', s_low)
    if m_ct:
        candidate_scene_keys.extend([
            m_ct.group(1) + '_hcg01_sh',
            m_ct.group(1) + '_hcg1_sh',
            m_ct.group(1) + '_hcg02_sh'
        ])

    for ck in candidate_scene_keys:
        if ck in scene_dialogues:
            dialogues = scene_dialogues[ck][:400]
            default_bgm = scene_bgm_map.get(ck)
            break
        elif ck.lower() in [s.lower() for s in scene_dialogues]:
            for actual_s in scene_dialogues:
                if actual_s.lower() == ck.lower():
                    dialogues = scene_dialogues[actual_s][:400]
                    default_bgm = scene_bgm_map.get(actual_s)
                    break
            if dialogues:
                break

    # Voices Resolution
    # A. Touch voices
    touch_voices = []
    clean_stem = re.sub(r'(_CG|_hcg\d*|_spine|_Spine)$', '', stem, flags=re.IGNORECASE).lower()
    if clean_stem in touch_voices_by_stem:
        touch_voices = touch_voices_by_stem[clean_stem]
    elif stem.lower() in touch_voices_by_stem:
        touch_voices = touch_voices_by_stem[stem.lower()]
    elif pfx.lower() in touch_voices_by_stem:
        touch_voices = touch_voices_by_stem[pfx.lower()]
    else:
        # Search for any touch voice with pfx
        for t_k, t_list in touch_voices_by_stem.items():
            if t_k.startswith(pfx.lower()):
                touch_voices = t_list
                break

    # B. Role dialogues
    role_voices = []
    if clean_stem in role_dialogs_by_pfx:
        role_voices = role_dialogs_by_pfx[clean_stem]
    elif pfx in role_dialogs_by_pfx:
        role_voices = role_dialogs_by_pfx[pfx]
    elif pfx.lower() in role_dialogs_by_pfx:
        role_voices = role_dialogs_by_pfx[pfx.lower()]

    has_voice = bool(touch_voices or role_voices or any(d.get("voice_clip") for d in dialogues))

    # Fallback in-game BGM if scene didn't specify one
    if not default_bgm:
        if is_hcg:
            default_bgm = "music_sex_01"
        else:
            default_bgm = "a01_a01_bpm140_210_inst"

    # Animation to voice interactive reaction map
    anim_voice_map = {}
    greeting_voice = None
    greeting_text = ""

    t01 = next((v for v in touch_voices if "Dialogue 1" in v["name"] or "01" in v.get("clip", "")), None)
    t02 = next((v for v in touch_voices if "Dialogue 2" in v["name"] or "02" in v.get("clip", "")), None)
    t_bon = next((v for v in touch_voices if "Bond" in v["name"] or "bon" in v.get("clip", "")), None)
    t_fin = next((v for v in touch_voices if "Finish" in v["name"] or "fin" in v.get("clip", "") or "bon_end" in v.get("clip", "")), None)

    r_intro = next((v for v in role_voices if v.get("tag") == "好感對話"), None)
    r_intimate = next((v for v in role_voices if "好感對話(III)" in v.get("tag", "") or "好感對話(II)" in v.get("tag", "")), None)
    r_vic = next((v for v in role_voices if "勝利" in v.get("tag", "")), None)

    if t01:
        greeting_voice = t01["url"]
        greeting_text = t01.get("text") or "..."
    elif r_intro:
        greeting_voice = r_intro["url"]
        greeting_text = r_intro.get("text") or "..."
    elif touch_voices:
        greeting_voice = touch_voices[0]["url"]
        greeting_text = touch_voices[0].get("text") or "..."
    elif role_voices:
        greeting_voice = role_voices[0]["url"]
        greeting_text = role_voices[0].get("text") or "..."

    for a in animations:
        an_name = a["name"]
        an_l = an_name.lower()
        if "touch" in an_l:
            if "1" in an_l and t01:
                anim_voice_map[an_name] = t01["url"]
            elif "2" in an_l and t02:
                anim_voice_map[an_name] = t02["url"]
            elif "3" in an_l and t_bon:
                anim_voice_map[an_name] = t_bon["url"]
            elif "4" in an_l and (t_fin or r_intimate):
                anim_voice_map[an_name] = (t_fin or r_intimate)["url"]
            elif touch_voices:
                anim_voice_map[an_name] = touch_voices[0]["url"]
        elif "talk" in an_l:
            if r_intro:
                anim_voice_map[an_name] = r_intro["url"]
            elif t01:
                anim_voice_map[an_name] = t01["url"]
            elif role_voices:
                anim_voice_map[an_name] = role_voices[0]["url"]
        elif "vic" in an_l or "win" in an_l:
            if r_vic:
                anim_voice_map[an_name] = r_vic["url"]

    thumb_file = f"{stem}.webp"
    has_thumb = os.path.exists(os.path.join(THUMBS_DIR, thumb_file))
    thumb_url = f"/thumbs/{thumb_file}" if has_thumb else (f"/out/{filename}" if os.path.exists(os.path.join(OUT_DIR, filename)) else f"/spines/{stem}/{stem}.png")
    has_spine = (stem in gallery_server.SKEL_INDEX or stem.lower() in gallery_server.SKEL_INDEX)

    # Extract distinct scene phases for H-scenes
    h_phases = []
    if is_hcg and dialogues:
        seen_anims = set()
        for d_idx, d in enumerate(dialogues):
            anim_name = d.get("anim")
            if anim_name:
                first_anim = anim_name.split('$')[0].strip()
                if first_anim and first_anim not in seen_anims:
                    seen_anims.add(first_anim)
                    lbl = first_anim.replace('_', ' ')
                    h_phases.append({
                        "line_idx": d_idx,
                        "anim": first_anim,
                        "label": lbl
                    })

    # Save detailed data for on-demand loading
    detail_data = {
        "stem": stem,
        "dialogues": dialogues,
        "touch_voices": touch_voices[:16],
        "role_voices": role_voices[:20]
    }
    detail_path = os.path.join(DATA_DIR, f"{stem}.json")
    detail_json = json.dumps(detail_data, ensure_ascii=False)
    if write_if_changed(detail_path, detail_json):
        detail_files_written += 1
    else:
        detail_files_skipped += 1

    models_data.append({
        "stem": stem,
        "prefix": pfx,
        "is_hcg": is_hcg,
        "category": "H-Scene (HCG)" if is_hcg else "Character CG",
        "name_en": name_en,
        "name_zh": name_zh,
        "frame0_url": f"/out/{filename}",
        "thumb_url": thumb_url,
        "has_spine": has_spine,
        "animations": animations,
        "gifs": gifs,
        "dialogue_count": len(dialogues),
        "touch_voice_count": len(touch_voices),
        "role_voice_count": len(role_voices),
        "default_bgm": default_bgm,
        "anim_voice_map": anim_voice_map,
        "greeting_voice": greeting_voice,
        "greeting_text": greeting_text,
        "has_voice": has_voice,
        "h_phases": h_phases
    })

total_hcg = sum(1 for m in models_data if m["is_hcg"])
total_cg = len(models_data) - total_hcg
total_gifs = sum(1 for m in models_data if m["gifs"])
total_anims = sum(len(m["animations"]) for m in models_data)
total_voiced = sum(1 for m in models_data if m["has_voice"])

# Generate catalog.json for /api/catalog server endpoint
catalog_list = [
    {"stem": m["stem"], "name": m["name_en"], "code": m["prefix"]}
    for m in models_data
]
catalog_list.sort(key=lambda x: x["name"])
catalog_path = os.path.join(DATA_DIR, "catalog.json")
catalog_json = json.dumps(catalog_list, ensure_ascii=False, indent=2)
cat_written = write_if_changed(catalog_path, catalog_json)

print(f"✅ Processed {len(models_data)} models:")
print(f"   - H-Scenes (HCG): {total_hcg}")
print(f"   - Character CGs: {total_cg}")
print(f"   - Models with Live 60 FPS Spine: {sum(1 for m in models_data if m['has_spine'])}")
print(f"   - Models with Animated GIFs: {total_gifs}")
print(f"   - Models with Voice Acting: {total_voiced}")
print(f"   - Total Spine Animations: {total_anims:,}")
print(f"   - On-demand JSON files: {detail_files_written} written, {detail_files_skipped} up to date")
if cat_written:
    print(f"   - Catalog index: generated {catalog_path}")
else:
    print(f"   - Catalog index: up to date")

# Character counts for dropdown selector
char_counts = {}
for m in models_data:
    n = m["name_en"]
    char_counts[n] = char_counts.get(n, 0) + 1

sorted_char_options = sorted(char_counts.items(), key=lambda x: x[0])

# Serialize data
json_models = json.dumps(models_data, ensure_ascii=False)
json_bgms = json.dumps(audio_manager.bgm_catalog, ensure_ascii=False)

html_content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CherryTale Datamine — Character & H-Scene Spine Gallery</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220%22%3E<text y=%2226%22 font-size=%2224%22>🌸</text></svg>">
<link rel="stylesheet" href="vendor/spine-player.css">
<script src="vendor/spine-player.js?v=6"></script>
<style>
  :root {{
    --bg-main: #070a10;
    --bg-surface: #0f1420;
    --bg-card: #151d2d;
    --bg-card-hover: #1e293f;
    --accent: #ff4d8d;
    --accent-light: #ff7aa8;
    --accent-glow: rgba(255, 77, 141, 0.35);
    --hcg-accent: #ff3366;
    --cg-accent: #8b5cf6;
    --voice-accent: #f59e0b;
    --bgm-accent: #06b6d4;
    --gif-accent: #10b981;
    --text-primary: #f1f5f9;
    --text-muted: #94a3b8;
    --border: #232f45;
    --border-hover: #3b4d6e;
    --glass-bg: rgba(15, 20, 32, 0.85);
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg-main);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
  }}

  /* Custom Scrollbar */
  ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg-main); }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: var(--border-hover); }}

  /* Sticky Top Header */
  header {{
    background: var(--glass-bg);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
  }}

  .header-container {{
    max-width: 1720px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
  }}

  .brand {{
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }}
  .brand-logo {{
    font-size: 32px;
    filter: drop-shadow(0 0 12px var(--accent));
    animation: gentle-pulse 3s infinite ease-in-out;
  }}
  @keyframes gentle-pulse {{
    0%, 100% {{ transform: scale(1); filter: drop-shadow(0 0 10px var(--accent)); }}
    50% {{ transform: scale(1.08); filter: drop-shadow(0 0 18px var(--accent-light)); }}
  }}
  .brand-title {{
    font-size: 21px;
    font-weight: 700;
    letter-spacing: -0.4px;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .brand-badge {{
    font-size: 11px;
    background: rgba(255, 77, 141, 0.18);
    color: var(--accent-light);
    border: 1px solid rgba(255, 77, 141, 0.35);
    padding: 2px 7px;
    border-radius: 12px;
    font-weight: 600;
  }}
  .brand-subtitle {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
  }}

  .header-actions {{
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }}

  .search-bar {{
    display: flex;
    align-items: center;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 6px 16px;
    width: 320px;
    transition: all 0.2s;
    position: relative;
  }}
  .search-bar:focus-within {{
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-glow);
    width: 360px;
  }}
  .search-icon {{
    font-size: 14px;
    color: var(--text-muted);
    margin-right: 8px;
  }}
  .search-input {{
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 13px;
    width: 100%;
    outline: none;
  }}
  .search-clear {{
    display: none;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
  }}
  .search-kbd {{
    font-size: 10px;
    background: rgba(255,255,255,0.08);
    border: 1px solid var(--border);
    padding: 2px 5px;
    border-radius: 4px;
    color: var(--text-muted);
  }}

  /* Mini BGM Bar in Header */
  .bgm-header-widget {{
    display: flex;
    align-items: center;
    background: rgba(6, 182, 212, 0.1);
    border: 1px solid rgba(6, 182, 212, 0.25);
    padding: 6px 14px;
    border-radius: 20px;
    gap: 10px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .bgm-header-widget:hover {{
    background: rgba(6, 182, 212, 0.18);
    border-color: var(--bgm-accent);
  }}
  .bgm-icon-animated {{
    display: flex;
    gap: 2px;
    align-items: flex-end;
    height: 14px;
    width: 14px;
  }}
  .bgm-bar {{
    width: 3px;
    background: var(--bgm-accent);
    border-radius: 2px;
    animation: equalizer 1.2s infinite ease-in-out;
  }}
  .bgm-bar:nth-child(1) {{ height: 60%; animation-delay: 0.1s; }}
  .bgm-bar:nth-child(2) {{ height: 100%; animation-delay: 0.3s; }}
  .bgm-bar:nth-child(3) {{ height: 40%; animation-delay: 0.2s; }}
  .bgm-bar.paused {{ animation-play-state: paused; height: 30% !important; }}
  @keyframes equalizer {{
    0%, 100% {{ height: 30%; }}
    50% {{ height: 100%; }}
  }}
  .bgm-widget-title {{
    font-size: 12px;
    font-weight: 600;
    color: #e2e8f0;
    max-width: 160px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .bgm-widget-btn {{
    background: none;
    border: none;
    color: var(--bgm-accent);
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    padding: 2px;
  }}

  .btn-random {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-random:hover {{
    border-color: var(--accent);
    color: var(--accent-light);
    box-shadow: 0 0 12px var(--accent-glow);
  }}

  /* Filter Toolbar */
  .toolbar-container {{
    max-width: 1720px;
    margin: 14px auto 0 auto;
    padding: 0 28px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .filters-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .filter-group-label {{
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin-right: 4px;
  }}
  .filter-chip {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }}
  .filter-chip:hover {{
    border-color: var(--border-hover);
    background: var(--bg-card);
  }}
  .filter-chip.active {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    box-shadow: 0 0 12px var(--accent-glow);
  }}
  .filter-chip.hcg-chip.active {{
    background: var(--hcg-accent);
    border-color: var(--hcg-accent);
    box-shadow: 0 0 12px rgba(255, 51, 102, 0.4);
  }}
  .filter-chip.cg-chip.active {{
    background: var(--cg-accent);
    border-color: var(--cg-accent);
    box-shadow: 0 0 12px rgba(139, 92, 246, 0.4);
  }}
  .filter-chip.voice-chip.active {{
    background: var(--voice-accent);
    border-color: var(--voice-accent);
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.4);
  }}
  .filter-chip.gif-chip.active {{
    background: var(--gif-accent);
    border-color: var(--gif-accent);
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
  }}

  /* Character Dropdown & Sort */
  .select-styled {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    outline: none;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .select-styled:hover, .select-styled:focus {{
    border-color: var(--accent);
  }}

  .view-density-group {{
    margin-left: auto;
    display: flex;
    align-items: center;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2px;
    gap: 2px;
  }}
  .density-btn {{
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .density-btn.active {{
    background: var(--bg-card-hover);
    color: #fff;
    font-weight: 600;
  }}

  /* Main Grid */
  main {{
    max-width: 1720px;
    width: 100%;
    margin: 0 auto;
    padding: 20px 28px 80px 28px;
    flex: 1;
  }}

  .stats-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 16px;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 22px;
  }}
  .grid.compact {{
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 14px;
  }}
  .grid.large {{
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 28px;
  }}

  /* Cards */
  .card {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.22s, border-color 0.22s;
    display: flex;
    flex-direction: column;
    position: relative;
    contain: content;
  }}
  .card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 16px 36px rgba(0,0,0,0.6);
    border-color: var(--border-hover);
  }}
  .card-hcg:hover {{
    border-color: var(--hcg-accent);
    box-shadow: 0 10px 30px rgba(255, 51, 102, 0.28);
  }}
  .card-cg:hover {{
    border-color: var(--cg-accent);
    box-shadow: 0 10px 30px rgba(139, 92, 246, 0.28);
  }}

  .card-media {{
    width: 100%;
    aspect-ratio: 4 / 5;
    background: #06090e;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .card-media img {{
    width: 100%;
    height: 100%;
    object-fit: contain;
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .card:hover .card-media img {{
    transform: scale(1.05);
  }}

  .badge-category {{
    position: absolute;
    top: 10px;
    left: 10px;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
    backdrop-filter: blur(6px);
  }}
  .badge-category.hcg {{
    background: rgba(225, 29, 72, 0.85);
    color: #fff;
    border: 1px solid rgba(244, 63, 94, 0.4);
  }}
  .badge-category.cg {{
    background: rgba(99, 102, 241, 0.85);
    color: #fff;
    border: 1px solid rgba(129, 140, 248, 0.4);
  }}

  .card-top-right-badges {{
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: flex-end;
  }}
  .badge-pill-micro {{
    background: rgba(10, 13, 20, 0.85);
    backdrop-filter: blur(4px);
    color: #cbd5e1;
    border: 1px solid var(--border);
    padding: 3px 7px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }}
  .badge-pill-micro.voice {{
    border-color: rgba(245, 158, 11, 0.4);
    color: #fbbf24;
  }}

  .card-quick-voice-btn {{
    position: absolute;
    bottom: 10px;
    right: 10px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fbbf24;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    opacity: 0.9;
    transition: all 0.2s;
    backdrop-filter: blur(6px);
  }}
  .card-quick-voice-btn:hover {{
    transform: scale(1.15);
    background: var(--voice-accent);
    color: #000;
  }}

  .card-body {{
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .card-title {{
    font-size: 15px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .card-stem {{
    font-size: 11px;
    color: var(--text-muted);
    font-family: monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .card-pills {{
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    margin-top: 4px;
  }}
  .pill {{
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 12px;
    background: var(--bg-card);
    color: var(--text-muted);
    border: 1px solid var(--border);
  }}
  .pill.animated {{
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border-color: rgba(52, 211, 153, 0.3);
  }}
  .pill.has-story {{
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border-color: rgba(251, 191, 36, 0.3);
  }}
  .pill.has-voice {{
    background: rgba(6, 182, 212, 0.15);
    color: #22d3ee;
    border-color: rgba(6, 182, 212, 0.3);
  }}

  /* Modal Experience */
  .modal-overlay {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.88);
    backdrop-filter: blur(10px);
    z-index: 1000;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .modal-overlay.active {{
    display: flex;
  }}

  .modal {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    width: 96vw;
    max-width: 1540px;
    height: 92vh;
    max-height: 94vh;
    display: flex;
    overflow: hidden;
    box-shadow: 0 24px 60px rgba(0,0,0,0.9);
    position: relative;
  }}

  /* Modal Left: Stage */
  .modal-preview {{
    flex: 1.45;
    background: #06090e;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 16px;
    min-height: 520px;
    overflow: hidden;
    transition: background 0.3s;
  }}
  .modal-preview.bg-navy {{ background: #0d1527; }}
  .modal-preview.bg-white {{ background: #ffffff; }}
  .modal-preview.bg-grid {{
    background-color: #0a0d14;
    background-image: linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
    background-size: 24px 24px;
  }}

  .stage-viewport {{
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    transform-origin: center center;
    transition: transform 0.15s ease-out;
  }}

  #spinePlayerContainer {{
    width: 100%;
    height: 100%;
    min-height: 500px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }}
  .spine-player {{
    width: 100% !important;
    height: 100% !important;
    background: transparent !important;
    border-radius: 8px;
  }}
  .modal-preview img, .modal-preview canvas {{
    max-width: 100%;
    max-height: 76vh;
    object-fit: contain;
  }}

  /* Stage Top Toolbar */
  .stage-top-bar {{
    position: absolute;
    top: 14px;
    left: 14px;
    right: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 20;
    pointer-events: none;
  }}
  .stage-ctrl-group {{
    display: flex;
    gap: 6px;
    background: rgba(10, 14, 22, 0.85);
    border: 1px solid var(--border);
    padding: 4px 8px;
    border-radius: 20px;
    backdrop-filter: blur(8px);
    pointer-events: auto;
  }}
  .stage-icon-btn {{
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 4px;
  }}
  .stage-icon-btn:hover {{
    color: #fff;
    background: rgba(255,255,255,0.08);
  }}

  /* Stage Bottom Speed Bar */
  .speed-bar {{
    position: absolute;
    bottom: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(10, 14, 22, 0.9);
    padding: 6px 16px;
    border-radius: 24px;
    border: 1px solid var(--border);
    backdrop-filter: blur(8px);
    z-index: 20;
  }}
  .speed-label {{
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-right: 4px;
  }}
  .speed-btn {{
    background: transparent;
    border: 1px solid transparent;
    color: #94a3b8;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.15s;
  }}
  .speed-btn:hover {{
    color: #fff;
    background: rgba(255, 255, 255, 0.08);
  }}
  .speed-btn.active {{
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    font-weight: 600;
  }}

  /* Modal Right: Details & Tabs */
  .modal-details {{
    flex: 1.1;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
    background: var(--bg-surface);
    overflow: hidden;
  }}

  .modal-header {{
    padding: 20px 24px 16px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .modal-title-wrap {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .modal-title {{
    font-size: 20px;
    font-weight: 700;
    color: #fff;
  }}
  .modal-meta-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }}
  .modal-stem {{
    color: var(--text-muted);
    font-family: monospace;
    font-size: 12px;
  }}
  .modal-nav-group {{
    display: flex;
    gap: 6px;
    align-items: center;
  }}
  .modal-nav-btn {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-muted);
    width: 32px;
    height: 32px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }}
  .modal-nav-btn:hover {{
    color: #fff;
    border-color: var(--accent);
  }}
  .modal-close {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 20px;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    margin-left: 6px;
  }}
  .modal-close:hover {{
    color: #fff;
    background: var(--accent);
  }}

  /* Modal Tabs */
  .modal-tabs {{
    display: flex;
    border-bottom: 1px solid var(--border);
    background: rgba(10, 14, 22, 0.4);
    padding: 0 16px;
  }}
  .tab-btn {{
    background: none;
    border: none;
    color: var(--text-muted);
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .tab-btn:hover {{
    color: #fff;
  }}
  .tab-btn.active {{
    color: var(--accent-light);
    border-bottom-color: var(--accent);
  }}
  .tab-badge {{
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    background: var(--bg-card);
    border: 1px solid var(--border);
  }}

  .modal-tab-content {{
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px;
    display: none;
  }}
  .modal-tab-content.active {{
    display: block;
  }}

  /* Animations Tab Grid */
  .anim-grid {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }}
  .anim-btn {{
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .anim-btn:hover, .anim-btn.active {{
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }}
  .anim-btn.live-spine {{
    border-color: rgba(99, 102, 241, 0.4);
    color: #c7d2fe;
  }}
  .anim-btn.live-spine:hover, .anim-btn.live-spine.active {{
    background: #4f46e5;
    color: #fff;
    border-color: #6366f1;
  }}
  .anim-btn.gif-ready {{
    border-color: rgba(74, 222, 128, 0.35);
    color: #4ade80;
  }}
  .anim-btn.gif-ready.active {{
    background: #16a34a;
    color: #fff;
    border-color: #22c55e;
  }}

  /* Dynamic Composite Skin Deck UI */
  .skin-deck-container {{
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .skin-category-card {{
    background: rgba(21, 29, 45, 0.6);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
  }}
  .skin-category-title {{
    font-size: 13px;
    font-weight: 700;
    color: var(--accent-light);
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }}
  .skin-controls-grid {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .skin-select-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .skin-label {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    min-width: 90px;
  }}
  .skin-select {{
    flex: 1;
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    outline: none;
    cursor: pointer;
    transition: border-color 0.2s;
  }}
  .skin-select:hover, .skin-select:focus {{
    border-color: var(--accent);
  }}
  .skin-toggle-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .skin-toggle-chip {{
    background: var(--bg-surface);
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 5px 12px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
  }}
  .skin-toggle-chip:hover {{
    color: #fff;
    border-color: var(--border-hover);
  }}
  .skin-toggle-chip.active {{
    background: var(--accent);
    color: #fff;
    border-color: var(--accent-light);
    box-shadow: 0 0 10px var(--accent-glow);
  }}
  .skin-reset-btn {{
    background: none;
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .skin-reset-btn:hover {{
    background: var(--bg-card-hover);
    color: #fff;
    border-color: var(--accent);
  }}

  /* Voice Lines List */
  .voice-section-title {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin: 16px 0 8px 0;
    font-weight: 700;
  }}
  .voice-list {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .voice-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    transition: all 0.2s;
  }}
  .voice-card:hover {{
    border-color: var(--voice-accent);
  }}
  .voice-info {{
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .voice-tag {{
    font-size: 11px;
    color: var(--voice-accent);
    font-weight: 600;
  }}
  .voice-en {{
    font-size: 13px;
    color: #f1f5f9;
  }}
  .voice-zh {{
    font-size: 11px;
    color: var(--text-muted);
  }}
  .voice-play-btn {{
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fbbf24;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }}
  .voice-play-btn:hover, .voice-play-btn.playing {{
    background: var(--voice-accent);
    color: #000;
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.5);
  }}

  /* Dialogue Box */
  .story-toolbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }}
  .btn-autoplay {{
    background: rgba(6, 182, 212, 0.15);
    border: 1px solid rgba(6, 182, 212, 0.35);
    color: #22d3ee;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-autoplay:hover, .btn-autoplay.active {{
    background: var(--bgm-accent);
    color: #000;
    box-shadow: 0 0 12px rgba(6, 182, 212, 0.4);
  }}

  .dialogue-box {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    max-height: 480px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .dialogue-card {{
    background: rgba(10, 14, 22, 0.5);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .dialogue-card.highlighted {{
    border-color: var(--accent);
    background: rgba(255, 77, 141, 0.08);
    box-shadow: 0 0 12px rgba(255, 77, 141, 0.2);
  }}
  .dialogue-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .dialogue-speaker {{
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    display: inline-block;
  }}
  .dialogue-speaker.heroine {{
    background: rgba(255, 77, 141, 0.2);
    color: var(--accent-light);
    border: 1px solid rgba(255, 77, 141, 0.35);
  }}
  .dialogue-speaker.master {{
    background: rgba(6, 182, 212, 0.2);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.35);
  }}
  .dialogue-speaker.narrator {{
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
  }}
  .dialogue-text {{
    font-size: 13.5px;
    line-height: 1.6;
    color: #e2e8f0;
  }}
  .dialogue-text-zh {{
    font-size: 11.5px;
    color: var(--text-muted);
    font-style: italic;
  }}

  /* Modal Footer Download Bar */
  .modal-footer {{
    padding: 14px 24px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(10, 14, 22, 0.4);
  }}
  .btn-download {{
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 12px;
    text-decoration: none;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-download:hover {{
    border-color: var(--accent);
    color: var(--accent);
  }}

  /* Floating Global BGM Drawer */
  .bgm-drawer-overlay {{
    position: fixed;
    top: 0;
    right: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(4px);
    z-index: 1200;
    display: none;
  }}
  .bgm-drawer-overlay.active {{
    display: block;
  }}
  .bgm-drawer {{
    position: fixed;
    top: 0;
    right: 0;
    width: 440px;
    max-width: 95vw;
    height: 100vh;
    background: var(--bg-surface);
    border-left: 1px solid var(--border);
    z-index: 1201;
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: -10px 0 30px rgba(0,0,0,0.7);
  }}
  .bgm-drawer.active {{
    transform: translateX(0);
  }}
  .bgm-drawer-header {{
    padding: 18px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .bgm-drawer-title {{
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .bgm-player-panel {{
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    background: rgba(10, 14, 22, 0.6);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .now-playing-title {{
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .now-playing-cat {{
    font-size: 11px;
    color: var(--bgm-accent);
  }}
  .bgm-controls-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .bgm-ctrl-btn {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }}
  .bgm-ctrl-btn:hover {{
    border-color: var(--bgm-accent);
    color: var(--bgm-accent);
  }}
  .bgm-play-main {{
    width: 44px;
    height: 44px;
    background: var(--bgm-accent);
    color: #000;
    border-color: var(--bgm-accent);
    font-size: 16px;
  }}
  .bgm-play-main:hover {{
    transform: scale(1.08);
    box-shadow: 0 0 16px rgba(6, 182, 212, 0.5);
  }}
  .volume-slider-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    color: var(--text-muted);
  }}
  .slider {{
    flex: 1;
    accent-color: var(--bgm-accent);
    cursor: pointer;
  }}

  .bgm-playlist-filter {{
    padding: 12px 20px 8px 20px;
    display: flex;
    gap: 6px;
    overflow-x: auto;
  }}
  .bgm-track-list {{
    flex: 1;
    overflow-y: auto;
    padding: 8px 20px 20px 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .bgm-track-item {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .bgm-track-item:hover, .bgm-track-item.playing {{
    border-color: var(--bgm-accent);
    background: rgba(6, 182, 212, 0.1);
  }}
  .bgm-track-info {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .bgm-track-name {{
    font-size: 13px;
    font-weight: 600;
    color: #fff;
  }}
  .bgm-track-sub {{
    font-size: 11px;
    color: var(--text-muted);
  }}

  /* Toast Notification */
  .toast {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid var(--border);
    color: #fff;
    padding: 12px 20px;
    border-radius: 10px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.6);
    backdrop-filter: blur(10px);
    z-index: 2000;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 10px;
    transform: translateY(100px);
    opacity: 0;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s;
    pointer-events: none;
  }}
  .toast.show {{
    transform: translateY(0);
    opacity: 1;
  }}

  /* Interactive Speech Bubble & Dialogue Box */
  .stage-speech-bubble {{
    position: absolute;
    top: 60px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.94);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(244, 63, 94, 0.45);
    box-shadow: 0 8px 32px rgba(244, 63, 94, 0.3), 0 4px 12px rgba(0,0,0,0.5);
    border-radius: 14px;
    padding: 10px 18px;
    color: #fff;
    font-size: 13.5px;
    font-weight: 500;
    max-width: 82%;
    z-index: 40;
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: none;
    animation: bubblePop 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }}
  @keyframes bubblePop {{
    0% {{ opacity: 0; transform: translateX(-50%) translateY(10px) scale(0.95); }}
    100% {{ opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }}
  }}
  .speech-bubble-icon {{ font-size: 15px; }}

  /* Visual Novel Floating Stage Dialogue Bar */
  .stage-vn-dialogue {{
    position: absolute;
    bottom: 30px;
    left: 20px;
    right: 20px;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.94) 0%, rgba(10, 15, 30, 0.98) 100%);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 14px;
    padding: 12px 18px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.7), 0 0 25px rgba(99, 102, 241, 0.2);
    z-index: 35;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }}
  .stage-vn-dialogue.minimized .vn-body {{ display: none; }}
  .stage-vn-dialogue.minimized {{ bottom: 30px; padding: 8px 14px; }}
  .vn-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }}
  .vn-speaker-tag {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .vn-speaker-name {{
    font-size: 12px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .vn-speaker-name.heroine {{
    background: linear-gradient(135deg, rgba(244, 63, 94, 0.25), rgba(236, 72, 153, 0.35));
    border: 1px solid rgba(244, 63, 94, 0.5);
    color: #fda4af;
  }}
  .vn-speaker-name.master {{
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.25), rgba(59, 130, 246, 0.35));
    border: 1px solid rgba(6, 182, 212, 0.5);
    color: #67e8f9;
  }}
  .vn-speaker-name.narrator {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #94a3b8;
  }}
  .vn-anim-badge {{
    font-size: 11px;
    color: #a5b4fc;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
  }}
  .vn-voice-wave {{
    display: inline-flex;
    align-items: center;
    gap: 2px;
    height: 12px;
  }}
  .vn-voice-wave span {{
    width: 2.5px;
    height: 100%;
    background: var(--voice-accent);
    border-radius: 2px;
    animation: waveBounce 0.8s infinite ease-in-out;
  }}
  .vn-voice-wave span:nth-child(2) {{ animation-delay: 0.2s; }}
  .vn-voice-wave span:nth-child(3) {{ animation-delay: 0.4s; }}
  @keyframes waveBounce {{
    0%, 100% {{ height: 30%; }}
    50% {{ height: 100%; }}
  }}
  .vn-actions {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .vn-btn {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--text-primary);
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
  }}
  .vn-btn:hover {{
    background: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.3);
  }}
  .vn-btn.active {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    box-shadow: 0 0 12px rgba(244, 63, 94, 0.4);
  }}
  .vn-counter {{
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    padding: 0 4px;
  }}
  .vn-body {{
    cursor: pointer;
    user-select: none;
    padding: 6px 0 2px;
  }}
  .vn-text-en {{
    font-size: 14.5px;
    line-height: 1.45;
    color: #f8fafc;
    margin-bottom: 3px;
    font-weight: 500;
  }}
  .vn-text-zh {{
    font-size: 12px;
    line-height: 1.4;
    color: #94a3b8;
    font-style: italic;
  }}
  .game-audio-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
  }}
  .game-audio-pill:hover {{
    background: rgba(16, 185, 129, 0.25);
  }}
  .game-audio-pill.muted {{
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #f87171;
  }}

  /* H-Scene Quick Phase Jump Bar */
  .stage-phase-bar {{
    position: absolute;
    bottom: 140px;
    left: 20px;
    right: 20px;
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 6px 10px;
    background: rgba(10, 15, 30, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    backdrop-filter: blur(12px);
    z-index: 34;
    scrollbar-width: none;
  }}
  .stage-phase-bar::-webkit-scrollbar {{ display: none; }}
  .phase-pill {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #e2e8f0;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    align-items: center;
    gap: 5px;
  }}
  .phase-pill:hover {{
    background: rgba(244, 63, 94, 0.25);
    border-color: rgba(244, 63, 94, 0.5);
    color: #fda4af;
    transform: translateY(-1px);
  }}
  .phase-pill.active {{
    background: linear-gradient(135deg, rgba(244, 63, 94, 0.4), rgba(236, 72, 153, 0.5));
    border-color: rgba(244, 63, 94, 0.8);
    color: #fff;
    box-shadow: 0 0 12px rgba(244, 63, 94, 0.4);
  }}

  /* Cinema Mode */
  .modal-preview.cinema-mode .stage-vn-dialogue,
  .modal-preview.cinema-mode .stage-top-bar,
  .modal-preview.cinema-mode .stage-phase-bar,
  .modal-preview.cinema-mode .speed-bar,
  .modal-preview.cinema-mode .stage-speech-bubble {{
    opacity: 0 !important;
    pointer-events: none !important;
    transition: opacity 0.25s ease;
  }}
  .stage-cinema-exit-btn {{
    position: absolute;
    top: 18px;
    right: 18px;
    z-index: 60;
    background: rgba(10, 15, 30, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #fff;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }}
  .stage-cinema-exit-btn:hover {{
    background: rgba(244, 63, 94, 0.4);
    border-color: rgba(244, 63, 94, 0.8);
  }}
</style>
</head>
<body>

<header>
  <div class="header-container">
    <div class="brand" onclick="window.scrollTo({{ top: 0, behavior: 'smooth' }})">
      <span class="brand-logo">🌸</span>
      <div>
        <div class="brand-title">
          CherryTale Datamine
          <span class="brand-badge">Audio & UX Edition</span>
        </div>
        <div class="brand-subtitle">
          {len(models_data)} Models ({total_hcg} H-Scenes • {total_cg} CGs) • {total_anims:,} Spine Anims • 90 BGM Tracks • Voiced English Dialogue
        </div>
      </div>
    </div>

    <div class="header-actions">
      <!-- Mini BGM Header Widget -->
      <div class="bgm-header-widget" onclick="toggleBgmDrawer()">
        <div class="bgm-icon-animated" id="headerBgmEqualizer">
          <div class="bgm-bar paused"></div>
          <div class="bgm-bar paused"></div>
          <div class="bgm-bar paused"></div>
        </div>
        <span class="bgm-widget-title" id="headerBgmTitle">CherryTale BGM (90 Tracks)</span>
        <button class="bgm-widget-btn" onclick="event.stopPropagation(); toggleBgmPlay()" title="Play/Pause BGM" id="headerBgmPlayBtn">▶</button>
      </div>

      <!-- Random Model Button -->
      <button class="btn-random" onclick="openRandomModel()" title="Explore a random character or scene">
        🎲 Surprise Me
      </button>

      <!-- Global Search -->
      <div class="search-bar">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input" placeholder="Search character, code, animation..." oninput="handleSearch()">
        <button class="search-clear" id="searchClearBtn" onclick="clearSearch()">&times;</button>
        <span class="search-kbd">/</span>
      </div>
    </div>
  </div>
</header>

<div class="toolbar-container">
  <div class="filters-row">
    <span class="filter-group-label">Category:</span>
    <button class="filter-chip active" onclick="setFilter('all', this)">All ({len(models_data)})</button>
    <button class="filter-chip hcg-chip" onclick="setFilter('hcg', this)">🔥 H-Scenes ({total_hcg})</button>
    <button class="filter-chip cg-chip" onclick="setFilter('cg', this)">✨ Character CGs ({total_cg})</button>
    <button class="filter-chip voice-chip" onclick="setFilter('voice', this)">🔊 Voiced Models ({total_voiced})</button>
    <button class="filter-chip gif-chip" onclick="setFilter('animated', this)">🎬 Pre-rendered GIFs ({total_gifs})</button>

    <span class="filter-group-label" style="margin-left: 12px;">Sort:</span>
    <select class="select-styled" id="sortSelect" onchange="handleSortChange(this.value)">
      <option value="default">Default Order</option>
      <option value="name_asc">Name (A → Z)</option>
      <option value="name_desc">Name (Z → A)</option>
      <option value="anims_desc">Most Animations</option>
      <option value="gifs_desc">Most GIFs</option>
      <option value="hcg_first">H-Scenes First</option>
      <option value="cg_first">Character CGs First</option>
    </select>

    <div class="view-density-group">
      <button class="density-btn" onclick="setDensity('compact', this)">Compact</button>
      <button class="density-btn active" onclick="setDensity('standard', this)">Standard</button>
      <button class="density-btn" onclick="setDensity('large', this)">Large</button>
    </div>
  </div>

  <div class="filters-row">
    <span class="filter-group-label">Characters:</span>
    <button class="filter-chip" onclick="setFilter('Cinderella', this)">Cinderella</button>
    <button class="filter-chip" onclick="setFilter('Gretel', this)">Gretel</button>
    <button class="filter-chip" onclick="setFilter('Aladdin', this)">Aladdin</button>
    <button class="filter-chip" onclick="setFilter('Alice', this)">Alice</button>
    <button class="filter-chip" onclick="setFilter('Dracula', this)">Dracula</button>
    <button class="filter-chip" onclick="setFilter('Snow White', this)">Snow White</button>
    <button class="filter-chip" onclick="setFilter('Red Riding Hood', this)">Red Riding Hood</button>
    <button class="filter-chip" onclick="setFilter('Belle', this)">Belle</button>
    <button class="filter-chip" onclick="setFilter('Arthur', this)">Arthur</button>

    <select class="select-styled" id="charSelect" onchange="handleCharSelect(this.value)">
      <option value="">All 60+ Characters...</option>
      {"".join(f'<option value="{name}">{name} ({cnt})</option>' for name, cnt in sorted_char_options)}
    </select>
  </div>
</div>

<main>
  <div class="stats-bar">
    <span id="gridStats">Showing {len(models_data)} models</span>
    <span id="activeFilterBadge" style="color: var(--accent-light);"></span>
  </div>
  <div class="grid" id="charactersGrid"></div>
</main>

<!-- Detail Modal -->
<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
  <div class="modal" onclick="event.stopPropagation()">
    <!-- Left: Visual Stage -->
    <div class="modal-preview" id="modalPreviewStage">
      <!-- Stage Top Toolbar -->
      <div class="stage-top-bar">
        <div class="stage-ctrl-group">
          <button class="stage-icon-btn" onclick="setStageBg('black')" title="Obsidian Black">🖤</button>
          <button class="stage-icon-btn" onclick="setStageBg('navy')" title="Studio Navy">🔷</button>
          <button class="stage-icon-btn" onclick="setStageBg('grid')" title="Transparent Grid">🏁</button>
          <button class="stage-icon-btn" onclick="setStageBg('white')" title="Spotlight White">⚪</button>
        </div>
        <div class="stage-ctrl-group">
          <button id="stageAudioToggleBtn" class="game-audio-pill" onclick="toggleGameAudio()" title="In-Game Master Audio: ON / MUTED">🔊 Auto Audio: ON</button>
          <button id="stageSfxToggleBtn" class="stage-icon-btn" onclick="toggleSfxAudio()" title="H-Scene Sound Effects (Thrusting & Splashes)">💦 SFX: ON</button>
          <button id="stageCinemaBtn" class="stage-icon-btn" onclick="toggleCinemaMode()" title="Cinema Mode (Hide UI)">👁 Cinema</button>
          <button id="stageCensorBtn" class="stage-icon-btn" onclick="toggleCensorship()" title="Toggle Censor Layers">🛡 Censor: OFF</button>
        </div>
        <div class="stage-ctrl-group">
          <button class="stage-icon-btn" onclick="zoomStage(0.2)" title="Zoom In">🔍+</button>
          <button class="stage-icon-btn" onclick="zoomStage(-0.2)" title="Zoom Out">🔍-</button>
          <button class="stage-icon-btn" onclick="resetZoom()" title="Reset 100%">100%</button>
          <button class="stage-icon-btn" onclick="toggleFullscreen()" title="Fullscreen Stage">⛶</button>
        </div>
      </div>

      <button id="stageCinemaExitBtn" class="stage-cinema-exit-btn" onclick="toggleCinemaMode()" style="display:none;">✕ Exit Cinema Mode</button>

      <div class="stage-viewport" id="stageViewport">
        <div id="spinePlayerContainer" style="display:none;"></div>
        <canvas id="modalCanvas" style="display:none; cursor:pointer;" title="Click to pause/resume" onclick="togglePause()"></canvas>
        <img id="modalImg" src="" alt="Preview">
      </div>

      <!-- Stage Touch Speech Bubble -->
      <div id="stageSpeechBubble" class="stage-speech-bubble" style="display:none;">
        <span class="speech-bubble-icon">💬</span>
        <span id="speechBubbleText" class="speech-bubble-text">...</span>
      </div>

      <!-- Stage H-Scene Quick Phase Jump Bar -->
      <div id="stagePhaseBar" class="stage-phase-bar" style="display:none;"></div>

      <!-- Stage Visual Novel Floating Dialogue Bar -->
      <div id="stageDialogueBox" class="stage-vn-dialogue" style="display:none;">
        <div class="vn-header">
          <div class="vn-speaker-tag">
            <span id="vnSpeakerName" class="vn-speaker-name heroine">Heroine</span>
            <span id="vnAnimBadge" class="vn-anim-badge" style="display:none;">🎬 Idle</span>
            <div id="vnVoiceWave" class="vn-voice-wave" style="display:none;">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div class="vn-actions">
            <button id="vnAutoBtn" class="vn-btn active" onclick="toggleStoryAutoPlay(event)" title="Toggle Auto-Play">▶ AUTO</button>
            <button class="vn-btn" onclick="prevStoryLine(event)" title="Previous Line">⏮</button>
            <button class="vn-btn" onclick="nextStoryLine(event)" title="Next Line">⏭</button>
            <span id="vnLineCounter" class="vn-counter">1 / 28</span>
            <button class="vn-btn min-btn" onclick="toggleVnMinimize(event)" title="Minimize / Expand">▼</button>
          </div>
        </div>
        <div class="vn-body" onclick="advanceStoryOnClick(event)">
          <div id="vnTextEn" class="vn-text-en">Dialogue text...</div>
          <div id="vnTextZh" class="vn-text-zh">原文對白...</div>
        </div>
      </div>

      <!-- Stage Speed Controls (Spine Live Speed & Media) -->
      <div id="speedControls" class="speed-bar" style="display:none;">
        <span class="speed-label">Speed:</span>
        <button class="speed-btn" onclick="setSpeed(0.5, this)">0.5x</button>
        <button class="speed-btn active" onclick="setSpeed(1.0, this)">1.0x</button>
        <button class="speed-btn" onclick="setSpeed(1.5, this)">1.5x</button>
        <button class="speed-btn" onclick="setSpeed(2.0, this)">2.0x</button>
        <button class="speed-btn" id="pauseBtn" onclick="togglePause()" style="margin-left: 6px; border: 1px solid var(--border);">⏸ Pause</button>
      </div>
    </div>

    <!-- Right: Multi-Tab Interactive Deck -->
    <div class="modal-details">
      <div class="modal-header">
        <div class="modal-title-wrap">
          <div class="modal-title" id="modalTitle"></div>
          <div class="modal-meta-row">
            <span class="modal-stem" id="modalStem"></span>
            <span id="modalSceneBgmBadge" style="display:none; cursor:pointer; font-size: 11px; background: rgba(6,182,212,0.15); color: #22d3ee; border: 1px solid rgba(6,182,212,0.3); padding: 1px 7px; border-radius: 10px;" onclick="playCurrentSceneBgm()">🎵 Play Scene BGM</span>
          </div>
        </div>
        <div class="modal-nav-group">
          <button class="modal-nav-btn" onclick="navigateModal(-1)" title="Previous model (← key)">◀</button>
          <button class="modal-nav-btn" onclick="navigateModal(1)" title="Next model (→ key)">▶</button>
          <button class="modal-close" onclick="closeModal()">&times;</button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="modal-tabs">
        <button class="tab-btn active" onclick="switchModalTab('tabAnims', this)">
          ⚡ Animations <span class="tab-badge" id="modalAnimTabBadge">0</span>
        </button>
        <button class="tab-btn" onclick="switchModalTab('tabSkins', this)">
          👗 Expression & Skins <span class="tab-badge" id="modalSkinsTabBadge">0</span>
        </button>
        <button class="tab-btn" onclick="switchModalTab('tabVoices', this)">
          🎙 Voice Lines <span class="tab-badge" id="modalVoiceTabBadge">0</span>
        </button>
        <button class="tab-btn" onclick="switchModalTab('tabStory', this)">
          📖 English Story <span class="tab-badge" id="modalStoryTabBadge">0</span>
        </button>
        <button class="tab-btn" onclick="switchModalTab('tabInfo', this)">
          ℹ️ Model Info
        </button>
      </div>

      <!-- Tab 1: Animations -->
      <div class="modal-tab-content active" id="tabAnims">
        <div class="anim-grid" id="modalAnimGrid"></div>
      </div>

      <!-- Tab: Dynamic Composite Skins & Expressions -->
      <div class="modal-tab-content" id="tabSkins">
        <div id="skinDeckContainer" class="skin-deck-container">
          <div style="color: var(--text-muted); font-size: 13px; font-style: italic;">Select a Spine model to customize facial expressions, bodily fluids, and overlays.</div>
        </div>
      </div>

      <!-- Tab 2: Voices -->
      <div class="modal-tab-content" id="tabVoices">
        <div class="voice-section-title">Heroine Touch & Interaction Voices</div>
        <div class="voice-list" id="modalTouchVoices"></div>

        <div class="voice-section-title" style="margin-top: 20px;">Role & Intimacy Dialogues</div>
        <div class="voice-list" id="modalRoleVoices"></div>
      </div>

      <!-- Tab 3: Story & Dialogue -->
      <div class="modal-tab-content" id="tabStory">
        <div class="story-toolbar">
          <button class="btn-autoplay" id="autoPlayStoryBtn" onclick="toggleStoryAutoPlay()">
            ▶ Auto-Play Story with Voices
          </button>
          <span style="font-size: 11px; color: var(--text-muted);" id="storyLineCounter"></span>
        </div>
        <div class="dialogue-box" id="modalDialogues"></div>
      </div>

      <!-- Tab 4: Model Info -->
      <div class="modal-tab-content" id="tabInfo">
        <div style="display:flex; flex-direction:column; gap:12px; font-size:13px; color:#cbd5e1;">
          <div><strong>Model Code:</strong> <span id="infoStem" style="font-family:monospace; color:var(--accent-light);"></span></div>
          <div><strong>Category:</strong> <span id="infoCategory"></span></div>
          <div><strong>Total Spine Animations:</strong> <span id="infoAnims"></span></div>
          <div><strong>WebGL Render Engine:</strong> Spine 4.0 Runtime (Hardware GPU Accelerated)</div>
          <div><strong>Assets Decryption:</strong> 3-Point Mirror Swap + Version Transform Verified</div>
          <div style="margin-top: 10px;">
            <a id="skelDownloadLink" href="#" class="btn-download" download>💾 Download .skel</a>
            <a id="atlasDownloadLink" href="#" class="btn-download" download style="margin-left: 8px;">💾 Download .atlas</a>
          </div>
        </div>
      </div>

      <!-- Footer Action Links -->
      <div class="modal-footer">
        <a id="modalDownloadImg" href="#" download class="btn-download">💾 Download Media</a>
        <span style="font-size: 11px; color: var(--text-muted);">Use ← / → keys to switch models</span>
      </div>
    </div>
  </div>
</div>

<!-- Floating BGM Drawer -->
<div class="bgm-drawer-overlay" id="bgmDrawerOverlay" onclick="toggleBgmDrawer()"></div>
<div class="bgm-drawer" id="bgmDrawer">
  <div class="bgm-drawer-header">
    <div class="bgm-drawer-title">
      <span>🎵</span> CherryTale Original Soundtrack
    </div>
    <button class="modal-close" onclick="toggleBgmDrawer()">&times;</button>
  </div>

  <div class="bgm-player-panel">
    <div>
      <div class="now-playing-title" id="drawerNowPlayingTitle">Select a track to play</div>
      <div class="now-playing-cat" id="drawerNowPlayingCat">CherryTale OST Collection</div>
    </div>
    <div class="bgm-controls-row">
      <button class="bgm-ctrl-btn" onclick="playPrevBgm()" title="Previous Track">⏮</button>
      <button class="bgm-ctrl-btn bgm-play-main" onclick="toggleBgmPlay()" title="Play / Pause" id="drawerPlayBtn">▶</button>
      <button class="bgm-ctrl-btn" onclick="playNextBgm()" title="Next Track">⏭</button>
      <button class="bgm-ctrl-btn" onclick="toggleBgmLoop()" title="Loop Single Track" id="drawerLoopBtn">🔁</button>
    </div>
    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin: 12px 0 6px; font-weight: 700;">Audio Mixer & Volume</div>
    <div class="volume-slider-row" style="margin-bottom: 6px;">
      <span style="font-size:12px; width:75px; color:#a5b4fc;">🎵 BGM</span>
      <input type="range" class="slider" min="0" max="1" step="0.05" id="bgmVolumeSlider" value="0.35" oninput="setBgmVolume(this.value)">
    </div>
    <div class="volume-slider-row" style="margin-bottom: 6px;">
      <span style="font-size:12px; width:75px; color:#f472b6;">🎙 Voice</span>
      <input type="range" class="slider" min="0" max="1" step="0.05" id="voiceVolumeSlider" value="0.85" oninput="setVoiceVolume(this.value)">
    </div>
    <div class="volume-slider-row">
      <span style="font-size:12px; width:75px; color:#38bdf8;">💦 SFX</span>
      <input type="range" class="slider" min="0" max="1" step="0.05" id="sfxVolumeSlider" value="0.70" oninput="setSfxVolume(this.value)">
    </div>
  </div>

  <div class="bgm-playlist-filter">
    <button class="filter-chip active" onclick="filterBgmCatalog('all', this)">All (90)</button>
    <button class="filter-chip" onclick="filterBgmCatalog('Anniversary', this)">Anniversary</button>
    <button class="filter-chip" onclick="filterBgmCatalog('Vocal & Theme', this)">Vocal Themes</button>
    <button class="filter-chip" onclick="filterBgmCatalog('H-Scene & Romance', this)">H-Scene & Intimacy</button>
    <button class="filter-chip" onclick="filterBgmCatalog('Battle & Combat', this)">Battle</button>
  </div>

  <div class="bgm-track-list" id="bgmTrackList"></div>
</div>

<!-- Toast Popup -->
<div class="toast" id="toastBox">
  <span id="toastIcon">🎵</span>
  <span id="toastMsg"></span>
</div>

<script>
const models = {json_models};
const bgmCatalog = {json_bgms};

let currentFilter = 'all';
let currentSearch = '';
let currentSort = 'default';
let activeModel = null;
let filteredModels = [];
const CHUNK_SIZE = 40;
let renderedCount = 0;

// Spine & Animation state
let activePlayer = null;
let currentSpineStem = null;
let currentDecoderFrames = [];
let currentFrameIndex = 0;
let animTimeoutId = null;
let isPaused = false;
let currentSpeed = 1.0;
let loadRequestId = 0;
let stageZoom = 1.0;

// Audio System
const bgmAudio = new Audio();
bgmAudio.loop = true;
let currentBgmIndex = -1;
let isBgmLoopSingle = true;

const voiceAudio = new Audio();
let activeVoiceBtn = null;
let isStoryAutoPlaying = false;
let storyAutoPlayIdx = 0;
let gameAudioEnabled = localStorage.getItem('cherry_game_audio') !== 'false';
let sfxAudioEnabled = localStorage.getItem('cherry_sfx_audio') !== 'false';
let touchCycleIdx = 0;
let speechBubbleTimer = null;

let baseBgmVol = parseFloat(localStorage.getItem('cherry_bgm_vol') || '0.35');
let baseVoiceVol = parseFloat(localStorage.getItem('cherry_voice_vol') || '0.85');
let baseSfxVol = parseFloat(localStorage.getItem('cherry_sfx_vol') || '0.70');

// Web Audio API Audio Engine (Zero-Latency Pooling, Sample-Accurate Loops & Ducking)
const AudioEngine = (() => {{
  let ctx = null;
  const bufferCache = new Map();
  let masterGain = null;
  let sfxGain = null;
  let moanGain = null;

  let currentSfxLoop = null; // {{ url, source, gainNode }}
  let currentMoanLoop = null; // {{ url, source, gainNode }}
  const activeOneShots = new Set();
  const MAX_ONE_SHOTS = 12;
  let bgmDuckAnimId = null;

  function init() {{
    if (ctx) {{
      if (ctx.state === 'suspended') {{
        ctx.resume().catch(e => console.warn('AudioContext resume note:', e));
      }}
      return ctx;
    }}
    try {{
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      ctx = new AudioCtx();
      masterGain = ctx.createGain();
      sfxGain = ctx.createGain();
      moanGain = ctx.createGain();

      sfxGain.connect(masterGain);
      moanGain.connect(masterGain);
      masterGain.connect(ctx.destination);

      updateVolumes();
    }} catch(e) {{
      console.warn('AudioContext init error:', e);
    }}
    return ctx;
  }}

  function updateVolumes() {{
    if (!ctx) return;
    const now = ctx.currentTime;
    const sfxV = (gameAudioEnabled && sfxAudioEnabled) ? baseSfxVol : 0;
    if (sfxGain) sfxGain.gain.setValueAtTime(sfxV, now);
    if (moanGain) moanGain.gain.setValueAtTime(Math.max(0, sfxV * 0.85), now);
  }}

  async function loadBuffer(url) {{
    init();
    if (!ctx) return null;
    if (bufferCache.has(url)) return bufferCache.get(url);
    try {{
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
      const arrayBuf = await res.arrayBuffer();
      const decoded = await ctx.decodeAudioData(arrayBuf);
      if (bufferCache.size > 100) {{
        const oldestKey = bufferCache.keys().next().value;
        bufferCache.delete(oldestKey);
      }}
      bufferCache.set(url, decoded);
      return decoded;
    }} catch(e) {{
      console.warn('Audio buffer load failed for ' + url, e);
      return null;
    }}
  }}

  function playOneShot(url, volScale = 1.0, speedScale = 1.0) {{
    if (!gameAudioEnabled || !sfxAudioEnabled || !url) return;
    init();
    if (!ctx) return;
    if (activeOneShots.size >= MAX_ONE_SHOTS) {{
      const oldest = activeOneShots.values().next().value;
      if (oldest) {{
        try {{ oldest.stop(); oldest.disconnect(); }} catch(e) {{}}
        activeOneShots.delete(oldest);
      }}
    }}
    loadBuffer(url).then(buf => {{
      if (!buf || !ctx) return;
      try {{
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.playbackRate.value = Math.max(0.25, Math.min(4.0, (isPaused ? 0 : currentSpeed) * speedScale));
        const gain = ctx.createGain();
        gain.gain.value = Math.max(0, Math.min(1.0, volScale));
        src.connect(gain);
        gain.connect(sfxGain);

        src.onended = () => {{
          activeOneShots.delete(src);
          try {{ src.disconnect(); gain.disconnect(); }} catch(e) {{}}
        }};
        activeOneShots.add(src);
        src.start(0);
      }} catch(err) {{
        console.warn('One-shot play error:', err);
      }}
    }});
  }}

  function setLoop(type, url, vol = 1.0) {{
    init();
    if (!ctx) return;
    const isMoan = (type === 'moan');
    const current = isMoan ? currentMoanLoop : currentSfxLoop;

    if (!url || !sfxAudioEnabled || !gameAudioEnabled) {{
      if (current) {{
        stopLoopWithFade(current);
        if (isMoan) currentMoanLoop = null; else currentSfxLoop = null;
      }}
      return;
    }}

    if (current && current.url === url) {{
      current.gainNode.gain.setValueAtTime(vol, ctx.currentTime);
      current.source.playbackRate.value = isPaused ? 0 : currentSpeed;
      return;
    }}

    if (current) {{
      stopLoopWithFade(current);
      if (isMoan) currentMoanLoop = null; else currentSfxLoop = null;
    }}

    loadBuffer(url).then(buf => {{
      if (!buf || !ctx) return;
      if (!sfxAudioEnabled || !gameAudioEnabled) return;
      try {{
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.loop = true;
        src.playbackRate.value = isPaused ? 0 : currentSpeed;

        const loopGain = ctx.createGain();
        loopGain.gain.setValueAtTime(vol, ctx.currentTime);

        src.connect(loopGain);
        loopGain.connect(isMoan ? moanGain : sfxGain);

        src.start(0);
        const loopRecord = {{ url, source: src, gainNode: loopGain }};
        if (isMoan) currentMoanLoop = loopRecord; else currentSfxLoop = loopRecord;
      }} catch(e) {{
        console.warn('Loop play error:', e);
      }}
    }});
  }}

  function stopLoopWithFade(loopRecord) {{
    if (!loopRecord || !loopRecord.source) return;
    try {{
      const now = ctx ? ctx.currentTime : 0;
      if (ctx && loopRecord.gainNode) {{
        loopRecord.gainNode.gain.setValueAtTime(loopRecord.gainNode.gain.value, now);
        loopRecord.gainNode.gain.linearRampToValueAtTime(0.001, now + 0.03);
      }}
      setTimeout(() => {{
        try {{
          loopRecord.source.stop();
          loopRecord.source.disconnect();
          if (loopRecord.gainNode) loopRecord.gainNode.disconnect();
        }} catch(e) {{}}
      }}, 35);
    }} catch(e) {{
      try {{ loopRecord.source.stop(); loopRecord.source.disconnect(); }} catch(err) {{}}
    }}
  }}

  function stopAllLoops() {{
    if (currentSfxLoop) {{
      stopLoopWithFade(currentSfxLoop);
      currentSfxLoop = null;
    }}
    if (currentMoanLoop) {{
      stopLoopWithFade(currentMoanLoop);
      currentMoanLoop = null;
    }}
    activeOneShots.forEach(src => {{
      try {{ src.stop(); src.disconnect(); }} catch(e) {{}}
    }});
    activeOneShots.clear();
  }}

  function setSpeed(speed) {{
    const s = Math.max(0, Math.min(4.0, speed));
    if (currentSfxLoop && currentSfxLoop.source) {{
      try {{ currentSfxLoop.source.playbackRate.value = s; }} catch(e) {{}}
    }}
    if (currentMoanLoop && currentMoanLoop.source) {{
      try {{ currentMoanLoop.source.playbackRate.value = s; }} catch(e) {{}}
    }}
  }}

  function duckBgm(duck, durationMs = 120) {{
    if (!bgmAudio) return;
    if (!gameAudioEnabled) {{
      bgmAudio.volume = 0;
      return;
    }}
    const targetVol = duck ? Math.max(0.06, baseBgmVol * 0.3) : baseBgmVol;
    if (bgmDuckAnimId) {{
      cancelAnimationFrame(bgmDuckAnimId);
      bgmDuckAnimId = null;
    }}
    const startVol = bgmAudio.volume;
    const startTime = performance.now();

    function ramp() {{
      const elapsed = performance.now() - startTime;
      const progress = Math.min(1.0, elapsed / durationMs);
      const factor = 0.5 - 0.5 * Math.cos(progress * Math.PI);
      bgmAudio.volume = Math.max(0, Math.min(1.0, startVol + (targetVol - startVol) * factor));
      if (progress < 1.0) {{
        bgmDuckAnimId = requestAnimationFrame(ramp);
      }} else {{
        bgmAudio.volume = targetVol;
        bgmDuckAnimId = null;
      }}
    }}
    bgmDuckAnimId = requestAnimationFrame(ramp);
  }}

  function handleSpineEvent(evName) {{
    if (!evName) return;
    const name = evName.toLowerCase();
    if (name.startsWith('se_') || name.startsWith('se-')) {{
      playOneShot(`/audio/se/${{evName}}.wav`, 1.0);
    }} else if (name.startsWith('vic_') || name.startsWith('vic-')) {{
      playOneShot(`/audio/voice/${{evName}}.wav`, 1.0);
    }}
  }}

  function handleCycleComplete(animName, duration) {{
    if (window.onSpineCycleComplete) {{
      window.onSpineCycleComplete(animName, duration);
    }}
  }}

  return {{
    init,
    loadBuffer,
    playOneShot,
    setLoop,
    stopAllLoops,
    setSpeed,
    updateVolumes,
    duckBgm,
    handleSpineEvent,
    handleCycleComplete
  }};
}})();

let isCinemaMode = false;
let isCensored = false;

function toggleCinemaMode() {{
  isCinemaMode = !isCinemaMode;
  const stage = document.getElementById('modalPreviewStage');
  const exitBtn = document.getElementById('stageCinemaExitBtn');
  if (stage) stage.classList.toggle('cinema-mode', isCinemaMode);
  if (exitBtn) exitBtn.style.display = isCinemaMode ? 'flex' : 'none';
  if (isCinemaMode) {{
    showToast('Cinema Mode: UI Hidden. Click or press Esc to exit', '👁');
  }}
}}

function toggleCensorship() {{
  isCensored = !isCensored;
  const btn = document.getElementById('stageCensorBtn');
  if (btn) {{
    btn.textContent = isCensored ? '🛡 Censor: ON' : '🛡 Censor: OFF';
    btn.style.color = isCensored ? '#38bdf8' : 'var(--text-muted)';
  }}
  showToast(isCensored ? 'Censorship Layers: ON' : 'Censorship Layers: OFF (Uncensored)', '🛡');
  if (activePlayer && activePlayer.skeleton) {{
    const skel = activePlayer.skeleton;
    skel.slots.forEach(slot => {{
      const name = (slot.data.name || '').toLowerCase();
      if (/censor|mark|mosaic|fog|light/i.test(name)) {{
        slot.color.a = isCensored ? 1 : 0;
      }}
    }});
  }}
}}

function toggleSfxAudio() {{
  sfxAudioEnabled = !sfxAudioEnabled;
  localStorage.setItem('cherry_sfx_audio', sfxAudioEnabled ? 'true' : 'false');
  updateSfxAudioUI();
  AudioEngine.updateVolumes();
  if (!sfxAudioEnabled) {{
    AudioEngine.stopAllLoops();
    showToast('H-Scene SFX: Muted', '🔇');
  }} else {{
    showToast('H-Scene SFX: Active', '💦');
    if (activeModel && activeModel.dialogues && activeModel.dialogues[storyAutoPlayIdx]) {{
      syncLineSfx(activeModel.dialogues[storyAutoPlayIdx]);
    }}
  }}
}}

function updateSfxAudioUI() {{
  const btn = document.getElementById('stageSfxToggleBtn');
  if (btn) {{
    btn.textContent = sfxAudioEnabled ? '💦 SFX: ON' : '🔇 SFX: OFF';
    btn.style.color = sfxAudioEnabled ? '#38bdf8' : 'var(--text-muted)';
  }}
}}

function setBgmVolume(val) {{
  baseBgmVol = parseFloat(val);
  bgmAudio.volume = gameAudioEnabled ? baseBgmVol : 0;
  localStorage.setItem('cherry_bgm_vol', val);
}}

function setVoiceVolume(val) {{
  baseVoiceVol = parseFloat(val);
  voiceAudio.volume = gameAudioEnabled ? baseVoiceVol : 0;
  localStorage.setItem('cherry_voice_vol', val);
}}

function setSfxVolume(val) {{
  baseSfxVol = parseFloat(val);
  AudioEngine.updateVolumes();
  localStorage.setItem('cherry_sfx_vol', val);
}}

function toggleGameAudio() {{
  gameAudioEnabled = !gameAudioEnabled;
  localStorage.setItem('cherry_game_audio', gameAudioEnabled ? 'true' : 'false');
  updateGameAudioUI();
  updateSfxAudioUI();
  AudioEngine.updateVolumes();
  if (!gameAudioEnabled) {{
    bgmAudio.pause();
    voiceAudio.pause();
    AudioEngine.stopAllLoops();
    updateBgmUI(false);
    showToast('In-Game Audio: Muted', '🔇');
  }} else {{
    setBgmVolume(baseBgmVol);
    setVoiceVolume(baseVoiceVol);
    setSfxVolume(baseSfxVol);
    showToast('In-Game Audio: Active', '🔊');
    if (activeModel && activeModel.default_bgm) {{
      playBgmById(activeModel.default_bgm, true);
    }}
    if (activeModel && activeModel.dialogues && activeModel.dialogues[storyAutoPlayIdx]) {{
      syncLineSfx(activeModel.dialogues[storyAutoPlayIdx]);
    }}
  }}
}}

function updateGameAudioUI() {{
  const pills = document.querySelectorAll('.game-audio-pill');
  pills.forEach(p => {{
    p.classList.toggle('muted', !gameAudioEnabled);
    p.innerHTML = gameAudioEnabled ? '🔊 Auto Audio: ON' : '🔇 Audio: MUTED';
  }});
}}

function duckBgm(duck) {{
  AudioEngine.duckBgm(duck);
}}

function playInteractiveVoice(voiceUrl, label) {{
  if (!gameAudioEnabled || !voiceUrl) return;
  duckBgm(true);
  voiceAudio.src = voiceUrl;
  voiceAudio.play().then(() => {{
    showSpeechBubble(label || 'Voice Reaction');
    voiceAudio.onended = () => {{
      duckBgm(false);
      hideSpeechBubble();
    }};
  }}).catch(e => {{
    duckBgm(false);
    console.warn('Voice play note:', e);
  }});
}}

function showSpeechBubble(text) {{
  const bubble = document.getElementById('stageSpeechBubble');
  const textEl = document.getElementById('speechBubbleText');
  if (!bubble || !textEl || !text) return;
  textEl.textContent = text;
  bubble.style.display = 'flex';
  clearTimeout(speechBubbleTimer);
  speechBubbleTimer = setTimeout(() => {{
    bubble.style.display = 'none';
  }}, 4500);
}}

function hideSpeechBubble() {{
  const bubble = document.getElementById('stageSpeechBubble');
  if (bubble) bubble.style.display = 'none';
}}

// Toast helper
function showToast(msg, icon = '🎵') {{
  const toast = document.getElementById('toastBox');
  document.getElementById('toastIcon').textContent = icon;
  document.getElementById('toastMsg').textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {{ toast.classList.remove('show'); }}, 3200);
}}

// Initialize BGM Player
function initBgm() {{
  bgmAudio.volume = gameAudioEnabled ? baseBgmVol : 0;
  voiceAudio.volume = gameAudioEnabled ? baseVoiceVol : 0;
  AudioEngine.updateVolumes();

  const bgmSlider = document.getElementById('bgmVolumeSlider');
  if (bgmSlider) bgmSlider.value = baseBgmVol;
  const vSlider = document.getElementById('voiceVolumeSlider');
  if (vSlider) vSlider.value = baseVoiceVol;
  const sfxSlider = document.getElementById('sfxVolumeSlider');
  if (sfxSlider) sfxSlider.value = baseSfxVol;

  updateGameAudioUI();
  updateSfxAudioUI();

  bgmAudio.onended = () => {{
    if (!isBgmLoopSingle) playNextBgm();
  }};

  renderBgmList(bgmCatalog);
}}

function renderBgmList(tracks) {{
  const container = document.getElementById('bgmTrackList');
  container.innerHTML = '';
  tracks.forEach((t, idx) => {{
    const item = document.createElement('div');
    item.className = 'bgm-track-item' + (currentBgmIndex >= 0 && bgmCatalog[currentBgmIndex].id === t.id ? ' playing' : '');
    item.onclick = () => playBgmById(t.id);

    item.innerHTML = `
      <div class="bgm-track-info">
        <div class="bgm-track-name">${{t.title}}</div>
        <div class="bgm-track-sub">${{t.category}} • ${{t.size_mb}} MB</div>
      </div>
      <span style="font-size: 14px; color: var(--bgm-accent);">▶</span>
    `;
    container.appendChild(item);
  }});
}}

function filterBgmCatalog(cat, btn) {{
  document.querySelectorAll('.bgm-playlist-filter .filter-chip').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (cat === 'all') {{
    renderBgmList(bgmCatalog);
  }} else {{
    const filtered = bgmCatalog.filter(b => b.category.toLowerCase().includes(cat.toLowerCase()));
    renderBgmList(filtered);
  }}
}}

function playBgmById(trackId, isAuto = false) {{
  if (!trackId) return;
  if (!gameAudioEnabled && isAuto) return;

  const baseVol = parseFloat(localStorage.getItem('cherry_bgm_vol') || '0.35');
  let idx = bgmCatalog.findIndex(b => b.id.toLowerCase() === trackId.toLowerCase());
  if (idx < 0) {{
    idx = bgmCatalog.findIndex(b => b.id.toLowerCase().includes(trackId.toLowerCase()) || trackId.toLowerCase().includes(b.id.toLowerCase()));
  }}

  if (idx >= 0) {{
    const track = bgmCatalog[idx];
    if (bgmAudio.src.includes(track.url) && !bgmAudio.paused) return;
    currentBgmIndex = idx;
    bgmAudio.src = track.url;
    bgmAudio.volume = baseVol;
    bgmAudio.play().then(() => {{
      updateBgmUI(true);
      if (!isAuto) showToast(`Now Playing: ${{track.title}}`, '🎵');
    }}).catch(e => console.warn('BGM auto play note:', e));
  }} else {{
    const cleanId = trackId.replace(/\.wav$/i, '');
    const directUrl = `/audio/bgm/${{cleanId}}`;
    if (bgmAudio.src.includes(directUrl) && !bgmAudio.paused) return;
    bgmAudio.src = directUrl;
    bgmAudio.volume = baseVol;
    bgmAudio.play().then(() => {{
      document.getElementById('headerBgmTitle').textContent = trackId;
      document.getElementById('drawerNowPlayingTitle').textContent = trackId;
      updateBgmUI(true);
    }}).catch(e => console.warn('Direct BGM auto play note:', e));
  }}
}}

function updateBgmUI(isPlaying) {{
  const track = bgmCatalog[currentBgmIndex] || {{ title: 'CherryTale Soundtrack', category: 'Select Track' }};
  document.getElementById('headerBgmTitle').textContent = track.title;
  document.getElementById('drawerNowPlayingTitle').textContent = track.title;
  document.getElementById('drawerNowPlayingCat').textContent = track.category;

  const playBtns = [document.getElementById('headerBgmPlayBtn'), document.getElementById('drawerPlayBtn')];
  playBtns.forEach(b => {{ if (b) b.textContent = isPlaying ? '⏸' : '▶'; }});

  const bars = document.querySelectorAll('#headerBgmEqualizer .bgm-bar');
  bars.forEach(b => {{
    if (isPlaying) b.classList.remove('paused');
    else b.classList.add('paused');
  }});

  document.querySelectorAll('.bgm-track-item').forEach((item, idx) => {{
    item.classList.toggle('playing', bgmCatalog[idx] && bgmCatalog[idx].id === track.id);
  }});
}}

function toggleBgmPlay() {{
  if (!bgmAudio.src || currentBgmIndex < 0) {{
    playBgmById('1st_anniv_1st_anniv');
    return;
  }}
  if (bgmAudio.paused) {{
    bgmAudio.play();
    updateBgmUI(true);
  }} else {{
    bgmAudio.pause();
    updateBgmUI(false);
  }}
}}

function playNextBgm() {{
  if (!bgmCatalog.length) return;
  const nextIdx = (currentBgmIndex + 1) % bgmCatalog.length;
  playBgmById(bgmCatalog[nextIdx].id);
}}

function playPrevBgm() {{
  if (!bgmCatalog.length) return;
  const prevIdx = (currentBgmIndex - 1 + bgmCatalog.length) % bgmCatalog.length;
  playBgmById(bgmCatalog[prevIdx].id);
}}

function toggleBgmLoop() {{
  isBgmLoopSingle = !isBgmLoopSingle;
  bgmAudio.loop = isBgmLoopSingle;
  const loopBtn = document.getElementById('drawerLoopBtn');
  if (loopBtn) {{
    loopBtn.style.color = isBgmLoopSingle ? 'var(--bgm-accent)' : 'var(--text-muted)';
  }}
  showToast(isBgmLoopSingle ? 'Loop: Single Track' : 'Loop: Entire Playlist', '🔁');
}}

function setBgmVolume(val) {{
  bgmAudio.volume = parseFloat(val);
  localStorage.setItem('cherry_bgm_vol', val);
}}

function toggleBgmDrawer() {{
  const drawer = document.getElementById('bgmDrawer');
  const overlay = document.getElementById('bgmDrawerOverlay');
  const isActive = drawer.classList.contains('active');
  drawer.classList.toggle('active', !isActive);
  overlay.classList.toggle('active', !isActive);
}}

// Voice Playback Engine
function playVoiceLine(url, btn) {{
  if (activeVoiceBtn && activeVoiceBtn !== btn) {{
    activeVoiceBtn.classList.remove('playing');
    if (activeVoiceBtn.textContent.includes('⏹')) {{
      activeVoiceBtn.textContent = activeVoiceBtn.textContent.replace('⏹', '▶');
    }}
  }}

  if (voiceAudio.src.endsWith(url) && !voiceAudio.paused) {{
    voiceAudio.pause();
    if (btn) {{
      btn.classList.remove('playing');
      btn.textContent = btn.textContent.replace('⏹', '▶');
    }}
    return;
  }}

  voiceAudio.src = url;
  voiceAudio.volume = 0.85;
  activeVoiceBtn = btn;
  if (btn) {{
    btn.classList.add('playing');
    btn.textContent = btn.textContent.replace('▶', '⏹');
  }}

  voiceAudio.play().catch(e => console.warn('Voice play note:', e));

  voiceAudio.onended = () => {{
    if (btn) {{
      btn.classList.remove('playing');
      btn.textContent = btn.textContent.replace('⏹', '▶');
    }}
    activeVoiceBtn = null;
  }};
}}

function playCardVoice(e, stem) {{
  e.stopPropagation();
  const model = models.find(x => x.stem === stem);
  if (!model) return;
  if (model.greeting_voice) {{
    playVoiceLine(model.greeting_voice, e.currentTarget);
    showToast(`Voice preview: ${{model.name_en}}`, '🎙');
  }} else {{
    loadModelDetails(model).then(() => {{
      let vUrl = null;
      if (model.touch_voices && model.touch_voices.length) {{
        vUrl = model.touch_voices[0].url;
      }} else if (model.role_voices && model.role_voices.length) {{
        vUrl = model.role_voices[0].url;
      }} else if (model.dialogues && model.dialogues.length) {{
        const voiced = model.dialogues.find(d => d.voice_url);
        if (voiced) vUrl = voiced.voice_url;
      }}
      if (vUrl) {{
        playVoiceLine(vUrl, e.currentTarget);
        showToast(`Voice preview: ${{model.name_en}}`, '🎙');
      }}
    }});
  }}
}}

// Grid Rendering & Filtering
function renderGrid() {{
  renderedCount = 0;
  const container = document.getElementById('charactersGrid');
  container.innerHTML = '';

  filteredModels = models.filter(m => {{
    const matchesSearch = !currentSearch || 
      m.stem.toLowerCase().includes(currentSearch) ||
      m.name_en.toLowerCase().includes(currentSearch) ||
      (m.name_zh && m.name_zh.includes(currentSearch)) ||
      m.prefix.toLowerCase().includes(currentSearch);
    
    if (!matchesSearch) return false;
    if (currentFilter === 'all') return true;
    if (currentFilter === 'hcg') return m.is_hcg;
    if (currentFilter === 'cg') return !m.is_hcg;
    if (currentFilter === 'voice') return m.has_voice;
    if (currentFilter === 'animated') return m.gifs.length > 0;
    return m.name_en.toLowerCase().includes(currentFilter.toLowerCase()) || 
           m.stem.toLowerCase().includes(currentFilter.toLowerCase());
  }});

  // Sort
  if (currentSort === 'name_asc') {{
    filteredModels.sort((a, b) => a.name_en.localeCompare(b.name_en));
  }} else if (currentSort === 'name_desc') {{
    filteredModels.sort((a, b) => b.name_en.localeCompare(a.name_en));
  }} else if (currentSort === 'anims_desc') {{
    filteredModels.sort((a, b) => b.animations.length - a.animations.length);
  }} else if (currentSort === 'gifs_desc') {{
    filteredModels.sort((a, b) => b.gifs.length - a.gifs.length);
  }} else if (currentSort === 'hcg_first') {{
    filteredModels.sort((a, b) => (b.is_hcg ? 1 : 0) - (a.is_hcg ? 1 : 0));
  }} else if (currentSort === 'cg_first') {{
    filteredModels.sort((a, b) => (a.is_hcg ? 1 : 0) - (b.is_hcg ? 1 : 0));
  }}

  document.getElementById('gridStats').textContent = `Showing ${{filteredModels.length}} of ${{models.length}} models`;
  renderNextChunk();
}}

function renderNextChunk() {{
  if (renderedCount >= filteredModels.length) return;
  const container = document.getElementById('charactersGrid');
  const slice = filteredModels.slice(renderedCount, renderedCount + CHUNK_SIZE);
  const frag = document.createDocumentFragment();

  slice.forEach(m => {{
    const card = document.createElement('div');
    card.className = 'card ' + (m.is_hcg ? 'card-hcg' : 'card-cg');
    card.onclick = () => openModal(m);

    const displayName = m.name_zh ? `${{m.name_en}} (${{m.name_zh}})` : m.name_en;
    const thumbSrc = m.thumb_url || m.frame0_url;

    card.innerHTML = `
      <div class="card-media">
        <img src="${{thumbSrc}}" alt="${{m.stem}}" loading="lazy" decoding="async">
        <span class="badge-category ${{m.is_hcg ? 'hcg' : 'cg'}}">${{m.is_hcg ? 'H-Scene' : 'Character CG'}}</span>
        <div class="card-top-right-badges">
          <span class="badge-pill-micro">${{m.animations.length}} Anims</span>
          ${{m.has_voice ? '<span class="badge-pill-micro voice">🔊 Voiced</span>' : ''}}
        </div>
        ${{m.has_voice ? `<button class="card-quick-voice-btn" onclick="playCardVoice(event, '${{m.stem}}')" title="Quick Voice Preview">🔊</button>` : ''}}
      </div>
      <div class="card-body">
        <div class="card-title" title="${{displayName}}">${{displayName}}</div>
        <div class="card-stem" title="${{m.stem}}">${{m.stem}}</div>
        <div class="card-pills">
          <span class="pill animated">⚡ 60fps Live</span>
          ${{m.gifs.length ? `<span class="pill animated">${{m.gifs.length}} GIFs</span>` : ''}}
          ${{m.dialogue_count ? `<span class="pill has-story">${{m.dialogue_count}} Lines</span>` : ''}}
          ${{m.has_voice ? '<span class="pill has-voice">🎙 Voice Pack</span>' : ''}}
        </div>
      </div>
    `;
    frag.appendChild(card);
  }});

  container.appendChild(frag);
  renderedCount += slice.length;
}}

window.addEventListener('scroll', () => {{
  if (renderedCount >= filteredModels.length) return;
  if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 800) {{
    renderNextChunk();
  }}
}}, {{ passive: true }});

function handleSearch() {{
  currentSearch = document.getElementById('searchInput').value.trim().toLowerCase();
  document.getElementById('searchClearBtn').style.display = currentSearch ? 'block' : 'none';
  renderGrid();
}}

function clearSearch() {{
  document.getElementById('searchInput').value = '';
  document.getElementById('searchClearBtn').style.display = 'none';
  currentSearch = '';
  renderGrid();
}}

function setFilter(filter, btn) {{
  currentFilter = filter;
  document.querySelectorAll('.filters-row .filter-chip').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.getElementById('charSelect').value = '';
  renderGrid();
}}

function handleCharSelect(val) {{
  if (!val) return;
  currentFilter = val;
  document.querySelectorAll('.filters-row .filter-chip').forEach(b => b.classList.remove('active'));
  renderGrid();
}}

function handleSortChange(val) {{
  currentSort = val;
  renderGrid();
}}

function setDensity(mode, btn) {{
  document.querySelectorAll('.density-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const grid = document.getElementById('charactersGrid');
  grid.classList.remove('compact', 'large');
  if (mode !== 'standard') grid.classList.add(mode);
}}

function openRandomModel() {{
  if (!models.length) return;
  const rand = models[Math.floor(Math.random() * models.length)];
  openModal(rand);
  showToast(`Surprise: Opened ${{rand.name_en}}`, '🎲');
}}

// Stage Controls
function setStageBg(type) {{
  const stage = document.getElementById('modalPreviewStage');
  stage.className = 'modal-preview';
  if (type !== 'black') stage.classList.add('bg-' + type);
}}

function zoomStage(delta) {{
  stageZoom = Math.max(0.6, Math.min(2.5, stageZoom + delta));
  document.getElementById('stageViewport').style.transform = `scale(${{stageZoom}})`;
}}

function resetZoom() {{
  stageZoom = 1.0;
  document.getElementById('stageViewport').style.transform = 'scale(1.0)';
}}

function toggleFullscreen() {{
  const stage = document.getElementById('modalPreviewStage');
  if (!document.fullscreenElement) {{
    stage.requestFullscreen().catch(err => console.warn(err));
  }} else {{
    document.exitFullscreen().catch(err => console.warn(err));
  }}
}}

// Modal Lifecycle & Spine Player
function disposeSpinePlayer() {{
  if (activePlayer) {{
    try {{
      const canvas = activePlayer.canvas || (document.getElementById('spinePlayerContainer')?.querySelector('canvas'));
      if (canvas) {{
        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
        if (gl) {{
          const loseExt = gl.getExtension('WEBGL_lose_context');
          if (loseExt) loseExt.loseContext();
        }}
      }}
      activePlayer.dispose();
    }} catch(e) {{
      console.warn("Dispose SpinePlayer error:", e);
    }}
    activePlayer = null;
  }}
  currentSpineStem = null;
  const container = document.getElementById('spinePlayerContainer');
  if (container) {{
    container.innerHTML = '';
    container.style.display = 'none';
  }}
}}

function stopCurrentAnimation() {{
  if (animTimeoutId) {{
    clearTimeout(animTimeoutId);
    animTimeoutId = null;
  }}
  currentDecoderFrames.forEach(f => {{
    if (f.bitmap && f.bitmap.close) f.bitmap.close();
  }});
  currentDecoderFrames = [];
  currentFrameIndex = 0;
}}

function renderCanvasFrame() {{
  if (!currentDecoderFrames.length) return;
  const canvas = document.getElementById('modalCanvas');
  const ctx = canvas.getContext('2d');
  const frame = currentDecoderFrames[currentFrameIndex];

  if (canvas.width !== frame.bitmap.width || canvas.height !== frame.bitmap.height) {{
    canvas.width = frame.bitmap.width;
    canvas.height = frame.bitmap.height;
  }}
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(frame.bitmap, 0, 0);

  if (!isPaused) {{
    const delay = Math.max(16, (frame.durationMs || 80) / currentSpeed);
    animTimeoutId = setTimeout(() => {{
      currentFrameIndex = (currentFrameIndex + 1) % currentDecoderFrames.length;
      renderCanvasFrame();
    }}, delay);
  }}
}}

function applyCensorship(skeleton) {{
  if (!skeleton) return;
  skeleton.slots.forEach(slot => {{
    const name = (slot.data.name || '').toLowerCase();
    if (/censor|mark|mosaic|fog|light/i.test(name)) {{
      slot.color.a = isCensored ? 1 : 0;
    }}
  }});
}}

function playSpineAnimation(char, animName) {{
  stopCurrentAnimation();
  const modalImg = document.getElementById('modalImg');
  const modalCanvas = document.getElementById('modalCanvas');
  const speedControls = document.getElementById('speedControls');
  const spineContainer = document.getElementById('spinePlayerContainer');

  modalImg.style.display = 'none';
  modalCanvas.style.display = 'none';
  speedControls.style.display = 'flex';
  spineContainer.style.display = 'block';

  if (activePlayer && currentSpineStem === char.stem) {{
    if (!activePlayer.animationState || !activePlayer.skeleton) {{
      activePlayer._pendingAnim = animName;
      return;
    }}
    try {{
      activePlayer.animationState.setAnimation(0, animName, true);
      activePlayer.animationState.timeScale = isPaused ? 0 : currentSpeed;
      activePlayer.skeleton.setSlotsToSetupPose();
      const bgLightSlot = activePlayer.skeleton.findSlot("BG_Light");
      if (bgLightSlot) {{
        bgLightSlot.attachment = null;
        bgLightSlot.color.a = 0;
      }}
      applyCensorship(activePlayer.skeleton);
      return;
    }} catch(e) {{
      console.warn("Direct animation switch note:", e);
      return;
    }}
  }}

  disposeSpinePlayer();
  currentSpineStem = char.stem;
  spineContainer.style.display = 'block';

  try {{
    activePlayer = new spine.SpinePlayer(spineContainer, {{
      skelUrl: `/spines/${{char.stem}}/${{char.stem}}.skel`,
      atlasUrl: `/spines/${{char.stem}}/${{char.stem}}.atlas`,
      animation: animName,
      premultipliedAlpha: false,
      backgroundColor: "#00000000",
      showControls: false,
      viewport: {{ padLeft: "2%", padRight: "2%", padTop: "2%", padBottom: "2%" }},
      success: (player) => {{
        if (player.disposed) return;
        try {{
          if (player.animationState && player.animationState.data) {{
            player.animationState.data.defaultMix = 0.25;
          }}

          setupInitialCompositeSkins(player);
          rebuildCompositeSkin();
          renderSkinDeck(player);

          if (player._pendingAnim) {{
            const targetAnim = player._pendingAnim;
            player._pendingAnim = null;
            player.animationState.setAnimation(0, targetAnim, true);
          }}

          player.animationState.addListener({{
            event: (entry, event) => {{
              if (event && event.data && event.data.name) {{
                AudioEngine.handleSpineEvent(event.data.name);
              }}
            }},
            complete: (entry) => {{
              if (entry && entry.animation) {{
                AudioEngine.handleCycleComplete(entry.animation.name, entry.animation.duration);
              }}
            }}
          }});

          player.animationState.timeScale = isPaused ? 0 : currentSpeed;
          AudioEngine.setSpeed(isPaused ? 0 : currentSpeed);

          if (player.canvas) {{
            let ptDownX = 0, ptDownY = 0, ptDownTime = 0;
            player.canvas.style.cursor = 'pointer';
            player.canvas.addEventListener('pointerdown', (e) => {{
              ptDownX = e.clientX;
              ptDownY = e.clientY;
              ptDownTime = Date.now();
            }});
            player.canvas.addEventListener('pointerup', (e) => {{
              const dist = Math.hypot(e.clientX - ptDownX, e.clientY - ptDownY);
              const dt = Date.now() - ptDownTime;
              if (dist < 8 && dt < 400) {{
                triggerCharacterStageTap();
              }}
            }});
          }}
        }} catch(err) {{
          console.warn("Skin composition note:", err);
        }}
      }},
      error: (player, err) => {{
        if (!player.disposed) {{
          console.warn("Spine Player error, fallback to static image:", err);
          showStaticMedia(char.frame0_url);
        }}
      }}
    }});
  }} catch(e) {{
    console.error("Spine player error:", e);
    showStaticMedia(char.frame0_url);
  }}
}}

// Dynamic Composite Skin Deck State & Rebuilder
let currentCompositeSkins = {{
  eye: null,
  mouth: null,
  blush: null,
  brow: null,
  fluids: {{}},
  overlays: {{}}
}};

function setupInitialCompositeSkins(player) {{
  if (!player || !player.skeleton) return;
  const sd = player.skeleton.data;
  currentCompositeSkins = {{
    eye: null,
    mouth: null,
    blush: null,
    brow: null,
    fluids: {{}},
    overlays: {{}}
  }};

  const isFluid = (n) => /(_wa|wa_|water|squirt|shoot|semen|wet|cum)/i.test(n);
  const isCensor = (n) => /(censor|mark|mosaic)/i.test(n);
  const candidates = {{ eye: [], mouth: [], blush: [], brow: [] }};

  for (let i = 0; i < sd.skins.length; i++) {{
    const sk = sd.skins[i];
    if (sk === sd.defaultSkin) continue;
    const name = sk.name;
    const nameL = name.toLowerCase();

    if (isFluid(nameL)) {{
      currentCompositeSkins.fluids[name] = false;
    }} else if (/(^|[_\-])eye/i.test(nameL)) {{
      candidates.eye.push(sk);
    }} else if (/(^|[_\-])mouth/i.test(nameL)) {{
      candidates.mouth.push(sk);
    }} else if (/(^|[_\-])(blush|cheek)/i.test(nameL)) {{
      candidates.blush.push(sk);
    }} else if (/(^|[_\-])brow/i.test(nameL)) {{
      candidates.brow.push(sk);
    }} else if (!isCensor(nameL) && !nameL.includes('light')) {{
      currentCompositeSkins.overlays[name] = false;
    }}
  }}

  for (const cat in candidates) {{
    const list = candidates[cat];
    if (list.length > 0) {{
      list.sort((a, b) => {{
        const a01 = /(01|(?<!\d)1(?!\d))/.test(a.name) ? 0 : 1;
        const b01 = /(01|(?<!\d)1(?!\d))/.test(b.name) ? 0 : 1;
        if (a01 !== b01) return a01 - b01;
        return a.name.localeCompare(b.name);
      }});
      currentCompositeSkins[cat] = list[0].name;
    }}
  }}
}}

function rebuildCompositeSkin() {{
  if (!activePlayer || !activePlayer.skeleton) return;
  const skel = activePlayer.skeleton;
  const sd = skel.data;
  const newSkin = new spine.Skin("custom_composite");

  if (sd.defaultSkin) newSkin.addSkin(sd.defaultSkin);

  ['eye', 'mouth', 'blush', 'brow'].forEach(cat => {{
    const sName = currentCompositeSkins[cat];
    if (sName) {{
      const s = sd.findSkin(sName);
      if (s) newSkin.addSkin(s);
    }}
  }});

  Object.keys(currentCompositeSkins.fluids).forEach(fName => {{
    if (currentCompositeSkins.fluids[fName]) {{
      const s = sd.findSkin(fName);
      if (s) newSkin.addSkin(s);
    }}
  }});

  Object.keys(currentCompositeSkins.overlays).forEach(ovName => {{
    if (currentCompositeSkins.overlays[ovName]) {{
      const s = sd.findSkin(ovName);
      if (s) newSkin.addSkin(s);
    }}
  }});

  const bgl = sd.findSlot("BG_Light");
  if (bgl) {{
    newSkin.removeAttachment(bgl.index, "BG_Light");
  }}

  skel.setSkin(newSkin);
  skel.setSlotsToSetupPose();

  const bgLightSlot = skel.findSlot("BG_Light");
  if (bgLightSlot) {{
    bgLightSlot.attachment = null;
    bgLightSlot.color.a = 0;
  }}

  applyCensorship(skel);
}}

function renderSkinDeck(player) {{
  const container = document.getElementById('skinDeckContainer');
  if (!container) return;
  container.innerHTML = '';

  if (!player || !player.skeleton) {{
    container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 13px;">No Spine model currently active.</div>';
    return;
  }}

  const sd = player.skeleton.data;
  const allSkins = sd.skins.filter(s => s !== sd.defaultSkin);

  const badge = document.getElementById('modalSkinsTabBadge');
  if (badge) badge.textContent = allSkins.length;

  if (allSkins.length === 0) {{
    container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 13px;">This model has a single base skin without alternate expressions or overlays.</div>';
    return;
  }}

  const isFluid = (n) => /(_wa|wa_|water|squirt|shoot|semen|wet|cum)/i.test(n);
  const isCensor = (n) => /(censor|mark|mosaic)/i.test(n);

  const categories = {{
    eye: allSkins.filter(s => /(^|[_\-])eye/i.test(s.name)),
    mouth: allSkins.filter(s => /(^|[_\-])mouth/i.test(s.name)),
    blush: allSkins.filter(s => /(^|[_\-])(blush|cheek)/i.test(s.name)),
    brow: allSkins.filter(s => /(^|[_\-])brow/i.test(s.name)),
    fluids: allSkins.filter(s => isFluid(s.name.toLowerCase())),
    overlays: allSkins.filter(s => !/(^|[_\-])(eye|mouth|blush|cheek|brow)/i.test(s.name) && !isFluid(s.name.toLowerCase()) && !isCensor(s.name.toLowerCase()) && !s.name.toLowerCase().includes('light'))
  }};

  // Facial Expressions Card
  const exprCard = document.createElement('div');
  exprCard.className = 'skin-category-card';
  exprCard.innerHTML = `
    <div class="skin-category-title">
      <span>😊 Facial Expressions</span>
      <button class="skin-reset-btn" onclick="resetDefaultExpressions()">↺ Reset</button>
    </div>
    <div class="skin-controls-grid"></div>
  `;
  const grid = exprCard.querySelector('.skin-controls-grid');
  const catLabels = {{ eye: '👀 Eyes', mouth: '👄 Mouth', blush: '😳 Blush', brow: '🤨 Eyebrows' }};

  ['eye', 'mouth', 'blush', 'brow'].forEach(cat => {{
    const list = categories[cat];
    if (list && list.length > 0) {{
      const row = document.createElement('div');
      row.className = 'skin-select-row';
      row.innerHTML = `<label class="skin-label">${{catLabels[cat]}}:</label>`;
      const sel = document.createElement('select');
      sel.className = 'skin-select';
      if (cat === 'blush' || cat === 'brow') {{
        const optNone = document.createElement('option');
        optNone.value = '';
        optNone.textContent = '(None / Neutral)';
        sel.appendChild(optNone);
      }}
      list.forEach(sk => {{
        const opt = document.createElement('option');
        opt.value = sk.name;
        opt.textContent = sk.name;
        if (currentCompositeSkins[cat] === sk.name) opt.selected = true;
        sel.appendChild(opt);
      }});
      sel.onchange = (e) => {{
        currentCompositeSkins[cat] = e.target.value || null;
        rebuildCompositeSkin();
      }};
      row.appendChild(sel);
      grid.appendChild(row);
    }}
  }});
  container.appendChild(exprCard);

  // Bodily Fluids Card
  if (categories.fluids.length > 0) {{
    const fluidCard = document.createElement('div');
    fluidCard.className = 'skin-category-card';
    fluidCard.innerHTML = `
      <div class="skin-category-title">
        <span>💦 Bodily Fluids & Splashes</span>
      </div>
      <div class="skin-toggle-grid"></div>
    `;
    const fGrid = fluidCard.querySelector('.skin-toggle-grid');
    categories.fluids.forEach(sk => {{
      const chip = document.createElement('button');
      chip.className = 'skin-toggle-chip' + (currentCompositeSkins.fluids[sk.name] ? ' active' : '');
      chip.textContent = '💧 ' + sk.name;
      chip.onclick = () => {{
        currentCompositeSkins.fluids[sk.name] = !currentCompositeSkins.fluids[sk.name];
        chip.classList.toggle('active', currentCompositeSkins.fluids[sk.name]);
        rebuildCompositeSkin();
      }};
      fGrid.appendChild(chip);
    }});
    container.appendChild(fluidCard);
  }}

  // Costume & Overlays Card
  if (categories.overlays.length > 0) {{
    const ovCard = document.createElement('div');
    ovCard.className = 'skin-category-card';
    ovCard.innerHTML = `
      <div class="skin-category-title">
        <span>👗 Costume & Accessory Overlays</span>
      </div>
      <div class="skin-toggle-grid"></div>
    `;
    const ovGrid = ovCard.querySelector('.skin-toggle-grid');
    categories.overlays.forEach(sk => {{
      const chip = document.createElement('button');
      chip.className = 'skin-toggle-chip' + (currentCompositeSkins.overlays[sk.name] ? ' active' : '');
      chip.textContent = '✨ ' + sk.name;
      chip.onclick = () => {{
        currentCompositeSkins.overlays[sk.name] = !currentCompositeSkins.overlays[sk.name];
        chip.classList.toggle('active', currentCompositeSkins.overlays[sk.name]);
        rebuildCompositeSkin();
      }};
      ovGrid.appendChild(chip);
    }});
    container.appendChild(ovCard);
  }}
}}

function resetDefaultExpressions() {{
  if (!activePlayer) return;
  setupInitialCompositeSkins(activePlayer);
  rebuildCompositeSkin();
  renderSkinDeck(activePlayer);
}}

function triggerCharacterStageTap() {{
  if (!activeModel) return;
  if (activeModel.is_hcg && activeModel.dialogues && activeModel.dialogues.length) {{
    nextStoryLine();
    return;
  }}
  const touchAnims = activeModel.animations.filter(a => /touch|talk/i.test(a.name));
  if (touchAnims.length) {{
    const chosen = touchAnims[touchCycleIdx % touchAnims.length].name;
    touchCycleIdx++;
    playSpineAnimation(activeModel, chosen);
    document.querySelectorAll('.anim-btn').forEach(b => {{
      b.classList.toggle('active', b.textContent.includes(chosen));
    }});
    if (activeModel.anim_voice_map && activeModel.anim_voice_map[chosen]) {{
      playInteractiveVoice(activeModel.anim_voice_map[chosen], `${{chosen.replace('_', ' ')}}`);
    }} else if (activeModel.touch_voices && activeModel.touch_voices.length) {{
      const v = activeModel.touch_voices[(touchCycleIdx - 1) % activeModel.touch_voices.length];
      playInteractiveVoice(v.url, v.name);
    }}
  }}
}}

async function playAnimationMedia(url) {{
  stopCurrentAnimation();
  disposeSpinePlayer();

  const modalImg = document.getElementById('modalImg');
  const modalCanvas = document.getElementById('modalCanvas');
  const speedControls = document.getElementById('speedControls');
  const pauseBtn = document.getElementById('pauseBtn');

  document.getElementById('modalDownloadImg').href = url;
  speedControls.style.display = 'flex';
  isPaused = false;
  if (pauseBtn) pauseBtn.textContent = '⏸ Pause';

  if (!('ImageDecoder' in window)) {{
    modalCanvas.style.display = 'none';
    modalImg.style.display = 'block';
    modalImg.src = url;
    return;
  }}

  const thisReq = ++loadRequestId;
  modalImg.style.display = 'block';
  modalCanvas.style.display = 'none';
  modalImg.src = url;

  try {{
    const res = await fetch(url);
    if (!res.ok) throw new Error('Fetch failed');
    const buffer = await res.arrayBuffer();
    if (thisReq !== loadRequestId) return;

    const decoder = new ImageDecoder({{ data: buffer, type: 'image/gif' }});
    await decoder.tracks.ready;
    const count = decoder.tracks.selectedTrack.frameCount;

    const frames = [];
    for (let i = 0; i < count; i++) {{
      if (thisReq !== loadRequestId) return;
      const decResult = await decoder.decode({{ frameIndex: i }});
      const durationMs = (decResult.image.duration || 66666) / 1000;
      const bmp = await createImageBitmap(decResult.image);
      decResult.image.close();
      frames.push({{ bitmap: bmp, durationMs: durationMs }});
    }}

    if (thisReq !== loadRequestId) {{
      frames.forEach(f => f.bitmap.close && f.bitmap.close());
      return;
    }}

    currentDecoderFrames = frames;
    currentFrameIndex = 0;
    modalImg.style.display = 'none';
    modalCanvas.style.display = 'block';
    renderCanvasFrame();
  }} catch (e) {{
    console.warn('ImageDecoder fallback to img:', e);
    if (thisReq === loadRequestId) {{
      modalCanvas.style.display = 'none';
      modalImg.style.display = 'block';
      modalImg.src = url;
    }}
  }}
}}

function showStaticMedia(url) {{
  stopCurrentAnimation();
  disposeSpinePlayer();

  const modalImg = document.getElementById('modalImg');
  const modalCanvas = document.getElementById('modalCanvas');
  const speedControls = document.getElementById('speedControls');

  modalCanvas.style.display = 'none';
  modalImg.style.display = 'block';
  modalImg.src = url;
  speedControls.style.display = 'none';
  document.getElementById('modalDownloadImg').href = url;
}}

function setSpeed(speed, btn) {{
  currentSpeed = speed;
  document.querySelectorAll('.speed-btn').forEach(b => {{
    if (b.id !== 'pauseBtn') b.classList.remove('active');
  }});
  if (btn) btn.classList.add('active');
  if (activePlayer && activePlayer.animationState) {{
    activePlayer.animationState.timeScale = isPaused ? 0 : currentSpeed;
  }}
  AudioEngine.setSpeed(isPaused ? 0 : currentSpeed);
  if (isPaused) togglePause();
}}

function togglePause() {{
  isPaused = !isPaused;
  const pauseBtn = document.getElementById('pauseBtn');
  if (pauseBtn) pauseBtn.textContent = isPaused ? '▶ Play' : '⏸ Pause';
  if (activePlayer && activePlayer.animationState) {{
    activePlayer.animationState.timeScale = isPaused ? 0 : currentSpeed;
  }}
  AudioEngine.setSpeed(isPaused ? 0 : currentSpeed);
  if (!isPaused) renderCanvasFrame();
  else if (animTimeoutId) {{
    clearTimeout(animTimeoutId);
    animTimeoutId = null;
  }}
}}

// Tab Switching
function switchModalTab(tabId, btn) {{
  document.querySelectorAll('.modal-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const target = document.getElementById(tabId);
  if (target) target.classList.add('active');
}}

function playCurrentSceneBgm() {{
  if (activeModel && activeModel.default_bgm) {{
    playBgmById(activeModel.default_bgm);
  }}
}}

// On-demand JSON Details Loader (Eliminates Browser Lag)
async function loadModelDetails(char) {{
  if (!char || char._detailsLoaded) return char;
  try {{
    const res = await fetch(`/data/${{char.stem}}.json`);
    if (res.ok) {{
      const data = await res.json();
      char.dialogues = data.dialogues || [];
      char.touch_voices = data.touch_voices || [];
      char.role_voices = data.role_voices || [];
      char._detailsLoaded = true;
    }}
  }} catch(e) {{
    console.warn("Could not load details for " + char.stem, e);
  }}
  return char;
}}

// H-Scene SFX Engine (Wet Thrusts, Panting/Moans, Climax Splashes)
function syncLineSfx(line) {{
  if (!sfxAudioEnabled || !gameAudioEnabled) {{
    AudioEngine.stopAllLoops();
    return;
  }}
  if (!line || !line.sfx_tracks || !line.sfx_tracks.length) {{
    AudioEngine.stopAllLoops();
    return;
  }}

  let loopSeUrl = null;
  let loopMoanUrl = null;

  for (const trk of line.sfx_tracks) {{
    if (trk.loop) {{
      if (trk.type === 'se') loopSeUrl = trk.url;
      else if (trk.type === 'moan') loopMoanUrl = trk.url;
    }} else {{
      AudioEngine.playOneShot(trk.url, 1.0);
    }}
  }}

  AudioEngine.setLoop('se', loopSeUrl, 1.0);
  AudioEngine.setLoop('moan', loopMoanUrl, 0.85);
}}

// Stage Phase Quick Jump Bar
// Play the H-scene SFX that the game pairs with a given Spine animation (Insert_01 etc).
function syncAnimSfx(char, animName) {{
  const lines = (char && char.dialogues) || [];
  const hit = lines.find(d => d.anim && d.sfx_tracks && d.sfx_tracks.length &&
    d.anim.split('$').some(a => a.trim() === animName));
  if (hit) {{
    syncLineSfx(hit);
  }} else {{
    AudioEngine.stopAllLoops();
  }}
}}

function renderStagePhases(char) {{
  const bar = document.getElementById('stagePhaseBar');
  if (!bar) return;
  bar.innerHTML = '';
  if (!char.is_hcg || !char.h_phases || !char.h_phases.length) {{
    bar.style.display = 'none';
    return;
  }}
  bar.style.display = 'flex';
  char.h_phases.forEach(phase => {{
    const pill = document.createElement('button');
    pill.className = 'phase-pill';
    pill.textContent = phase.label;
    pill.title = `Jump to ${{phase.anim}} (Line ${{phase.line_idx + 1}})`;
    pill.dataset.lineIdx = phase.line_idx;
    pill.onclick = (e) => {{
      e.stopPropagation();
      jumpToStoryPhase(phase.line_idx);
    }};
    bar.appendChild(pill);
  }});
  updateActivePhasePill();
}}

function updateActivePhasePill() {{
  if (!activeModel || !activeModel.h_phases) return;
  const currentLine = storyAutoPlayIdx;
  let activePhase = null;
  for (const phase of activeModel.h_phases) {{
    if (phase.line_idx <= currentLine) {{
      activePhase = phase;
    }} else {{
      break;
    }}
  }}
  document.querySelectorAll('#stagePhaseBar .phase-pill').forEach(pill => {{
    const pIdx = parseInt(pill.dataset.lineIdx, 10);
    pill.classList.toggle('active', activePhase && pIdx === activePhase.line_idx);
  }});
}}

function jumpToStoryPhase(lineIdx) {{
  if (!activeModel || !activeModel.dialogues || lineIdx >= activeModel.dialogues.length) return;

  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}

  voiceAudio.onended = null;
  voiceAudio.pause();
  duckBgm(false);
  hideSpeechBubble();
  const wave = document.getElementById('vnVoiceWave');
  if (wave) wave.style.display = 'none';

  storyAutoPlayIdx = lineIdx;
  playNextStoryLine();
}}

// Story & Visual Novel Engine
let storyAutoTimer = null;

function updateStoryAutoUI() {{
  const autoBtn = document.getElementById('vnAutoBtn');
  if (autoBtn) {{
    autoBtn.classList.toggle('active', isStoryAutoPlaying);
    autoBtn.textContent = isStoryAutoPlaying ? '⏸ AUTO' : '▶ AUTO';
  }}
  const storyTabBtn = document.getElementById('autoPlayStoryBtn');
  if (storyTabBtn) {{
    storyTabBtn.classList.toggle('active', isStoryAutoPlaying);
    storyTabBtn.textContent = isStoryAutoPlaying ? '⏹ Stop Auto-Play' : '▶ Auto-Play Story with Voices';
  }}
}}

function toggleStoryAutoPlay(e) {{
  if (e) e.stopPropagation();
  isStoryAutoPlaying = !isStoryAutoPlaying;
  updateStoryAutoUI();
  if (isStoryAutoPlaying) {{
    if (!activeModel || !activeModel.dialogues || !activeModel.dialogues.length) return;
    if (storyAutoPlayIdx >= activeModel.dialogues.length) {{
      storyAutoPlayIdx = 0;
    }}
    playNextStoryLine();
  }} else {{
    if (storyAutoTimer) {{
      clearTimeout(storyAutoTimer);
      storyAutoTimer = null;
    }}
    voiceAudio.pause();
    duckBgm(false);
    const wave = document.getElementById('vnVoiceWave');
    if (wave) wave.style.display = 'none';
  }}
}}

function nextStoryLine(e) {{
  if (e) e.stopPropagation();
  if (!activeModel || !activeModel.dialogues || !activeModel.dialogues.length) return;
  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}
  voiceAudio.pause();
  duckBgm(false);
  const wave = document.getElementById('vnVoiceWave');
  if (wave) wave.style.display = 'none';

  if (storyAutoPlayIdx + 1 < activeModel.dialogues.length) {{
    storyAutoPlayIdx++;
    playNextStoryLine();
  }} else if (isStoryAutoPlaying) {{
    toggleStoryAutoPlay();
  }}
}}

function prevStoryLine(e) {{
  if (e) e.stopPropagation();
  if (!activeModel || !activeModel.dialogues || !activeModel.dialogues.length) return;
  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}
  voiceAudio.pause();
  duckBgm(false);
  const wave = document.getElementById('vnVoiceWave');
  if (wave) wave.style.display = 'none';

  if (storyAutoPlayIdx > 0) {{
    storyAutoPlayIdx--;
    playNextStoryLine();
  }}
}}

function advanceStoryOnClick(e) {{
  if (e) e.stopPropagation();
  nextStoryLine(e);
}}

function toggleVnMinimize(e) {{
  if (e) e.stopPropagation();
  const box = document.getElementById('stageDialogueBox');
  if (!box) return;
  const isMin = box.classList.toggle('minimized');
  const minBtn = box.querySelector('.min-btn');
  if (minBtn) minBtn.textContent = isMin ? '▲' : '▼';
}}

function playNextStoryLine() {{
  if (!activeModel || !activeModel.dialogues || !activeModel.dialogues.length) return;
  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}

  if (storyAutoPlayIdx >= activeModel.dialogues.length) {{
    if (isStoryAutoPlaying) toggleStoryAutoPlay();
    return;
  }}

  const line = activeModel.dialogues[storyAutoPlayIdx];
  const total = activeModel.dialogues.length;

  // Synchronize authentic H-scene SFX (wet thrusts, moans, splashes)
  syncLineSfx(line);
  updateActivePhasePill();

  // Highlight dialogue in right tab
  const cards = document.querySelectorAll('.dialogue-card');
  cards.forEach((c, idx) => c.classList.toggle('highlighted', idx === storyAutoPlayIdx));
  if (cards[storyAutoPlayIdx]) {{
    cards[storyAutoPlayIdx].scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }}
  const storyLineCounter = document.getElementById('storyLineCounter');
  if (storyLineCounter) {{
    storyLineCounter.textContent = `Line ${{storyAutoPlayIdx + 1}} of ${{total}}`;
  }}

  // Update on-stage Visual Novel floating bar
  const vnBox = document.getElementById('stageDialogueBox');
  if (vnBox) vnBox.style.display = 'block';

  const vnSpeaker = document.getElementById('vnSpeakerName');
  if (vnSpeaker) {{
    vnSpeaker.className = 'vn-speaker-name';
    const spk = (line.speaker || 'Narrator').trim();
    if (spk.toLowerCase().includes('master')) {{
      vnSpeaker.classList.add('master');
      vnSpeaker.textContent = spk;
    }} else if (spk.toLowerCase() === 'narrator' || !line.speaker) {{
      vnSpeaker.classList.add('narrator');
      vnSpeaker.textContent = 'Narration';
    }} else {{
      vnSpeaker.classList.add('heroine');
      vnSpeaker.textContent = spk;
    }}
  }}

  const vnAnimBadge = document.getElementById('vnAnimBadge');
  if (vnAnimBadge) {{
    if (line.anim) {{
      vnAnimBadge.textContent = '🎬 ' + line.anim;
      vnAnimBadge.style.display = 'inline-block';
    }} else {{
      vnAnimBadge.style.display = 'none';
    }}
  }}

  const vnLineCounter = document.getElementById('vnLineCounter');
  if (vnLineCounter) {{
    vnLineCounter.textContent = `${{storyAutoPlayIdx + 1}} / ${{total}}`;
  }}

  const vnTextEn = document.getElementById('vnTextEn');
  if (vnTextEn) vnTextEn.textContent = line.text || '...';

  const vnTextZh = document.getElementById('vnTextZh');
  if (vnTextZh) {{
    if (line.text_zh) {{
      vnTextZh.textContent = line.text_zh;
      vnTextZh.style.display = 'block';
    }} else {{
      vnTextZh.style.display = 'none';
    }}
  }}

  // Trigger Spine animation transition if present
  if (line.anim && activeModel.has_spine) {{
    const primaryAnim = line.anim.split('$')[0].trim();
    const matched = activeModel.animations.find(a => a.name.toLowerCase() === primaryAnim.toLowerCase()) ||
                    activeModel.animations.find(a => a.name.toLowerCase().includes(primaryAnim.toLowerCase()));
    if (matched) {{
      playSpineAnimation(activeModel, matched.name);
      document.querySelectorAll('.anim-btn').forEach(b => {{
        b.classList.toggle('active', b.textContent.includes(matched.name));
      }});
    }}
  }}

  // Play dialogue voice and advance if auto-playing
  const wave = document.getElementById('vnVoiceWave');
  if (line.voice_url && gameAudioEnabled) {{
    if (wave) wave.style.display = 'inline-flex';
    duckBgm(true);
    voiceAudio.src = line.voice_url;
    voiceAudio.play().then(() => {{
      voiceAudio.onended = () => {{
        duckBgm(false);
        if (wave) wave.style.display = 'none';
        if (isStoryAutoPlaying) {{
          storyAutoTimer = setTimeout(() => {{
            nextStoryLine();
          }}, 800);
        }}
      }};
    }}).catch(e => {{
      duckBgm(false);
      if (wave) wave.style.display = 'none';
      if (isStoryAutoPlaying) {{
        storyAutoTimer = setTimeout(() => {{
          nextStoryLine();
        }}, 2500);
      }}
    }});
  }} else {{
    if (wave) wave.style.display = 'none';
    duckBgm(false);
    if (isStoryAutoPlaying) {{
      const duration = Math.min(5000, Math.max(2200, (line.text || '').length * 55));
      storyAutoTimer = setTimeout(() => {{
        nextStoryLine();
      }}, duration);
    }}
  }}
}}

// Tab Renderers
function renderAnimationsTab(char) {{
  const animGrid = document.getElementById('modalAnimGrid');
  animGrid.innerHTML = '';

  const frame0Btn = document.createElement('button');
  frame0Btn.className = 'anim-btn';
  frame0Btn.textContent = '🖼 Frame 0 (Setup Pose)';
  frame0Btn.onclick = () => {{
    showStaticMedia(char.frame0_url);
    document.querySelectorAll('.anim-btn').forEach(b => b.classList.remove('active'));
    frame0Btn.classList.add('active');
  }};
  animGrid.appendChild(frame0Btn);

  const gifByAnim = {{}};
  char.gifs.forEach(g => {{ gifByAnim[g.anim] = g; }});

  const bestDefaultAnim = char.animations.find(a => !a.name.toLowerCase().includes('_mark') && (a.name.toLowerCase().includes('idle') || a.name.toLowerCase().includes('finish'))) ||
                          char.animations.find(a => !a.name.toLowerCase().includes('_mark')) ||
                          char.animations[0];

  let defaultActivated = false;

  char.animations.forEach((a) => {{
    const aBtn = document.createElement('button');
    const hasGif = Boolean(gifByAnim[a.name]);
    const durLabel = a.duration ? ` (${{a.duration}}s)` : '';
    const isMark = a.name.toLowerCase().includes('_mark');
    const markBadge = isMark ? ' [Censored]' : '';

    if (hasGif) {{
      aBtn.className = 'anim-btn gif-ready';
      aBtn.textContent = '🎬 ' + a.name + markBadge + durLabel;
    }} else {{
      aBtn.className = 'anim-btn live-spine';
      aBtn.textContent = (isMark ? '🛡 ' : '▶ ') + a.name + markBadge + durLabel;
    }}

    aBtn.onclick = () => {{
      document.querySelectorAll('.anim-btn').forEach(b => b.classList.remove('active'));
      aBtn.classList.add('active');
      history.replaceState(null, '', `?char=${{char.stem}}&anim=${{encodeURIComponent(a.name)}}`);

      if (char.has_spine) {{
        playSpineAnimation(char, a.name);
        syncAnimSfx(char, a.name);
      }} else if (hasGif) {{
        playAnimationMedia(gifByAnim[a.name].url);
      }} else {{
        showStaticMedia(char.frame0_url);
      }}

      // Character Interactive Voice reaction on animation click
      if (gameAudioEnabled && char.anim_voice_map && char.anim_voice_map[a.name]) {{
        playInteractiveVoice(char.anim_voice_map[a.name], a.name.replace(/_/g, ' '));
      }}

      const dlBtn = document.getElementById('modalDownloadImg');
      if (hasGif) {{
        dlBtn.href = gifByAnim[a.name].url;
        dlBtn.textContent = `💾 Download GIF (${{a.name}})`;
      }} else {{
        dlBtn.href = char.frame0_url;
        dlBtn.textContent = `💾 Download Frame 0 Image`;
      }}
    }};

    animGrid.appendChild(aBtn);

    if (!defaultActivated && bestDefaultAnim && a.name === bestDefaultAnim.name) {{
      aBtn.classList.add('active');
      defaultActivated = true;
      if (char.has_spine) playSpineAnimation(char, a.name);
      else if (hasGif) playAnimationMedia(gifByAnim[a.name].url);
      else showStaticMedia(char.frame0_url);
    }}
  }});

  if (!defaultActivated) {{
    frame0Btn.classList.add('active');
    if (char.has_spine) playSpineAnimation(char, null);
    else showStaticMedia(char.frame0_url);
  }}
}}

function renderVoicesTab(char) {{
  const touchList = document.getElementById('modalTouchVoices');
  touchList.innerHTML = '';
  if (char.touch_voices && char.touch_voices.length) {{
    char.touch_voices.forEach(v => {{
      const card = document.createElement('div');
      card.className = 'voice-card';
      card.innerHTML = `
        <div class="voice-info">
          <span class="voice-tag">${{v.name}}</span>
          <span class="voice-en">${{v.clip}}</span>
        </div>
        <button class="voice-play-btn" onclick="playVoiceLine('${{v.url}}', this)">▶ Play Voice</button>
      `;
      touchList.appendChild(card);
    }});
  }} else {{
    touchList.innerHTML = '<div style="color:var(--text-muted); font-size:12px; font-style:italic;">No direct touch interaction voice lines for this costume.</div>';
  }}

  const roleList = document.getElementById('modalRoleVoices');
  roleList.innerHTML = '';
  if (char.role_voices && char.role_voices.length) {{
    char.role_voices.forEach(v => {{
      const card = document.createElement('div');
      card.className = 'voice-card';
      card.innerHTML = `
        <div class="voice-info">
          <span class="voice-tag">${{v.tag}}</span>
          <span class="voice-en">${{v.text_en}}</span>
          <span class="voice-zh">${{v.text_zh}}</span>
        </div>
        <button class="voice-play-btn" onclick="playVoiceLine('${{v.url}}', this)">▶ Play Voice</button>
      `;
      roleList.appendChild(card);
    }});
  }} else {{
    roleList.innerHTML = '<div style="color:var(--text-muted); font-size:12px; font-style:italic;">No favorability role dialogues linked for this code.</div>';
  }}

  const totalVoices = (char.touch_voices ? char.touch_voices.length : 0) + (char.role_voices ? char.role_voices.length : 0);
  document.getElementById('modalVoiceTabBadge').textContent = totalVoices;
}}

function renderStoryTab(char) {{
  const dialogBox = document.getElementById('modalDialogues');
  dialogBox.innerHTML = '';
  if (char.dialogues && char.dialogues.length) {{
    document.getElementById('modalStoryTabBadge').textContent = char.dialogues.length;
    char.dialogues.forEach((d) => {{
      const dCard = document.createElement('div');
      dCard.className = 'dialogue-card';

      let spkClass = 'narrator';
      if (d.speaker.toLowerCase().includes('master')) spkClass = 'master';
      else if (d.speaker) spkClass = 'heroine';

      const voiceBtnHtml = d.voice_url ? 
        `<button class="voice-play-btn" style="padding: 2px 8px; font-size: 11px;" onclick="playVoiceLine('${{d.voice_url}}', this)">▶ Voice</button>` : '';

      dCard.innerHTML = `
        <div class="dialogue-header">
          ${{d.speaker ? `<span class="dialogue-speaker ${{spkClass}}">[${{d.speaker}}]</span>` : '<span class="dialogue-speaker narrator">Narration</span>'}}
          ${{voiceBtnHtml}}
        </div>
        <div class="dialogue-text">${{d.text}}</div>
        ${{d.text_zh ? `<div class="dialogue-text-zh">${{d.text_zh}}</div>` : ''}}
      `;
      dialogBox.appendChild(dCard);
    }});
  }} else {{
    document.getElementById('modalStoryTabBadge').textContent = '0';
    dialogBox.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 13px;">No specific story dialogues cataloged for this model.</div>';
  }}
}}

function setupSceneMode(char) {{
  const vnBox = document.getElementById('stageDialogueBox');
  hideSpeechBubble();

  if (char.is_hcg && char.dialogues && char.dialogues.length > 0) {{
    if (vnBox) {{
      vnBox.style.display = 'block';
      vnBox.classList.remove('minimized');
      const minBtn = vnBox.querySelector('.min-btn');
      if (minBtn) minBtn.textContent = '▼';
    }}
    storyAutoPlayIdx = 0;
    isStoryAutoPlaying = gameAudioEnabled;
    updateStoryAutoUI();
    playNextStoryLine();
  }} else {{
    if (vnBox) vnBox.style.display = 'none';
    if (!char.is_hcg && gameAudioEnabled && char.greeting_voice) {{
      setTimeout(() => {{
        if (activeModel && activeModel.stem === char.stem) {{
          playInteractiveVoice(char.greeting_voice, char.greeting_text || char.name_en);
        }}
      }}, 600);
    }}
  }}
}}

// Open Modal with On-Demand Async Details
async function openModal(char) {{
  activeModel = char;
  resetZoom();
  touchCycleIdx = 0;
  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}
  voiceAudio.onended = null;
  voiceAudio.pause();
  AudioEngine.stopAllLoops();
  duckBgm(false);
  isStoryAutoPlaying = false;
  updateStoryAutoUI();

  const modal = document.getElementById('modalOverlay');
  const displayName = char.name_zh ? `${{char.name_en}} (${{char.name_zh}})` : char.name_en;
  document.getElementById('modalTitle').textContent = displayName;
  document.getElementById('modalStem').textContent = `[${{char.category}}] ${{char.stem}}`;
  document.getElementById('modalAnimTabBadge').textContent = char.animations.length;

  const bgmBadge = document.getElementById('modalSceneBgmBadge');
  if (char.default_bgm) {{
    bgmBadge.style.display = 'inline-block';
    bgmBadge.textContent = `🎵 BGM: ${{char.default_bgm}}`;
  }} else {{
    bgmBadge.style.display = 'none';
  }}

  // Auto-play official in-game scene/lobby BGM
  if (gameAudioEnabled && char.default_bgm) {{
    playBgmById(char.default_bgm, true);
  }}

  // Model Info Tab
  document.getElementById('infoStem').textContent = char.stem;
  document.getElementById('infoCategory').textContent = char.category;
  document.getElementById('infoAnims').textContent = `${{char.animations.length}} Animations`;
  document.getElementById('skelDownloadLink').href = `/spines/${{char.stem}}/${{char.stem}}.skel`;
  document.getElementById('atlasDownloadLink').href = `/spines/${{char.stem}}/${{char.stem}}.atlas`;

  // Render Animations Tab immediately
  renderAnimationsTab(char);

  // Render Stage Phase Bar immediately
  renderStagePhases(char);

  // Switch default tab to Animations
  switchModalTab('tabAnims', document.querySelectorAll('.modal-tabs .tab-btn')[0]);

  history.replaceState(null, '', `?char=${{char.stem}}`);
  modal.classList.add('active');

  // Load detailed dialogues and role voices asynchronously
  await loadModelDetails(char);

  // If this model is still active after fetch, populate details
  if (activeModel && activeModel.stem === char.stem) {{
    renderVoicesTab(char);
    renderStoryTab(char);
    setupSceneMode(char);
  }}
}}

function closeModal(e) {{
  if (e && e.target !== document.getElementById('modalOverlay') && !e.target.classList.contains('modal-close')) return;
  if (storyAutoTimer) {{
    clearTimeout(storyAutoTimer);
    storyAutoTimer = null;
  }}
  isStoryAutoPlaying = false;
  voiceAudio.onended = null;
  voiceAudio.pause();
  AudioEngine.stopAllLoops();
  duckBgm(false);
  hideSpeechBubble();

  if (isCinemaMode) {{
    toggleCinemaMode();
  }}

  const vnBox = document.getElementById('stageDialogueBox');
  if (vnBox) vnBox.style.display = 'none';
  const wave = document.getElementById('vnVoiceWave');
  if (wave) wave.style.display = 'none';
  const phaseBar = document.getElementById('stagePhaseBar');
  if (phaseBar) phaseBar.innerHTML = '';

  stopCurrentAnimation();
  disposeSpinePlayer();
  document.getElementById('modalOverlay').classList.remove('active');
  activeModel = null;
  history.replaceState(null, '', window.location.pathname);
}}

function navigateModal(direction) {{
  if (!activeModel || !filteredModels.length) return;
  const curIdx = filteredModels.findIndex(m => m.stem === activeModel.stem);
  if (curIdx < 0) return;
  const nextIdx = (curIdx + direction + filteredModels.length) % filteredModels.length;
  openModal(filteredModels[nextIdx]);
}}

// Keyboard Navigation
window.addEventListener('keydown', (e) => {{
  if (e.key === '/' && document.activeElement !== document.getElementById('searchInput')) {{
    e.preventDefault();
    document.getElementById('searchInput').focus();
    return;
  }}
  if (document.getElementById('modalOverlay').classList.contains('active')) {{
    if (e.key === 'Escape') {{
      if (isCinemaMode) toggleCinemaMode();
      else closeModal();
    }} else if (e.key.toLowerCase() === 'c') {{
      toggleCinemaMode();
    }} else if (e.key === 'ArrowLeft') {{
      if (!isCinemaMode) navigateModal(-1);
    }} else if (e.key === 'ArrowRight') {{
      if (!isCinemaMode) navigateModal(1);
    }} else if (e.key === ' ' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {{
      e.preventDefault();
      togglePause();
    }} else if (e.key.toLowerCase() === 'f') {{
      toggleFullscreen();
    }} else if (e.key.toLowerCase() === 'm') {{
      toggleBgmPlay();
    }}
  }} else if (document.getElementById('bgmDrawer').classList.contains('active')) {{
    if (e.key === 'Escape') toggleBgmDrawer();
  }}
}});

// Initialize
initBgm();
renderGrid();

window.addEventListener('DOMContentLoaded', () => {{
  const params = new URLSearchParams(window.location.search);
  const charStem = params.get('char');
  const animName = params.get('anim');
  if (charStem) {{
    const target = models.find(m => m.stem.toLowerCase() === charStem.toLowerCase());
    if (target) {{
      openModal(target);
      if (animName) {{
        setTimeout(() => {{
          const btns = Array.from(document.querySelectorAll('.anim-btn'));
          const btn = btns.find(b => b.textContent.includes(animName));
          if (btn) btn.click();
        }}, 120);
      }}
    }}
  }}
}});
</script>
</body>
</html>
"""

# Write to viewer/index.html only if content changed
viewer_index = os.path.join(VIEWER_DIR, "index.html")
index_written = write_if_changed(viewer_index, html_content)

if index_written:
    print(f"🎉 Generated Web Gallery at {viewer_index} with full audio and enhanced UX!")
else:
    print(f"⚡ Web Gallery at {viewer_index} is up to date (0 bytes changed).")

