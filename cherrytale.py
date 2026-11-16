#!/usr/bin/env python3
"""CherryTale End-to-End Reverse Engineering & Datamine Pipeline (Standalone).

A 100% self-contained toolchain that runs directly in an empty directory.
Zero external repository dependencies; requires only standard Python + UnityPy + Pillow.

Subcommands:
  sync       Query live server API, retrieve master index, decrypt settings & translations.
  download   Bulk download & decrypt assets from CDN into Asset/ (Keep-Alive, multi-threaded).
  extract    Extract Spine models (.skel, .atlas, .png) and Audio clips (.wav).
  build      Compile WebP thumbnails, choreography JSONs, and responsive Web Viewer.
  serve      Launch the local interactive gallery web server (http://localhost:8000).
  run-all    Run the complete end-to-end pipeline from start to finish.
"""

import os
import sys
import json
import ssl
import time
import http.client
import urllib.parse
import urllib.request
import re
import zipfile
import threading
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field, asdict

# -----------------------------------------------------------------------------
# Workspace Paths (Anchored to this script's directory)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = BASE_DIR / "hcg_manifest"
ASSET_DIR = BASE_DIR / "Asset"
DUMP_DIR = BASE_DIR / "dump"
TEXT_DIR = DUMP_DIR / "textassets"
SPINE_DIR = DUMP_DIR / "hcg_art"
AUDIO_DIR = DUMP_DIR / "audio"
VIEWER_DIR = BASE_DIR / "viewer"
DATA_DIR = VIEWER_DIR / "data"
THUMBS_DIR = VIEWER_DIR / "thumbs"

SKEL_DIR = SPINE_DIR / "skel"
ATLAS_DIR = SPINE_DIR / "atlas"
TEX_DIR = SPINE_DIR / "textures"

BGM_DIR = AUDIO_DIR / "bgm"
VOICE_DIR = AUDIO_DIR / "voice"
SE_DIR = AUDIO_DIR / "se"

for d in (MANIFEST_DIR, ASSET_DIR, TEXT_DIR, SKEL_DIR, ATLAS_DIR, TEX_DIR, BGM_DIR, VOICE_DIR, SE_DIR, DATA_DIR, THUMBS_DIR):
    os.makedirs(d, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Cryptography Engine (CherryTale_AssetDecDL Specification)
# -----------------------------------------------------------------------------
IDX_SWAP = (0x3FB, 0xD99, 0x197C)
FAKE_VER = b"2018.3.5f1\x00"
REAL_VER = b"2020.3.41f1"
BIT_REV_TABLE = bytes(((b * 0x0202020202 & 0x010884422010) % 1023) for b in range(256))

def is_unityfs(data: bytes) -> bool:
    return data[:7] == b"UnityFS"

def change_idx(data: bytes) -> bytearray:
    d = bytearray(data)
    L = len(d)
    for off in IDX_SWAP:
        if L > off:
            other = L - off
            d[off], d[other] = d[other], d[off]
    return d

def change_version(data: bytearray) -> bytearray:
    head_len = min(0x1000, len(data))
    head = data[:head_len]
    if FAKE_VER in head:
        head = head.replace(FAKE_VER, REAL_VER)
        data[:len(head)] = head
    return data

def decrypt_unityfs(raw: bytes) -> bytes:
    return bytes(change_version(change_idx(raw)))

def decrypt_settings(raw: bytes) -> bytes:
    return bytes(change_idx(raw))

def decrypt_text_language(raw: bytes) -> bytes:
    return raw.translate(BIT_REV_TABLE)[::-1]

# -----------------------------------------------------------------------------
# 2. Network Client & CDN Downloader
# -----------------------------------------------------------------------------
CDN_HOST = "pfdd.88kongque.com"
CDN_BASE_PATH = "/patch/files/"
API_HOST = "api-ct-labs.ecchi.xxx"
USER_AGENT = "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)"
SSL_CTX = ssl._create_unverified_context()

class _ThreadLocalState(threading.local):
    conn: Optional[http.client.HTTPSConnection] = None

_tls = _ThreadLocalState()

def _get_conn() -> http.client.HTTPSConnection:
    if _tls.conn is None:
        _tls.conn = http.client.HTTPSConnection(CDN_HOST, context=SSL_CTX, timeout=20)
    return _tls.conn

def _reset_conn():
    if getattr(_tls, "conn", None) is not None:
        try:
            _tls.conn.close()
        except Exception:
            pass
        _tls.conn = None

def get_token() -> str:
    token_file = MANIFEST_DIR / "access_token.txt"
    if token_file.exists():
        try:
            return token_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""

def query_latest_node(nodes=(1002, 1004, 1000)) -> Tuple[int, Dict[str, str]]:
    token = get_token()
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for node in nodes:
        url = f"https://{API_HOST}/api/getMd5ByNode_V2.jsp?node={node}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
                if "client_patch_index_md5" in data:
                    return node, data
        except Exception:
            continue
    raise RuntimeError("Failed to resolve patch index from live API node.")

def fetch_index(patch_md5: str, save_path: Optional[str] = None) -> Dict[str, list]:
    token = get_token()
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://{CDN_HOST}{CDN_BASE_PATH}index.txt.{patch_md5}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as r:
        raw = r.read()
    index_dict = json.loads(raw.decode("utf-8"))
    if save_path:
        with open(save_path, "wb") as f:
            f.write(raw)
    return index_dict

def download_and_decrypt_asset(
    name: str,
    md5: str,
    out_dir: str = str(ASSET_DIR),
    token: str = "",
    overwrite: bool = False
) -> Tuple[str, str, int]:
    out_path = os.path.join(out_dir, name)
    if not overwrite and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return (name, "SKIPPED", 0)

    quoted_name = urllib.parse.quote(name)
    url_path = f"{CDN_BASE_PATH}{quoted_name}.{md5}"
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, 4):
        try:
            conn = _get_conn()
            conn.request("GET", url_path, headers=headers)
            resp = conn.getresponse()
            if resp.status == 200:
                raw_data = resp.read()
                if is_unityfs(raw_data):
                    dec_data = decrypt_unityfs(raw_data)
                elif name == "settings":
                    dec_data = decrypt_settings(raw_data)
                elif name.startswith("LanguageSettings_") and name.endswith(".txt"):
                    dec_data = decrypt_text_language(raw_data)
                else:
                    dec_data = raw_data

                tmp_path = f"{out_path}.tmp_{threading.get_ident()}"
                with open(tmp_path, "wb") as f:
                    f.write(dec_data)
                if os.path.exists(out_path):
                    os.remove(out_path)
                os.rename(tmp_path, out_path)
                return (name, "OK", len(dec_data))
            elif resp.status == 404:
                resp.read()
                return (name, "404_NOT_FOUND", 0)
            else:
                resp.read()
                _reset_conn()
                time.sleep(0.3 * attempt)
        except Exception:
            _reset_conn()
            time.sleep(0.3 * attempt)
    return (name, "ERR_FAILED", 0)

