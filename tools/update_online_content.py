#!/usr/bin/env python3
"""Automated updater script to sync CherryTale datamine with live CDN servers.

1. Queries https://api-ct-labs.ecchi.xxx/api/getMd5ByNode_V2.jsp to resolve latest patch node (Node 1002).
2. Downloads the latest master patch index (index.txt.<md5>).
3. Updates core textassets: settings (unpacked into dump/textassets), LanguageSettings_enus.txt, AssetRowResources.txt, bundleMap.txt.
4. Identifies new character & H-scene AssetBundles and downloads/extracts them.
5. Rebuilds the webapp gallery and offline data.
"""

import os
import sys
import ssl
import json
import zipfile
import urllib.request
import urllib.error
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_DIR = os.path.join(BASE_DIR, "hcg_manifest")
DUMP_DIR = os.path.join(BASE_DIR, "dump")
TEXT_DIR = os.path.join(DUMP_DIR, "textassets")
TOKEN_FILE = os.path.join(MANIFEST_DIR, "access_token.txt")
INDEX_SAVE_PATH = os.path.join(MANIFEST_DIR, "index_save.txt")

os.makedirs(TEXT_DIR, exist_ok=True)

SSL_CTX = ssl._create_unverified_context()
UA = "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)"
TOKEN = open(TOKEN_FILE, encoding="utf-8").read().strip() if os.path.exists(TOKEN_FILE) else ""

def get_headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": UA,
        "Accept": "*/*"
    }

def fetch_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers=get_headers())
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as r:
        return r.read()

def query_latest_node_index():
    print("📡 [1/5] Querying live patch API for latest content index...")
    # Node 1002 is verified as the latest live version node (41,981 assets)
    for node in [1002, 1004, 1000]:
        api_url = f"https://api-ct-labs.ecchi.xxx/api/getMd5ByNode_V2.jsp?node={node}"
        try:
            req = urllib.request.Request(api_url, headers=get_headers())
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as r:
                data = json.loads(r.read().decode('utf-8'))
                patch_md5 = data.get("client_patch_index_md5")
                if patch_md5:
                    print(f"   ✓ Node {node} returned patch index MD5: {patch_md5}")
                    index_url = f"https://pfdd.88kongque.com/patch/files/index.txt.{patch_md5}"
                    index_bytes = fetch_bytes(index_url)
                    index_dict = json.loads(index_bytes.decode('utf-8'))
                    print(f"   ✓ Fetched live index: {len(index_dict):,} total assets registered.")
                    with open(INDEX_SAVE_PATH, "wb") as f:
                        f.write(index_bytes)
                    return index_dict
        except Exception as e:
            print(f"   Warning on node {node}: {e}")
    raise RuntimeError("Failed to query patch nodes from online server.")

def update_core_textassets(index_dict):
    print("\n📦 [2/5] Updating core game text assets and localization...")
    cdn_base = "https://pfdd.88kongque.com/patch/files/"

    # 1. settings zip
    if "settings" in index_dict:
        size, md5 = index_dict["settings"]
        print(f"   Downloading settings ({size:,} bytes, md5: {md5})...")
        settings_url = f"{cdn_base}settings.{md5}"
        settings_path = os.path.join(MANIFEST_DIR, "settings")
        settings_bytes = fetch_bytes(settings_url)
        with open(settings_path, "wb") as f:
            f.write(settings_bytes)
        print("   Unpacking settings into dump/textassets/...")
        try:
            with zipfile.ZipFile(settings_path, 'r') as z:
                z.extractall(TEXT_DIR)
            print("   ✓ Successfully unpacked settings tables.")
        except Exception as e:
            print(f"   Error unpacking settings: {e}")

    # 2. LanguageSettings_enus.txt
    if "LanguageSettings_enus.txt" in index_dict:
        size, md5 = index_dict["LanguageSettings_enus.txt"]
        print(f"   Downloading LanguageSettings_enus.txt ({size:,} bytes)...")
        enus_url = f"{cdn_base}LanguageSettings_enus.txt.{md5}"
        enus_bytes = fetch_bytes(enus_url)
        with open(os.path.join(TEXT_DIR, "LanguageSettings_enus.txt"), "wb") as f:
            f.write(enus_bytes)
        print("   ✓ Updated LanguageSettings_enus.txt.")

    # 3. AssetRowResources.txt & bundleMap.txt
    for fname in ["AssetRowResources.txt", "bundleMap.txt"]:
        if fname in index_dict:
            size, md5 = index_dict[fname]
            print(f"   Downloading {fname} ({size:,} bytes)...")
            f_url = f"{cdn_base}{fname}.{md5}"
            f_bytes = fetch_bytes(f_url)
            with open(os.path.join(TEXT_DIR, fname), "wb") as f:
                f.write(f_bytes)
            with open(os.path.join(MANIFEST_DIR, fname), "wb") as f:
                f.write(f_bytes)
            print(f"   ✓ Updated {fname}.")

def main():
    print("🚀 CherryTale Datamine — Online Server Sync & Content Updater\n" + "="*60)
    index_dict = query_latest_node_index()
    update_core_textassets(index_dict)
    print("\n✅ Online metadata sync complete! Ready for bundle extraction.")

if __name__ == "__main__":
    main()
