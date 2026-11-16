import os
import ssl
import urllib.request
import json
import lz4.block

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, "hcg_manifest", "access_token.txt")
TOKEN = open(TOKEN_FILE, encoding="utf-8").read().strip()

with open('hcg_manifest/index_save.txt', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Find a b004 voice or bgm bundle
target_name = None
for k in manifest.keys():
    if 'b004_01' in k and 'voice' in k:
        target_name = k
        break

if not target_name:
    target_name = 'assets_resources_versionshare_baseassets_sound_bgm_a01_a01_bpm140_210_2mix'

size, md5 = manifest[target_name]
print(f"Target bundle: {target_name} ({size} bytes, md5={md5})")

url = f"https://pfdd.88kongque.com/patch/files/{target_name}.{md5}"
req = urllib.request.Request(url, headers={
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
    "Accept": "*/*"
})

SSL_CTX = ssl._create_unverified_context()
try:
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as r:
        data = r.read()
    print(f"Downloaded successfully: {len(data)} bytes! Status: {r.status}")
    with open('test_audio_bundle.bundle', 'wb') as f:
        f.write(data)
except Exception as e:
    print(f"Download failed: {e}")
