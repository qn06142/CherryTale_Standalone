#!/usr/bin/env python3
"""Download, unpack, and process all 265 HCG (H-scene) Spine bundles from CherryTale CDN.

1. Downloads missing img_hcg_dynamic bundles from pfdd.88kongque.com.
2. Applies byte transformation (ChangeIdx + ChangeVersion) and decodes LZ4 blocks.
3. Extracts .skel, .atlas, and Texture2D (.png) into dump/hcg_art/.
4. Renders high-res setup poses (Frame 0) into viewer/out/.
"""

import os
import sys
import json
import ssl
import struct
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import lz4.block
from PIL import Image

import UnityPy
from UnityPy import Environment
from UnityPy.streams import EndianBinaryReader
from UnityPy.files.SerializedFile import SerializedFile
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_FILE = os.path.join(BASE_DIR, "hcg_manifest", "index_save.txt")
TOKEN_FILE = os.path.join(BASE_DIR, "hcg_manifest", "access_token.txt")
BUNDLE_DIR = os.path.join(BASE_DIR, "hcg_manifest", "hcg_bundles")
HCG_EXTRACTED = os.path.join(BASE_DIR, "hcg_manifest", "hcg_extracted")

SKEL_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "skel")
ATLAS_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "atlas")
TEX_DIR = os.path.join(BASE_DIR, "dump", "hcg_art", "textures")
OUT_DIR = os.path.join(BASE_DIR, "viewer", "out")
EXE = os.path.join(BASE_DIR, "viewer", "render_anim.exe")

for d in [BUNDLE_DIR, SKEL_DIR, ATLAS_DIR, TEX_DIR, OUT_DIR, HCG_EXTRACTED]:
    os.makedirs(d, exist_ok=True)

SSL_CTX = ssl._create_unverified_context()
CDN_BASE = "https://pfdd.88kongque.com/patch/files/"
USER_AGENT = "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)"
TOKEN = open(TOKEN_FILE, encoding="utf-8").read().strip()

IDX = (0x3FB, 0xD99, 0x197C)
FAKE = bytes([0x32, 0x30, 0x31, 0x38, 0x2E, 0x33, 0x2E, 0x35, 0x66, 0x31, 0x00])
REAL = bytes([0x32, 0x30, 0x32, 0x30, 0x2E, 0x33, 0x2E, 0x34, 0x31, 0x66, 0x31])

def change_idx(d):
    d = bytearray(d)
    L = len(d)
    for v in IDX:
        if L > v:
            t = d[v]
            d[v] = d[L - v]
            d[L - v] = t
    return d

def change_version(d):
    d = bytearray(d)
    head = d[:0x1000]
    i = 0
    while True:
        i = head.find(FAKE, i)
        if i < 0:
            break
        head[i:i + len(REAL)] = REAL
    d[:0x1000] = head
    return d

def download_bundle(name, md5):
    out_path = os.path.join(BUNDLE_DIR, f"{name}.bundle")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
        return out_path, "cached"
    url = f"{CDN_BASE}{name}.{md5}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": USER_AGENT,
        "Accept": "*/*"
    })
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=60) as r:
            data = r.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path, f"ok:{len(data)}"
    except Exception as e:
        return None, str(e)

def decode_bundle_stream(raw_data):
    if raw_data[:8] != b"UnityFS\x00":
        return None, None
    d = change_version(change_idx(raw_data))
    compBI = int.from_bytes(d[0x27:0x2a], 'big')
    uncompBI = int.from_bytes(d[0x2b:0x2e], 'big')
    try:
        bi = lz4.block.decompress(bytes(d[0x40:0x40 + compBI]), uncompressed_size=uncompBI)
    except Exception:
        return None, None
    cnt = struct.unpack(">I", bi[16:20])[0]
    blocks = []
    p = 20
    for _ in range(cnt):
        us, cs, fl = struct.unpack(">IIH", bi[p:p + 10])
        p += 10
        blocks.append((us, cs, fl))

    st = (0x40 + compBI + 15) & ~0xF
    stream = bytearray()
    cur = st
    for (us, cs, fl) in blocks:
        try:
            stream += lz4.block.decompress(bytes(d[cur:cur + cs]), uncompressed_size=us)
        except Exception:
            try:
                out = bytearray(us)
                lz4.block.decompress(bytes(d[cur:cur + cs]), uncompressed_size=us, output=out)
                stream += out
            except Exception:
                stream += bytes(d[cur:cur + cs])
        cur += cs

    # Parse directory entries from block directory
    entries = []
    try:
        np = 20 + 10 * cnt
        ncnt = struct.unpack(">I", bi[np:np + 4])[0]
        np += 4
        for _ in range(ncnt):
            offset, size, flags = struct.unpack(">QQI", bi[np:np + 20])
            np += 20
            e = bi.index(b'\x00', np)
            entry_name = bi[np:e].decode('utf-8', 'replace')
            np = e + 1
            entries.append((entry_name, offset, size, flags))
    except Exception:
        pass

    return bytes(stream), entries

