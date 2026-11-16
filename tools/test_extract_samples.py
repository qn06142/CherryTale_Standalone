import os
import sys
import ssl
import json
import urllib.request
import lz4.block

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.fetch_and_extract_hcg import decode_bundle_stream
from UnityPy import Environment
from UnityPy.streams import EndianBinaryReader
from UnityPy.files.SerializedFile import SerializedFile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, "hcg_manifest", "access_token.txt")
TOKEN = open(TOKEN_FILE, encoding="utf-8").read().strip()
AUDIO_OUT = os.path.join(BASE_DIR, "dump", "audio")
os.makedirs(AUDIO_OUT, exist_ok=True)

with open(os.path.join(BASE_DIR, 'hcg_manifest', 'index_save.txt'), 'r', encoding='utf-8') as f:
    manifest = json.load(f)

test_targets = [
    # March Hare HCG loop voice
    'assets_resources_honly_baseassets_sound_voice_b004_01_hcg01_sh_vic_b004_01_012_1_loop',
    # March Hare Touch voices
    'assets_resources_honly_baseassets_sound_charvoicetouch_b004_01_vic_b004_01_tou_01',
    'assets_resources_honly_baseassets_sound_charvoicetouch_b004_01_vic_b004_01_tou_02',
    # Sex BGMs
    'assets_resources_versionshare_baseassets_sound_bgm_music_sex_music_sex_01',
    'assets_resources_versionshare_baseassets_sound_bgm_music_sex_music_sex_02',
    'assets_resources_versionshare_baseassets_sound_bgm_music_sex_music_sex_03',
]

SSL_CTX = ssl._create_unverified_context()

for bundle_name in test_targets:
    if bundle_name not in manifest:
        print(f"Bundle not in manifest: {bundle_name}")
        continue
    size, md5 = manifest[bundle_name]
    url = f"https://pfdd.88kongque.com/patch/files/{bundle_name}.{md5}"
    print(f"Downloading {bundle_name} ({size} bytes)...")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
        "Accept": "*/*"
    })
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as r:
            raw_bytes = r.read()
    except Exception as e:
        print(f"  Download error: {e}")
        continue

    stream, entries = decode_bundle_stream(raw_bytes)
    if not stream or not entries:
        print("  Decode error")
        continue

    env = Environment()
    for entry_name, offset, esize, flags in entries:
        sub_stream = stream[offset : offset + esize]
        reader = EndianBinaryReader(sub_stream)
        clean_name = entry_name.split("/")[-1]
        env.register_cab(clean_name, reader)
        if clean_name.endswith('.resource'):
            env.register_cab(clean_name[:-9], reader)
            env.register_cab(clean_name, reader)
        elif clean_name.endswith('.resS'):
            env.register_cab(clean_name[:-5], reader)

    main_entry = (entries[0][0], entries[0][1], entries[0][2])
    sf = SerializedFile(EndianBinaryReader(stream[main_entry[1] : main_entry[1] + main_entry[2]]), main_entry[0])
    sf.environment = env

    for pid, obj in sf.objects.items():
        if int(obj.type) == 83:  # AudioClip
            rd = obj.read()
            clip_name = getattr(rd, "m_Name", "") or "audio"
            samples = getattr(rd, "samples", {})
            if isinstance(samples, dict):
                for sname, sdata in samples.items():
                    out_file = os.path.join(AUDIO_OUT, sname)
                    with open(out_file, "wb") as out_f:
                        out_f.write(sdata)
                    print(f"  Extracted: {sname} ({len(sdata)} bytes)")

print("\nDone testing sample audio downloads!")