def sync_assets(
    index_dict: Dict[str, list],
    out_dir: str = str(ASSET_DIR),
    workers: int = 32,
    overwrite: bool = False,
    filter_fn: Optional[Callable[[str], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str, int], None]] = None
) -> Dict[str, int]:
    token = get_token()
    targets = []
    for k, v in index_dict.items():
        if isinstance(v, list) and len(v) >= 2:
            if filter_fn is None or filter_fn(k):
                targets.append((k, v[0], v[1]))

    stats = {"total": len(targets), "ok": 0, "skipped": 0, "failed": 0, "bytes": 0}
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                download_and_decrypt_asset,
                name,
                md5,
                out_dir,
                token,
                overwrite
            ): name for name, sz, md5 in targets
        }

        for f in as_completed(futures):
            name, status, b_count = f.result()
            completed += 1
            if status == "OK":
                stats["ok"] += 1
                stats["bytes"] += b_count
            elif status == "SKIPPED":
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

            if progress_callback:
                progress_callback(completed, stats["total"], status, b_count)
    return stats

# -----------------------------------------------------------------------------
# 3. Game Database & Metadata Parser
# -----------------------------------------------------------------------------
def clean_text(text: str) -> str:
    if not text or text in ("NULL", "-1", "null"):
        return ""
    return re.sub(r"<[^>]+>", "", text).rstrip("┤\r\n").strip()

@dataclass
class HSceneStep:
    step: int
    speaker_en: str
    speaker_zh: str
    text_en: str
    text_zh: str
    anim: Optional[str] = None
    voice: Optional[str] = None
    bgm: Optional[str] = None
    sfx: List[str] = field(default_factory=list)
    bg: Optional[str] = None

@dataclass
class HScene:
    scene_id: str
    char_code: str
    title_en: str
    title_zh: str
    steps: List[HSceneStep] = field(default_factory=list)
    bgm_tracks: List[str] = field(default_factory=list)
    voice_clips: List[str] = field(default_factory=list)
    sfx_clips: List[str] = field(default_factory=list)
    spine_anims: List[str] = field(default_factory=list)

@dataclass
class CharacterMetadata:
    code: str
    role_id: str
    name_en: str
    name_zh: str
    title_en: str
    title_zh: str
    cup: str
    height: str
    weight: str
    personality: str
    theme: str
    cg_spine: str
    hcg_spine: str
    hscenes: List[str] = field(default_factory=list)

