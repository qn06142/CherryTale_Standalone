#!/usr/bin/env python3
"""High-Performance Bulk Asset Downloader & Decryptor for CherryTale.

Directly implements the official decryption specification.

1. Reads index_save.txt (all 41,981 indexed assets from live Node 1002).
2. Concurrently downloads each asset from pfdd.88kongque.com using persistent Keep-Alive connections.
3. Automatically decrypts on the fly:
   - UnityFS bundles: ChangeIdx (3-offset swap) + ChangeVersion (fake version replacement).
   - settings archive: ChangeIdx to restore standard zip structure.
   - Language text: Bit-reversal and byte-reversal.
4. Saves decrypted assets to local Asset/ directory.
5. Supports auto-resume, retries, and comprehensive progress tracking.
"""

import os
import sys
import json
import ssl
import time
import http.client
import urllib.parse
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "hcg_manifest", "index_save.txt")
TOKEN_PATH = os.path.join(BASE_DIR, "hcg_manifest", "access_token.txt")
DEFAULT_OUT_DIR = os.path.join(BASE_DIR, "Asset")
LOG_PATH = os.path.join(BASE_DIR, "download_failed.log")

CDN_HOST = "pfdd.88kongque.com"
CDN_BASE_PATH = "/patch/files/"
USER_AGENT = "UnityPlayer/2020.3.49f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)"

# Decryption constants from DecryptUnityAsset.cs
IDX_SWAP = (0x3FB, 0xD99, 0x197C)
FAKE_VER = b"2018.3.5f1\x00"
REAL_VER = b"2020.3.41f1"

# Bit reversal lookup table (0..255)
BIT_REV_TABLE = bytes(((b * 0x0202020202 & 0x010884422010) % 1023) for b in range(256))

SSL_CTX = ssl._create_unverified_context()

def decrypt_unityfs(raw: bytes) -> bytes:
    """Exact port of DecryptUnityAsset.ChangeVersion(DecryptUnityAsset.ChangeIdx(data))."""
    d = bytearray(raw)
    L = len(d)
    for off in IDX_SWAP:
        if L > off:
            other = L - off
            d[off], d[other] = d[other], d[off]

    head_len = min(0x1000, L)
    head = d[:head_len]
    if FAKE_VER in head:
        head = head.replace(FAKE_VER, REAL_VER)
        d[:len(head)] = head
    return bytes(d)

def decrypt_settings(raw: bytes) -> bytes:
    """Exact port of ChangeIdx on settings archive to restore valid PK zip."""
    d = bytearray(raw)
    L = len(d)
    for off in IDX_SWAP:
        if L > off:
            other = L - off
            d[off], d[other] = d[other], d[off]
    return bytes(d)

def decrypt_text_language(raw: bytes) -> bytes:
    """Exact port of Utility.Text.DecryptTxtWithReverByteAndBits."""
    return raw.translate(BIT_REV_TABLE)[::-1]

class WorkerThreadLocal(threading.local):
    conn: Optional[http.client.HTTPSConnection] = None

thread_local = WorkerThreadLocal()

def get_connection() -> http.client.HTTPSConnection:
    if thread_local.conn is None:
        thread_local.conn = http.client.HTTPSConnection(CDN_HOST, context=SSL_CTX, timeout=20)
    return thread_local.conn

def reset_connection():
    if getattr(thread_local, "conn", None) is not None:
        try:
            thread_local.conn.close()
        except Exception:
            pass
        thread_local.conn = None

def fetch_single_asset(name: str, expected_size: int, md5: str, out_path: str, token: str, overwrite: bool) -> Tuple[str, str, int]:
    """Download, decrypt, and save a single asset."""
    if not overwrite and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return (name, "SKIPPED", 0)

    quoted_name = urllib.parse.quote(name)
    url_path = f"{CDN_BASE_PATH}{quoted_name}.{md5}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            conn = get_connection()
            conn.request("GET", url_path, headers=headers)
            resp = conn.getresponse()
            if resp.status == 200:
                raw_data = resp.read()
                # Check sign & Decrypt
                if raw_data.startswith(b"UnityFS"):
                    dec_data = decrypt_unityfs(raw_data)
                elif name == "settings":
                    dec_data = decrypt_settings(raw_data)
                elif name.startswith("LanguageSettings_") and name.endswith(".txt"):
                    dec_data = decrypt_text_language(raw_data)
                else:
                    dec_data = raw_data

                # Write atomical temporary file then rename
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
                reset_connection()
                time.sleep(0.5 * attempt)
        except Exception as e:
            reset_connection()
            if attempt == max_attempts:
                return (name, f"ERR_{e.__class__.__name__}", 0)
            time.sleep(0.5 * attempt)

    return (name, "ERR_UNKNOWN", 0)