def process_single_bundle(name, md5):
    bundle_path, status = download_bundle(name, md5)
    if not bundle_path:
        return {"name": name, "status": f"download_failed: {status}"}

    try:
        raw_bytes = open(bundle_path, "rb").read()
    except Exception as e:
        return {"name": name, "status": f"read_failed: {e}"}

    stream, entries = decode_bundle_stream(raw_bytes)
    if not stream or not entries:
        return {"name": name, "status": "decode_failed"}

    env = Environment()
    main_entry = None
    for entry_name, offset, size, flags in entries:
        sub_stream = stream[offset : offset + size]
        reader = EndianBinaryReader(sub_stream)
        clean_name = entry_name.split("/")[-1]
        env.register_cab(clean_name, reader)
        if clean_name.endswith('.resS'):
            base = clean_name[:-5]
            env.register_cab(base, reader)
            env.register_cab(base + '.resS', reader)
            env.register_cab(base + '.assets.resS', reader)
        else:
            env.register_cab(clean_name + '.resS', reader)
            env.register_cab(clean_name + '.assets.resS', reader)
            if main_entry is None:
                main_entry = (entry_name, offset, size)

    if main_entry is None:
        main_entry = (entries[0][0], entries[0][1], entries[0][2])

    sf = SerializedFile(EndianBinaryReader(stream[main_entry[1] : main_entry[1] + main_entry[2]]), main_entry[0])
    sf.environment = env

    skels_found = []
    atlases_found = []
    textures_found = []

    # First pass: TextAssets (.skel, .atlas)
    for pid, obj in sf.objects.items():
        if int(obj.type) == 49:  # TextAsset
            try:
                rd = obj.read()
                mn = getattr(rd, "m_Name", "") or ""
                data = rd.m_Script
                if isinstance(data, str):
                    try:
                        data = data.encode("utf-8", "surrogateescape")
                    except Exception:
                        data = data.encode("latin-1", "replace")
                if mn.endswith(".skel") or "skel" in mn.lower():
                    dest = os.path.join(SKEL_DIR, f"{mn if mn.endswith('.skel') else mn + '.skel'}")
                    with open(dest, "wb") as f:
                        f.write(data)
                    skels_found.append(mn)
                elif mn.endswith(".atlas"):
                    dest = os.path.join(ATLAS_DIR, mn)
                    with open(dest, "wb") as f:
                        f.write(data)
                    atlases_found.append(mn)
            except Exception:
                pass
        elif int(obj.type) == 28:  # Texture2D
            try:
                tex = obj.read()
                mn = getattr(tex, "m_Name", "") or f"tex_{pid}"
                img = get_image_from_texture2d(tex)
                tex_out = os.path.join(TEX_DIR, f"{mn}.png")
                img.save(tex_out)
                textures_found.append(mn)
            except Exception:
                pass

    return {
        "name": name,
        "status": "ok",
        "skels": skels_found,
        "atlases": atlases_found,
        "textures": textures_found
    }

def main():
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    # Select all img_hcg_dynamic targets
    targets = [(k, v[1]) for k, v in manifest_data.items() if "img_hcg_dynamic" in k]
    print(f"Total HCG targets to fetch & extract: {len(targets)}")

    done = 0
    skel_total = 0
    tex_total = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_single_bundle, name, md5): name for name, md5 in targets}
        for future in as_completed(futures):
            res = future.result()
            done += 1
            if res.get("status") == "ok":
                skel_total += len(res.get("skels", []))
                tex_total += len(res.get("textures", []))
            if done % 10 == 0 or done == len(targets):
                print(f"  [{done}/{len(targets)}] processed... (extracted {skel_total} skels, {tex_total} textures)")

    print(f"\n[DONE] Finished processing {done} HCG bundles! Extracted {skel_total} skels, {tex_total} textures.")

if __name__ == "__main__":
    main()