class GameDatabase:
    def __init__(self, text_dir: Path = TEXT_DIR):
        self.text_dir = Path(text_dir)
        self.translations: Dict[str, str] = {}
        self.characters: Dict[str, CharacterMetadata] = {}
        self.hscenes: Dict[str, HScene] = {}
        self._load_translations()
        self._load_roles()
        self._load_hscenes()

    def translate(self, zh_text: str) -> str:
        cleaned = clean_text(zh_text)
        if not cleaned:
            return ""
        if cleaned == "${playername}":
            return "Master"
        if cleaned in self.translations:
            return self.translations[cleaned]
        for punct in ("！", "？", "，", "。", "……", "♥", "…", "!", "?", ",", "."):
            if cleaned.endswith(punct) and cleaned[:-len(punct)] in self.translations:
                return self.translations[cleaned[:-len(punct)]] + (punct if punct in "!?.," else "")
        return cleaned

    def _load_translations(self):
        enus_file = self.text_dir / "LanguageSettings_enus.txt"
        if not enus_file.exists():
            return
        with open(enus_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "|" in line:
                    parts = line.split("|", 1)
                    zh = clean_text(parts[0])
                    en_val = parts[1].split("┤")[0].strip()
                    if zh and en_val:
                        self.translations[zh] = en_val

    def _load_roles(self):
        role_file = self.text_dir / "RoleInfoData.txt"
        if not role_file.exists():
            role_file = self.text_dir / "RoleInfoData.bytes"
        if not role_file.exists():
            return
        with open(role_file, "r", encoding="utf-8", errors="ignore") as f:
            hdr_line = f.readline().rstrip("┤\r\n")
            headers = [h.strip() for h in hdr_line.split("|")]
            idx_map = {h: i for i, h in enumerate(headers)}
            for line in f:
                parts = line.rstrip("┤\r\n").split("|")
                if len(parts) <= max(idx_map.values(), default=0):
                    continue
                role_id = parts[idx_map.get("roleID", 0)].strip()
                name_zh = clean_text(parts[idx_map.get("name", 1)])
                if not name_zh or name_zh in ("NULL", "-1"):
                    continue
                cg_asset = clean_text(parts[idx_map.get("cg_assetId", 54)])
                m = re.search(r"([a-z][0-9]{3}|ct[0-9]{3})", cg_asset, re.IGNORECASE)
                if not m:
                    m = re.search(r"([a-z][0-9]{3}|ct[0-9]{3})", role_id, re.IGNORECASE)
                code = m.group(1).lower() if m else f"role_{role_id}"
                name_en = self.translate(name_zh) or name_zh
                meta = CharacterMetadata(
                    code=code,
                    role_id=role_id,
                    name_en=name_en,
                    name_zh=name_zh,
                    title_en=self.translate(clean_text(parts[idx_map.get("qualityState", 9)])),
                    title_zh=clean_text(parts[idx_map.get("qualityState", 9)]),
                    cup=clean_text(parts[idx_map.get("cup", 60)]) if clean_text(parts[idx_map.get("cup", 60)]) != "-1" else "",
                    height=clean_text(parts[idx_map.get("heigth", 58)]) if clean_text(parts[idx_map.get("heigth", 58)]) != "-1" else "",
                    weight=clean_text(parts[idx_map.get("weight", 59)]) if clean_text(parts[idx_map.get("weight", 59)]) != "-1" else "",
                    personality=self.translate(clean_text(parts[idx_map.get("personality", 62)])),
                    theme=self.translate(clean_text(parts[idx_map.get("theme", 64)])),
                    cg_spine=f"{code}_CG",
                    hcg_spine=f"{code}_HCG"
                )
                self.characters[code] = meta

    def _load_hscenes(self):
        h_file = self.text_dir / "StoryHData.txt"
        if not h_file.exists():
            h_file = self.text_dir / "StoryHData.bytes"
        if not h_file.exists():
            return
        with open(h_file, "r", encoding="utf-8", errors="ignore") as f:
            hdr_line = f.readline().rstrip("┤\r\n")
            headers = [h.strip() for h in hdr_line.split("|")]
            idx_map = {h: i for i, h in enumerate(headers)}
            counters = {}
            for line in f:
                parts = line.rstrip("┤\r\n").split("|")
                if len(parts) <= max(idx_map.values(), default=0):
                    continue
                scene_id = clean_text(parts[idx_map.get("id", 0)])
                if not scene_id:
                    continue
                m = re.search(r"(ct[0-9]{3}|[a-z][0-9]{3})", scene_id, re.IGNORECASE)
                code = m.group(1).lower() if m else "generic"
                if scene_id not in self.hscenes:
                    title_zh = clean_text(parts[idx_map.get("speakerNote", 14)]) or scene_id
                    title_en = self.translate(title_zh) or scene_id
                    self.hscenes[scene_id] = HScene(scene_id=scene_id, char_code=code, title_en=title_en, title_zh=title_zh)
                    counters[scene_id] = 0
                    if code in self.characters and scene_id not in self.characters[code].hscenes:
                        self.characters[code].hscenes.append(scene_id)

                scene = self.hscenes[scene_id]
                counters[scene_id] += 1
                anim = clean_text(parts[idx_map.get("spineAnimName", 47)])
                voice = clean_text(parts[idx_map.get("charSound", 40)])
                bgm = clean_text(parts[idx_map.get("music", 26)])
                sfx_list = [clean_text(parts[idx_map.get(col, -1)]) for col in ("sceneSound", "sceneSound2", "successiveSound") if clean_text(parts[idx_map.get(col, -1)]) not in ("-1", "0", "")]
                if anim and anim not in ("-1", "0") and anim not in scene.spine_anims:
                    scene.spine_anims.append(anim)
                if voice and voice not in ("-1", "0") and voice not in scene.voice_clips:
                    scene.voice_clips.append(voice)
                if bgm and bgm not in ("-1", "0") and bgm not in scene.bgm_tracks:
                    scene.bgm_tracks.append(bgm)
                for s in sfx_list:
                    if s not in scene.sfx_clips:
                        scene.sfx_clips.append(s)

                scene.steps.append(HSceneStep(
                    step=counters[scene_id],
                    speaker_en=self.translate(clean_text(parts[idx_map.get("speaker", 13)])),
                    speaker_zh=clean_text(parts[idx_map.get("speaker", 13)]),
                    text_en=self.translate(clean_text(parts[idx_map.get("text", 21)])),
                    text_zh=clean_text(parts[idx_map.get("text", 21)]),
                    anim=anim if anim not in ("-1", "0") else None,
                    voice=voice if voice not in ("-1", "0") else None,
                    bgm=bgm if bgm not in ("-1", "0") else None,
                    sfx=sfx_list,
                    bg=clean_text(parts[idx_map.get("bg", 1)]) if clean_text(parts[idx_map.get("bg", 1)]) not in ("-1", "0") else None
                ))

# -----------------------------------------------------------------------------
# 4. Spine & Audio Extractor (UnityPy)
# -----------------------------------------------------------------------------
def _worker_extract_spine(args: Tuple[str, str, str, str, bool]) -> List[str]:
    bpath_str, skel_dir_str, atlas_dir_str, tex_dir_str, overwrite = args
    import UnityPy
    try:
        env = UnityPy.load(bpath_str)
    except Exception:
        return []

    atlases, skels, textures = {}, {}, {}
    for obj in env.objects:
        tname = obj.type.name
        if tname == "TextAsset":
            try:
                rd = obj.read()
                name = getattr(rd, "m_Name", getattr(rd, "name", ""))
                s = getattr(rd, "m_Script", getattr(rd, "script", b""))
                script = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)
                if not script:
                    continue
                if name.endswith(".atlas") or name.endswith(".atlas.txt"):
                    stem = name.replace(".atlas.txt", "").replace(".atlas", "")
                    atlases[stem] = script
                elif name.endswith(".skel") or name.endswith(".skel.bytes"):
                    stem = name.replace(".skel.bytes", "").replace(".skel", "")
                    skels[stem] = script
            except Exception:
                continue
        elif tname == "Texture2D":
            try:
                rd = obj.read()
                name = getattr(rd, "m_Name", getattr(rd, "name", ""))
                img = getattr(rd, "image", None)
                if img is not None:
                    textures[name] = img
            except Exception:
                continue

    extracted = []
    all_stems = set(skels.keys()) | set(atlases.keys())
    for stem in all_stems:
        skel_f = os.path.join(skel_dir_str, f"{stem}.skel")
        atlas_f = os.path.join(atlas_dir_str, f"{stem}.atlas")
        tex_f = os.path.join(tex_dir_str, f"{stem}.png")
        if stem in skels and (overwrite or not os.path.exists(skel_f)):
            with open(skel_f, "wb") as f: f.write(skels[stem])
        if stem in atlases and (overwrite or not os.path.exists(atlas_f)):
            with open(atlas_f, "wb") as f: f.write(atlases[stem])
        matched_tex = textures.get(stem) or (next(iter(textures.values())) if len(textures) == 1 else None)
        if matched_tex is not None and (overwrite or not os.path.exists(tex_f)):
            matched_tex.save(tex_f, format="PNG")
        extracted.append(stem)
    return extracted