def main():
    parser = argparse.ArgumentParser(description="Bulk Download & Decrypt CherryTale Assets")
    parser.add_argument("--index", default=INDEX_PATH, help="Path to index_save.txt")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Destination directory for decrypted assets")
    parser.add_argument("--workers", type=int, default=32, help="Parallel worker threads (default 32)")
    parser.add_argument("--overwrite", action="store_true", help="Force redownload of existing files")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for testing")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"============================================================")
    print(f"🚀 CHERRYTALE FULL ASSET DOWNLOADER & DECRYPTOR")
    print(f"============================================================")
    print(f"📁 Destination Dir : {args.out}")
    print(f"📄 Index File       : {args.index}")
    print(f"⚡ Worker Threads  : {args.workers}")

    token = ""
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = f.read().strip()

    with open(args.index, "r", encoding="utf-8") as f:
        raw_index: Dict[str, list] = json.load(f)

    # Filter valid index entries
    items = []
    for k, v in raw_index.items():
        if isinstance(v, list) and len(v) >= 2:
            items.append((k, v[0], v[1]))

    total_items = len(items)
    if args.limit > 0:
        items = items[:args.limit]
        total_items = len(items)

    total_bytes_expected = sum(sz for _, sz, _ in items)
    print(f"📊 Total Assets    : {total_items:,} items ({total_bytes_expected / (1024**3):.2f} GB)")
    print(f"============================================================\n")

    t_start = time.time()
    ok_count = 0
    skip_count = 0
    fail_count = 0
    bytes_downloaded = 0
    failed_items = []

    pbar = tqdm(total=total_items, desc="Downloading", unit="asset", smoothing=0.1) if tqdm else None

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_single_asset,
                name,
                sz,
                md5,
                os.path.join(args.out, name),
                token,
                args.overwrite
            ): name for name, sz, md5 in items
        }

        for f in as_completed(futures):
            name, status, b_count = f.result()
            if status == "OK":
                ok_count += 1
                bytes_downloaded += b_count
            elif status == "SKIPPED":
                skip_count += 1
            else:
                fail_count += 1
                failed_items.append((name, status))

            if pbar:
                pbar.update(1)
                mb_so_far = bytes_downloaded / (1024 * 1024)
                dur = max(0.1, time.time() - t_start)
                speed = mb_so_far / dur
                pbar.set_postfix({"OK": ok_count, "Skip": skip_count, "Fail": fail_count, "MB/s": f"{speed:.1f}"})
            else:
                done = ok_count + skip_count + fail_count
                if done % 500 == 0 or done == total_items:
                    dur = max(0.1, time.time() - t_start)
                    mb_so_far = bytes_downloaded / (1024 * 1024)
                    speed = mb_so_far / dur
                    print(f"[{done:,}/{total_items:,}] OK={ok_count:,} Skip={skip_count:,} Fail={fail_count:,} | {speed:.2f} MB/s | {mb_so_far:.1f} MB downloaded")

    if pbar:
        pbar.close()

    elapsed = time.time() - t_start
    print(f"\n============================================================")
    print(f"🏁 DOWNLOAD COMPLETED in {elapsed / 60:.2f} minutes ({elapsed:.1f}s)")
    print(f"   ✓ Successfully Downloaded & Decrypted : {ok_count:,}")
    print(f"   ⚡ Already Existing / Skipped          : {skip_count:,}")
    print(f"   ❌ Failed Assets                        : {fail_count:,}")
    print(f"   📦 Data Downloaded                     : {bytes_downloaded / (1024**3):.2f} GB")
    print(f"   🚀 Average Throughput                  : {(bytes_downloaded / (1024*1024)) / max(0.1, elapsed):.2f} MB/s")
    print(f"============================================================")

    if failed_items:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            for n, s in failed_items:
                f.write(f"{n}\t{s}\n")
        print(f"⚠️ Logged {len(failed_items)} failed assets to {LOG_PATH}")

if __name__ == "__main__":
    main()