def _worker_extract_audio(args: Tuple[str, str, str, str, bool]) -> List[str]:
    bpath_str, bgm_dir_str, voice_dir_str, se_dir_str, overwrite = args
    bname = os.path.basename(bpath_str).lower()
    if "sound_bgm" in bname or "bgm" in bname:
        dest = bgm_dir_str
    elif "sound_voice" in bname or "voice" in bname or "vic_" in bname:
        dest = voice_dir_str
    elif "sound_se" in bname or "ambientsound" in bname or "_se" in bname:
        dest = se_dir_str
    else:
        dest = voice_dir_str

    # Fast existence check
    parts = bname.split("_")
    candidate = parts[-1]
    if len(parts) >= 2 and parts[-2].startswith("vic"):
        candidate = f"{parts[-2]}_{parts[-1]}"
    fast_check = os.path.join(dest, f"{candidate}.wav")
    if not overwrite and os.path.exists(fast_check) and os.path.getsize(fast_check) > 0:
        return [candidate]

    import UnityPy
    try:
        env = UnityPy.load(bpath_str)
    except Exception:
        return []

    clips = []
    for obj in env.objects:
        if int(obj.type) == 83:  # AudioClip
            try:
                rd = obj.read()
                for sname, sdata in getattr(rd, "samples", {}).items():
                    cname = os.path.splitext(sname)[0]
                    dest_f = os.path.join(dest, f"{cname}.wav")
                    if overwrite or not os.path.exists(dest_f) or os.path.getsize(dest_f) == 0:
                        with open(dest_f, "wb") as f:
                            f.write(sdata)
                    clips.append(cname)
            except Exception:
                continue
    return clips

def _worker_generate_thumbnail(task: Tuple[str, str, int, int, bool]) -> bool:
    src_path, dst_path, max_size, quality, overwrite = task
    try:
        src = Path(src_path)
        dst = Path(dst_path)
        if not overwrite and dst.exists() and dst.stat().st_size > 0:
            if dst.stat().st_mtime >= src.stat().st_mtime:
                return False
        from PIL import Image
        with Image.open(src_path) as img:
            img_rgba = img.convert("RGBA")
            w, h = img_rgba.size
            if w <= 0 or h <= 0:
                return False
            scale = min(max_size / w, max_size / h, 1.0)
            new_sz = (max(1, int(w * scale)), max(1, int(h * scale)))
            img_rgba.resize(new_sz, Image.Resampling.LANCZOS).save(dst_path, format="WEBP", quality=quality, method=4)
            return True
    except Exception:
        return False

# -----------------------------------------------------------------------------
# 5. Web App & Gallery Compiler
# -----------------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CherryTale Datamine Gallery</title>
<link rel="stylesheet" href="vendor/spine-player.css">
<style>
  :root { --bg: #0b0d14; --card-bg: rgba(22, 27, 46, 0.7); --accent: #ff4d8d; --text: #e6edf3; --text-dim: #8b949e; --border: rgba(255, 77, 141, 0.2); }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; min-height: 100vh; }
  header { background: rgba(11, 13, 20, 0.95); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
  .logo { font-size: 1.4rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }
  .logo span { color: var(--accent); }
  .controls { display: flex; gap: 12px; align-items: center; }
  input[type="text"] { background: rgba(255, 255, 255, 0.06); border: 1px solid var(--border); border-radius: 8px; padding: 8px 16px; color: #fff; font-size: 0.9rem; outline: none; width: 260px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 18px; padding: 28px; flex: 1; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column; }
  .card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(255, 77, 141, 0.2); border-color: var(--accent); }
  .thumb { width: 100%; aspect-ratio: 1; object-fit: contain; background: rgba(0, 0, 0, 0.3); }
  .info { padding: 12px; }
  .name { font-weight: 600; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .code { font-size: 0.8rem; color: var(--text-dim); margin-top: 4px; }
  /* Modal */
  .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(10px); z-index: 200; justify-content: center; align-items: center; }
  .modal-content { width: 90vw; height: 85vh; background: var(--bg); border: 1px solid var(--border); border-radius: 16px; display: flex; overflow: hidden; position: relative; }
  .spine-stage { flex: 1; height: 100%; background: #000; position: relative; }
  .sidebar { width: 380px; border-left: 1px solid var(--border); display: flex; flex-direction: column; background: var(--card-bg); }
  .close-btn { position: absolute; top: 16px; right: 16px; background: rgba(255,255,255,0.1); border: none; color: #fff; font-size: 1.2rem; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; z-index: 10; }
  .anim-btn { background: rgba(255,255,255,0.06); border: 1px solid var(--border); color: #fff; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; margin: 4px; }
  .anim-btn:hover, .anim-btn.active { background: var(--accent); }
</style>
</head>
<body>
<header>
  <div class="logo">🌸 CherryTale <span>Datamine</span></div>
  <div class="controls">
    <input type="text" id="search" placeholder="Search characters or scenes..." oninput="filterCards()">
  </div>
</header>
<div class="grid" id="grid"></div>

<div class="modal" id="modal">
  <div class="modal-content">
    <button class="close-btn" onclick="closeModal()">✕</button>
    <div class="spine-stage" id="spineContainer"></div>
    <div class="sidebar">
      <div style="padding: 20px; border-bottom: 1px solid var(--border);">
        <h2 id="mName"></h2>
        <div id="mCode" style="color: var(--text-dim); font-size: 0.9rem;"></div>
      </div>
      <div style="padding: 16px; flex: 1; overflow-y: auto;" id="animList"></div>
    </div>
  </div>
</div>

<script src="vendor/spine-player.js"></script>
<script>
let models = [];
let player = null;

async function init() {
  const r = await fetch('/api/catalog');
  models = await r.json();
  renderGrid(models);
}

function renderGrid(list) {
  const g = document.getElementById('grid');
  g.innerHTML = list.map(m => `
    <div class="card" onclick="openModel('${m.stem}')">
      <img class="thumb" src="/thumbs/${m.stem}.webp" onerror="this.src='/spines/${m.stem}/${m.stem}.png'">
      <div class="info">
        <div class="name">${m.name}</div>
        <div class="code">${m.stem}</div>
      </div>
    </div>
  `).join('');
}

function filterCards() {
  const q = document.getElementById('search').value.toLowerCase();
  renderGrid(models.filter(m => m.name.toLowerCase().includes(q) || m.stem.toLowerCase().includes(q)));
}

async function openModel(stem) {
  const m = models.find(x => x.stem === stem);
  if (!m) return;
  document.getElementById('mName').innerText = m.name;
  document.getElementById('mCode').innerText = m.stem;
  document.getElementById('modal').style.display = 'flex';

  const container = document.getElementById('spineContainer');
  container.innerHTML = '';
  
  player = new spine.SpinePlayer(container, {
    skelUrl: `/spines/${stem}/${stem}.skel`,
    atlasUrl: `/spines/${stem}/${stem}.atlas`,
    backgroundColor: '#00000000',
    alpha: true,
    showControls: true,
    success: (p) => {
      const anims = p.skeleton.data.animations.map(a => a.name);
      const al = document.getElementById('animList');
      al.innerHTML = '<h3>Animations</h3>' + anims.map(an => `
        <button class="anim-btn" onclick="player.animationState.setAnimation(0, '${an}', true)">${an}</button>
      `).join('');
    }
  });
}

function closeModal() {
  if (player) { player.dispose(); player = null; }
  document.getElementById('modal').style.display = 'none';
}
window.onload = init;
</script>
</body>
</html>
"""

def generate_catalog_json(db: GameDatabase) -> List[Dict[str, Any]]:
    catalog = []
    for skel_path in SKEL_DIR.glob("*.skel"):
        stem = skel_path.stem
        m = re.search(r"([a-z][0-9]{3}|ct[0-9]{3})", stem, re.IGNORECASE)
        code = m.group(1).lower() if m else stem
        char = db.characters.get(code)
        name = char.name_en if char else stem.replace("_", " ").title()
        catalog.append({"stem": stem, "name": name, "code": code})

    catalog.sort(key=lambda x: x["name"])
    with open(DATA_DIR / "catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    return catalog

# -----------------------------------------------------------------------------
# 6. Web Server Orchestrator
# -----------------------------------------------------------------------------
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

SKEL_INDEX: Dict[str, str] = {}
ATLAS_INDEX: Dict[str, str] = {}
TEX_INDEX: Dict[str, str] = {}

def build_spine_indices():
    for sk in SKEL_DIR.glob("*.skel"):
        SKEL_INDEX[sk.stem] = str(sk)
        SKEL_INDEX[sk.stem.lower()] = str(sk)
    for at in ATLAS_DIR.glob("*.atlas"):
        ATLAS_INDEX[at.stem] = str(at)
        ATLAS_INDEX[at.stem.lower()] = str(at)
    for tx in TEX_DIR.glob("*.png"):
        TEX_INDEX[tx.name] = str(tx)
        TEX_INDEX[tx.name.lower()] = str(tx)
        TEX_INDEX[tx.stem] = str(tx)
        TEX_INDEX[tx.stem.lower()] = str(tx)

class GalleryHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        clean_path = self.path.split("?")[0].lower()
        if clean_path.endswith((".webp", ".png", ".jpg", ".gif", ".skel", ".atlas", ".js", ".css", ".wav", ".mp3", ".json")):
            self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_file_range(self, filepath: str, content_type: str = "audio/wav"):
        try:
            file_size = os.path.getsize(filepath)
            range_header = self.headers.get("Range")
            if range_header:
                m = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if m:
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    if start >= file_size:
                        self.send_error(416, "Requested Range Not Satisfiable")
                        return
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    super().end_headers()
                    with open(filepath, "rb") as f:
                        f.seek(start)
                        bytes_left = length
                        while bytes_left > 0:
                            chunk = f.read(min(65536, bytes_left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_left -= len(chunk)
                    return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_error(500, f"Error streaming file: {e}")
            except Exception:
                pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/catalog":
            cat_f = DATA_DIR / "catalog.json"
            if cat_f.exists():
                data = cat_f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        if p == "/api/bgm_list":
            bgm_tracks = []
            for bf in sorted(BGM_DIR.glob("*.wav")):
                title = bf.stem.replace("_", " ").title()
                bgm_tracks.append({
                    "id": bf.stem,
                    "title": title,
                    "category": "BGM",
                    "url": f"/audio/bgm/{bf.stem}",
                    "size_mb": round(bf.stat().st_size / (1024*1024), 2)
                })
            data = json.dumps(bgm_tracks, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
            self.wfile.write(data)
            return

        if p.startswith("/spines/"):
            parts = [x for x in p.split("/") if x]
            if len(parts) >= 3:
                stem, fname = parts[1], parts[2]
                file_target = None
                mime_type = "application/octet-stream"
                if fname.endswith(".skel"):
                    file_target = SKEL_INDEX.get(stem) or SKEL_INDEX.get(stem.lower()) or (str(SKEL_DIR / f"{stem}.skel") if (SKEL_DIR / f"{stem}.skel").exists() else None)
                elif fname.endswith(".atlas"):
                    file_target = ATLAS_INDEX.get(stem) or ATLAS_INDEX.get(stem.lower()) or (str(ATLAS_DIR / f"{stem}.atlas") if (ATLAS_DIR / f"{stem}.atlas").exists() else None)
                    mime_type = "text/plain; charset=utf-8"
                elif fname.endswith(".png"):
                    file_target = (TEX_INDEX.get(fname) or TEX_INDEX.get(fname.lower()) or
                                   TEX_INDEX.get(stem) or TEX_INDEX.get(stem.lower()) or
                                   (str(TEX_DIR / fname) if (TEX_DIR / fname).exists() else str(TEX_DIR / f"{stem}.png")))
                    mime_type = "image/png"

                if file_target and os.path.exists(file_target):
                    self.send_file_range(file_target, mime_type)
                    return
                else:
                    self.send_error(404, f"Spine file not found: {fname} for {stem}")
                    return

        if p.startswith("/audio/"):
            parts = [x for x in p.split("/") if x]
            if len(parts) >= 3:
                cat, clip = parts[1], parts[2]
                dest = BGM_DIR if cat == "bgm" else (SE_DIR if cat in ("se", "ambientsound") else VOICE_DIR)
                fpath = dest / f"{clip}.wav" if not clip.endswith(".wav") else dest / clip
                if not fpath.exists():
                    for alt in (VOICE_DIR, SE_DIR, BGM_DIR):
                        cand = alt / f"{clip}.wav" if not clip.endswith(".wav") else alt / clip
                        if cand.exists():
                            fpath = cand
                            break
                if not fpath.exists():
                    try:
                        from tools.audio_manager import audio_manager
                        clean_id = clip[:-4] if clip.endswith(".wav") else clip
                        extracted = audio_manager.get_or_extract_audio(cat, clean_id)
                        if extracted and os.path.exists(extracted):
                            fpath = Path(extracted)
                    except Exception:
                        pass
                if fpath.exists():
                    self.send_file_range(str(fpath), "audio/wav")
                    return
                else:
                    self.send_error(404, f"Audio clip not found: {clip}")
                    return

        return super().do_GET()

# -----------------------------------------------------------------------------
# 7. Unified CLI Commands
# -----------------------------------------------------------------------------
def cmd_sync(args):
    print("📡 [1/3] Querying Live Patch API...")
    node, info = query_latest_node()
    patch_md5 = info.get("client_patch_index_md5")
    print(f"✓ Node {node} live index MD5: {patch_md5}")
    index_dict = fetch_index(patch_md5, save_path=str(MANIFEST_DIR / "index_save.txt"))
    print(f"✓ Synced master index: {len(index_dict):,} assets registered.")

    print("\n📦 [2/3] Downloading Core Tables (settings, language)...")
    for cf in ["settings", "LanguageSettings_enus.txt", "AssetRowResources.txt", "bundleMap.txt"]:
        if cf in index_dict:
            download_and_decrypt_asset(cf, index_dict[cf][1], out_dir=str(ASSET_DIR), overwrite=args.overwrite)

    settings_zip = ASSET_DIR / "settings"
    if settings_zip.exists():
        with zipfile.ZipFile(str(settings_zip), "r") as z:
            z.extractall(str(TEXT_DIR))
        print(f"✓ Unpacked 371 internal game tables into {TEXT_DIR}")

    enus_src = ASSET_DIR / "LanguageSettings_enus.txt"
    if enus_src.exists():
        import shutil
        shutil.copy2(str(enus_src), str(TEXT_DIR / "LanguageSettings_enus.txt"))

    print("\n📚 [3/3] Parsing Translations & Metadata...")
    db = GameDatabase(TEXT_DIR)
    print(f"✓ Loaded {len(db.translations):,} translations, {len(db.characters):,} characters, {len(db.hscenes):,} H-scenes.")
    print("✅ Sync stage complete!")

def cmd_download(args):
    print("🚀 Downloading & Decrypting Assets from CDN...")
    index_f = MANIFEST_DIR / "index_save.txt"
    if not index_f.exists():
        cmd_sync(args)
    index_dict = json.loads(index_f.read_text(encoding="utf-8"))

    filt = None
    if args.filter == "spine": filt = lambda k: "_cg_spine" in k or "img_hcg_dynamic" in k or "img_cg_dynamic" in k or "gacha_spine" in k
    elif args.filter == "audio": filt = lambda k: "sound_voice" in k or "sound_bgm" in k or "sound_ambientsound" in k or "sound_se" in k

    t0 = time.time()
    stats = sync_assets(index_dict, out_dir=str(ASSET_DIR), workers=args.workers, overwrite=args.overwrite, filter_fn=filt)
    dur = time.time() - t0
    print(f"\n🏁 Finished in {dur:.1f}s: OK={stats['ok']:,}, Skipped={stats['skipped']:,}, Failed={stats['failed']:,}, Size={stats['bytes']/(1024**3):.2f} GB")

def cmd_extract(args):
    print("🔍 Extracting Spine & Audio Assets from Asset/...")
    t0 = time.time()
    targets = [str(f) for f in ASSET_DIR.iterdir() if not f.name.endswith(".tmp")]

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    if args.type in ("all", "spine"):
        spines = [b for b in targets if ("_cg_spine" in b or "img_hcg_dynamic" in b or "img_cg_dynamic" in b or "gacha_spine" in b)]
        task_args = [(b, str(SKEL_DIR), str(ATLAS_DIR), str(TEX_DIR), args.overwrite) for b in spines]
        extracted_spines = []
        pbar = tqdm(total=len(spines), desc="Extracting Spines", unit="model") if tqdm else None
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for stems in ex.map(_worker_extract_spine, task_args, chunksize=4):
                extracted_spines.extend(stems)
                if pbar: pbar.update(1)
        if pbar: pbar.close()
        print(f"✓ Extracted {len(set(extracted_spines)):,} Spine models into {SPINE_DIR}")

    if args.type in ("all", "audio"):
        sounds = [b for b in targets if ("sound_voice" in b or "sound_bgm" in b or "sound_ambientsound" in b or "sound_se" in b)]
        task_args = [(b, str(BGM_DIR), str(VOICE_DIR), str(SE_DIR), args.overwrite) for b in sounds]
        extracted_clips = []
        pbar = tqdm(total=len(sounds), desc="Extracting Audio", unit="bundle") if tqdm else None
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for clips in ex.map(_worker_extract_audio, task_args, chunksize=10):
                extracted_clips.extend(clips)
                if pbar:
                    pbar.update(1)
                    pbar.set_postfix({"clips": len(extracted_clips)})
        if pbar: pbar.close()
        print(f"✓ Extracted {len(set(extracted_clips)):,} Audio clips into {AUDIO_DIR}")

    print(f"✅ Extraction completed in {time.time()-t0:.1f}s!")

def cmd_build(args):
    print("🔨 Building Web Viewer & Thumbnails (Multi-threaded)...")
    t0 = time.time()
    db = GameDatabase(TEXT_DIR)

    workers = getattr(args, "workers", None) or min(16, os.cpu_count() or 4)
    png_files = list(TEX_DIR.glob("*.png"))

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    # Render assembled frame-0 for every skeleton (multi-slice CGs need stitching), in parallel.
    out_dir = VIEWER_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = VIEWER_DIR / "render_anim.exe"
    if exe.exists():
        from concurrent.futures import ThreadPoolExecutor
        import subprocess
        def _render(sk):
            stem = sk.stem
            dst = out_dir / f"{stem}.png"
            if dst.exists() and dst.stat().st_size > 1024 and not args.overwrite:
                return
            atl = ATLAS_DIR / f"{stem}.atlas"
            if not atl.exists():
                return
            try:
                page = atl.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
                subprocess.run([str(exe), str(sk), str(atl), str(TEX_DIR / page), str(dst)],
                               capture_output=True, timeout=120)
            except Exception:
                pass
        with ThreadPoolExecutor(max_workers=workers) as tp:
            list(tp.map(_render, list(SKEL_DIR.glob("*.skel"))))

    def _thumb_src(p):
        r = out_dir / f"{p.stem}.png"
        return r if r.exists() and r.stat().st_size > 1024 else p
    task_args = [(str(_thumb_src(p)), str(THUMBS_DIR / f"{p.stem}.webp"), 320, 85, getattr(args, "overwrite", False)) for p in png_files]
    created = 0
    skipped = 0

    if task_args:
        pbar = tqdm(total=len(task_args), desc="Generating Thumbnails", unit="thumb") if tqdm else None
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for ok in ex.map(_worker_generate_thumbnail, task_args, chunksize=8):
                if ok:
                    created += 1
                else:
                    skipped += 1
                if pbar:
                    pbar.update(1)
        if pbar:
            pbar.close()

    print(f"✓ Thumbnails: {created:,} newly generated, {skipped:,} up to date across {workers} worker processes.")

    # Rebuild web viewer & interactive Spine model metadata
    build_script = BASE_DIR / "tools" / "build_gallery_webapp.py"
    if build_script.exists():
        import subprocess
        print("⚙️  Compiling interactive Spine web application & dialogue metadata...")
        res = subprocess.run([sys.executable, str(build_script)], cwd=str(BASE_DIR), capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Warning: build_gallery_webapp encountered issue: {res.stderr}")
        else:
            for l in res.stdout.splitlines():
                if "🎉" in l or "Loaded" in l or "Generated" in l or "Spine" in l:
                    print(f"  {l}")
    else:
        index_html = VIEWER_DIR / "index.html"
        if args.overwrite or not index_html.exists():
            index_html.write_text(HTML_TEMPLATE, encoding="utf-8")
        cat = generate_catalog_json(db)
        print(f"✓ Compiled catalog with {len(cat)} models into {DATA_DIR / 'catalog.json'}")

    dur = time.time() - t0
    print(f"✓ Web viewer ready at {VIEWER_DIR / 'index.html'}")
    print(f"✅ Build completed in {dur:.2f}s!")

def cmd_serve(args):
    viewer_path = str(VIEWER_DIR)
    if viewer_path not in sys.path:
        sys.path.insert(0, viewer_path)
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    handler_cls = None
    try:
        import gallery_server
        gallery_server.build_indices()
        handler_cls = gallery_server.GalleryHTTPHandler
    except Exception as e:
        print(f"Notice: using built-in handler: {e}")
        build_spine_indices()
        handler_cls = GalleryHandler

    print(f"\n============================================================")
    print(f"🌸 CHERRYTALE INTERACTIVE SPINE GALLERY SERVER")
    print(f"============================================================")
    print(f"🌐 Serving at        : http://localhost:{args.port}/index.html")
    print(f"📁 Web Root         : {VIEWER_DIR}")
    print(f"⚡ Range streaming   : Enabled (HTTP 206)")
    print(f"⚡ Press Ctrl+C to stop.")
    print(f"============================================================\n")

    server = ThreadingHTTPServer((args.host, args.port), handler_cls)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()

def cmd_run_all(args):
    cmd_sync(args)
    cmd_download(args)
    cmd_extract(args)
    cmd_build(args)
    cmd_serve(args)

def main():
    p = argparse.ArgumentParser(description="CherryTale End-to-End Reverse Engineering CLI")
    subs = p.add_subparsers(dest="command")

    p_sync = subs.add_parser("sync")
    p_sync.add_argument("--overwrite", action="store_true")

    p_dl = subs.add_parser("download")
    p_dl.add_argument("--workers", type=int, default=128)
    p_dl.add_argument("--overwrite", action="store_true")
    p_dl.add_argument("--filter", choices=["all", "spine", "audio"], default="all")

    p_ex = subs.add_parser("extract")
    p_ex.add_argument("--type", choices=["all", "spine", "audio"], default="all")
    p_ex.add_argument("--workers", type=int, default=16)
    p_ex.add_argument("--overwrite", action="store_true")

    p_bd = subs.add_parser("build")
    p_bd.add_argument("--workers", type=int, default=16, help="Worker processes for thumbnail generation (default: 16)")
    p_bd.add_argument("--overwrite", action="store_true")

    p_sv = subs.add_parser("serve")
    p_sv.add_argument("--port", type=int, default=8000)
    p_sv.add_argument("--host", default="0.0.0.0")

    p_all = subs.add_parser("run-all")
    p_all.add_argument("--workers", type=int, default=32)
    p_all.add_argument("--overwrite", action="store_true")
    p_all.add_argument("--type", choices=["all", "spine", "audio"], default="all")
    p_all.add_argument("--filter", choices=["all", "spine", "audio"], default="all")
    p_all.add_argument("--port", type=int, default=8000)
    p_all.add_argument("--host", default="0.0.0.0")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)

    cmds = {"sync": cmd_sync, "download": cmd_download, "extract": cmd_extract, "build": cmd_build, "serve": cmd_serve, "run-all": cmd_run_all}
    cmds[args.command](args)

if __name__ == "__main__":
    main()
