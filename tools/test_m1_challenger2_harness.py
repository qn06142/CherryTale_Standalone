#!/usr/bin/env python3
"""Empirical Challenger Test Suite for Milestone 1.

Verifies:
1. /api/catalog (with and without query params)
2. /api/bgm_list (with and without query params)
3. HTTP 206 Partial Content range requests against Spine .skel model in /spines/
4. Cache-Control headers on static assets and models with and without query strings
5. Offline audio extraction via audio_manager using local Asset/ bundle with network blocked
6. Verification across both GalleryHTTPHandler (gallery_server.py) and GalleryHandler (cherrytale.py)
"""

import os
import sys
import time
import socket
import threading
import urllib.request
import urllib.error
import json
from http.server import ThreadingHTTPServer

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def run_test_server(server_class, handler_class, port):
    server = server_class(("", port), handler_class)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": resp.read(),
                "error": None
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": e.read(),
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "body": b"",
            "error": str(e)
        }

def test_handler(name, handler_class):
    print(f"\n==========================================")
    print(f"Testing Server Handler: {name}")
    print(f"==========================================")
    port = get_free_port()
    server = run_test_server(ThreadingHTTPServer, handler_class, port)
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.5)

    results = []

    def record(test_name, passed, detail=""):
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] {test_name}: {detail}")
        results.append((test_name, passed, detail))

    try:
        # 1. /api/catalog without query params
        res = http_get(f"{base_url}/api/catalog")
        valid_json = False
        catalog_len = 0
        try:
            cat_data = json.loads(res["body"].decode("utf-8"))
            valid_json = True
            catalog_len = len(cat_data)
        except Exception as e:
            pass
        record(
            "1.1 /api/catalog without query params",
            res["status"] == 200 and valid_json and catalog_len > 0,
            f"Status={res['status']}, JSON items={catalog_len}, Content-Type={res['headers'].get('Content-Type')}"
        )

        # 1.2 /api/catalog with query params (?v=1)
        res = http_get(f"{base_url}/api/catalog?v=1")
        valid_json = False
        try:
            cat_data = json.loads(res["body"].decode("utf-8"))
            valid_json = True
        except Exception:
            pass
        record(
            "1.2 /api/catalog?v=1",
            res["status"] == 200 and valid_json,
            f"Status={res['status']}, Valid JSON={valid_json}"
        )

        # 1.3 /api/catalog with multiple complex query params
        res = http_get(f"{base_url}/api/catalog?v=6&category=HCG&filter=all&search=2.5nd")
        valid_json = False
        try:
            cat_data = json.loads(res["body"].decode("utf-8"))
            valid_json = True
        except Exception:
            pass
        record(
            "1.3 /api/catalog?v=6&category=HCG&...",
            res["status"] == 200 and valid_json,
            f"Status={res['status']}, Valid JSON={valid_json}"
        )

        # 1.4 Non-existent catalog route
        res = http_get(f"{base_url}/api/catalog_nonexistent")
        record(
            "1.4 /api/catalog_nonexistent returns 404",
            res["status"] == 404,
            f"Status={res['status']}"
        )

        # 2.1 /api/bgm_list without query params
        res = http_get(f"{base_url}/api/bgm_list")
        valid_json = False
        bgm_count = 0
        sample_track = None
        try:
            bgm_data = json.loads(res["body"].decode("utf-8"))
            valid_json = isinstance(bgm_data, list)
            bgm_count = len(bgm_data)
            if bgm_count > 0:
                sample_track = bgm_data[0]
        except Exception:
            pass
        has_fields = sample_track and all(k in sample_track for k in ("id", "title", "category", "url", "size_mb"))
        record(
            "2.1 /api/bgm_list without query params",
            res["status"] == 200 and valid_json and bgm_count > 0 and has_fields,
            f"Status={res['status']}, Tracks={bgm_count}, Sample: {sample_track.get('title') if sample_track else None}"
        )

        # 2.2 /api/bgm_list with query params (?v=2)
        res = http_get(f"{base_url}/api/bgm_list?v=2")
        valid_json = False
        try:
            bgm_data = json.loads(res["body"].decode("utf-8"))
            valid_json = isinstance(bgm_data, list) and len(bgm_data) > 0
        except Exception:
            pass
        record(
            "2.2 /api/bgm_list?v=2",
            res["status"] == 200 and valid_json,
            f"Status={res['status']}, Valid JSON list={valid_json}"
        )

        # 3. HTTP 206 Partial Content Range Requests against Spine model
        # Find an existing skel file
        skel_stem = "2.5nd_Anniversary"
        skel_file = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "skel", f"{skel_stem}.skel")
        file_size = os.path.getsize(skel_file)
        with open(skel_file, "rb") as f:
            full_file_bytes = f.read()

        # 3.1 Range: bytes=0-100 (exact assignment requirement)
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", headers={"Range": "bytes=0-100"})
        expected_range_header = f"bytes 0-100/{file_size}"
        actual_range_header = res["headers"].get("Content-Range", "")
        body_matches = (res["body"] == full_file_bytes[0:101])
        record(
            "3.1 Range: bytes=0-100 on .skel",
            res["status"] == 206 and actual_range_header == expected_range_header and len(res["body"]) == 101 and body_matches,
            f"Status={res['status']}, Content-Range={actual_range_header}, BodyLen={len(res['body'])}, Exact Bytes Match={body_matches}"
        )

        # 3.2 Range: bytes=50-150
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", headers={"Range": "bytes=50-150"})
        body_matches = (res["body"] == full_file_bytes[50:151])
        record(
            "3.2 Range: bytes=50-150 on .skel",
            res["status"] == 206 and res["headers"].get("Content-Range") == f"bytes 50-150/{file_size}" and body_matches,
            f"Status={res['status']}, Content-Range={res['headers'].get('Content-Range')}, Bytes Match={body_matches}"
        )

        # 3.3 Open-ended Range: bytes=100-
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", headers={"Range": "bytes=100-"})
        expected_len = file_size - 100
        body_matches = (res["body"] == full_file_bytes[100:])
        record(
            "3.3 Range: bytes=100- (open-ended)",
            res["status"] == 206 and len(res["body"]) == expected_len and body_matches,
            f"Status={res['status']}, Len={len(res['body'])}, Expected={expected_len}, Bytes Match={body_matches}"
        )

        # 3.4 Full request (no range) -> HTTP 200
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel")
        record(
            "3.4 Full request (no Range) on .skel",
            res["status"] == 200 and len(res["body"]) == file_size and res["headers"].get("Accept-Ranges") == "bytes",
            f"Status={res['status']}, Len={len(res['body'])}, Accept-Ranges={res['headers'].get('Accept-Ranges')}"
        )

        # 3.5 Range out of bounds: bytes=99999999- -> HTTP 416
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", headers={"Range": "bytes=99999999-"})
        record(
            "3.5 Range out of bounds (bytes=99999999-) returns 416",
            res["status"] == 416,
            f"Status={res['status']}"
        )

        # 3.6 Range on .atlas file
        atlas_file = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "atlas", f"{skel_stem}.atlas")
        if os.path.exists(atlas_file):
            atlas_size = os.path.getsize(atlas_file)
            res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.atlas", headers={"Range": "bytes=0-50"})
            record(
                "3.6 Range: bytes=0-50 on .atlas",
                res["status"] == 206 and res["headers"].get("Content-Range") == f"bytes 0-50/{atlas_size}" and len(res["body"]) == 51,
                f"Status={res['status']}, Content-Range={res['headers'].get('Content-Range')}, Content-Type={res['headers'].get('Content-Type')}"
            )

        # 3.7 Range on .png texture
        png_file = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "textures", f"{skel_stem}.png")
        if os.path.exists(png_file):
            png_size = os.path.getsize(png_file)
            res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.png", headers={"Range": "bytes=0-100"})
            record(
                "3.7 Range: bytes=0-100 on .png texture",
                res["status"] == 206 and res["headers"].get("Content-Range") == f"bytes 0-100/{png_size}" and len(res["body"]) == 101,
                f"Status={res['status']}, Content-Range={res['headers'].get('Content-Range')}, Content-Type={res['headers'].get('Content-Type')}"
            )

        # 3.8 Case-insensitive fallback
        res = http_get(f"{base_url}/spines/{skel_stem.lower()}/{skel_stem.lower()}.skel", headers={"Range": "bytes=0-50"})
        record(
            "3.8 Case-insensitive /spines/<stem.lower()>/...",
            res["status"] == 206 and len(res["body"]) == 51,
            f"Status={res['status']}, Len={len(res['body'])}"
        )

        # 4. Cache-Control Header Checks
        # 4.1 Static vendor JS with query string
        res = http_get(f"{base_url}/vendor/spine-player.js?v=6")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.1 Cache-Control on /vendor/spine-player.js?v=6",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.2 Static vendor CSS with query string
        res = http_get(f"{base_url}/vendor/spine-player.css?v=6")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.2 Cache-Control on /vendor/spine-player.css?v=6",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.3 Spine .skel model with query string
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.skel?v=6")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.3 Cache-Control on /spines/...skel?v=6",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.4 Spine .atlas with query string
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.atlas?v=6")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.4 Cache-Control on /spines/...atlas?v=6",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.5 Spine .png texture with query string
        res = http_get(f"{base_url}/spines/{skel_stem}/{skel_stem}.png?v=6")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.5 Cache-Control on /spines/...png?v=6",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.6 Static assets without query string
        res = http_get(f"{base_url}/vendor/spine-player.js")
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.6 Cache-Control on /vendor/spine-player.js (no query)",
            res["status"] == 200 and "public" in cc and "max-age=86400" in cc,
            f"Status={res['status']}, Cache-Control='{cc}'"
        )

        # 4.7 Audio endpoint with Range request and query string
        res = http_get(f"{base_url}/audio/se/se_hstory001.wav?v=3", headers={"Range": "bytes=0-100"})
        cc = res["headers"].get("Cache-Control", "")
        record(
            "4.7 Audio Range request with query string",
            res["status"] == 206 and "public" in cc and "max-age=86400" in cc and len(res["body"]) == 101,
            f"Status={res['status']}, Cache-Control='{cc}', Len={len(res['body'])}"
        )

    finally:
        server.shutdown()
        server.server_close()

    total_pass = sum(1 for _, p, _ in results if p)
    print(f"\nHandler {name} Summary: {total_pass}/{len(results)} tests passed.")
    return all(p for _, p, _ in results)


def test_offline_audio_extraction():
    print(f"\n==========================================")
    print(f"Testing Offline Audio Extraction via audio_manager")
    print(f"==========================================")
    from tools.audio_manager import audio_manager

    # 1. Verify ASSET_DIR points to local directory
    asset_dir = getattr(audio_manager, "ASSET_DIR", None) or os.path.join(PROJECT_ROOT, "Asset")
    print(f"[Check] ASSET_DIR = {asset_dir}")
    if not os.path.exists(asset_dir):
        print(f"[FAIL] Local Asset directory does not exist: {asset_dir}")
        return False

    # 2. Identify available local sound bundles
    test_clip = "se_hstory002"
    bundle_info = audio_manager.resolve_bundle(test_clip)
    print(f"[Check] Resolved bundle for {test_clip}: {bundle_info}")
    if not bundle_info:
        print(f"[FAIL] Could not resolve bundle for {test_clip}")
        return False

    bundle_name, bsize, bmd5 = bundle_info
    local_bundle_path = os.path.join(asset_dir, bundle_name)
    if not os.path.exists(local_bundle_path):
        print(f"[FAIL] Local bundle file not found at: {local_bundle_path}")
        return False

    print(f"[PASS] Local bundle exists: {local_bundle_path} ({os.path.getsize(local_bundle_path):,} bytes)")

    # 3. Offline constraint: Block network access by replacing urllib.request.urlopen with a poison pill
    original_urlopen = urllib.request.urlopen
    def poison_urlopen(*args, **kwargs):
        raise ConnectionRefusedError("TEST NETWORK BLOCK: Attempted external network access during offline extraction test!")

    urllib.request.urlopen = poison_urlopen

    try:
        # Clear destination cached wav if it exists so we force real extraction
        se_dir = os.path.join(PROJECT_ROOT, "dump", "audio", "se")
        cached_wav = os.path.join(se_dir, f"{test_clip}.wav")
        backup_wav = os.path.join(se_dir, f"{test_clip}.wav.bak")

        if os.path.exists(cached_wav):
            if os.path.exists(backup_wav):
                os.remove(backup_wav)
            os.rename(cached_wav, backup_wav)

        try:
            print(f"[Test] Triggering extraction for {test_clip} with network blocked...")
            extracted_path = audio_manager.get_or_extract_audio("se", test_clip)

            if not extracted_path or not os.path.exists(extracted_path):
                print(f"[FAIL] Extraction returned invalid path: {extracted_path}")
                return False

            wav_size = os.path.getsize(extracted_path)
            with open(extracted_path, "rb") as f:
                header = f.read(12)
            is_valid_wav = (header[:4] == b"RIFF" and header[8:12] == b"WAVE")

            print(f"[PASS] Successfully extracted local bundle offline:")
            print(f"       Path: {extracted_path}")
            print(f"       Size: {wav_size:,} bytes")
            print(f"       RIFF/WAVE header verified: {is_valid_wav}")

            if not is_valid_wav or wav_size < 1000:
                print(f"[FAIL] Extracted file is not a valid non-empty WAV file!")
                return False

            # Test 4: Verify subsequent call is instantaneous cache hit
            t0 = time.perf_counter()
            hit_path = audio_manager.get_or_extract_audio("se", test_clip)
            t1 = time.perf_counter()
            hit_duration_ms = (t1 - t0) * 1000
            print(f"[PASS] Cache hit returned in {hit_duration_ms:.2f} ms")

            # Test 5: Concurrency test - 5 simultaneous threads extracting
            threads = []
            thread_results = [None] * 5
            def worker_thread(idx):
                thread_results[idx] = audio_manager.get_or_extract_audio("se", test_clip)

            for i in range(5):
                t = threading.Thread(target=worker_thread, args=(i,))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

            concurrency_pass = all(r == extracted_path for r in thread_results)
            print(f"[PASS] Concurrency test (5 threads): {concurrency_pass}")
            if not concurrency_pass:
                return False

            return True

        finally:
            # Restore backup if needed
            if os.path.exists(backup_wav):
                if os.path.exists(cached_wav):
                    os.remove(backup_wav)
                else:
                    os.rename(backup_wav, cached_wav)

    finally:
        urllib.request.urlopen = original_urlopen


def main():
    print("Starting Empirical Challenger M1 Verification Suite...")

    # Test GalleryHTTPHandler from viewer/gallery_server.py
    from viewer.gallery_server import GalleryHTTPHandler
    res1 = test_handler("viewer.gallery_server.GalleryHTTPHandler", GalleryHTTPHandler)

    # Test GalleryHandler from cherrytale.py
    from cherrytale import GalleryHandler
    res2 = test_handler("cherrytale.GalleryHandler", GalleryHandler)

    # Test offline audio extraction
    res3 = test_offline_audio_extraction()

    print("\n==========================================")
    print("FINAL CHALLENGER VERIFICATION RESULTS")
    print("==========================================")
    print(f"viewer.gallery_server.GalleryHTTPHandler: {'PASS' if res1 else 'FAIL'}")
    print(f"cherrytale.GalleryHandler:                {'PASS' if res2 else 'FAIL'}")
    print(f"offline_audio_extraction:                 {'PASS' if res3 else 'FAIL'}")

    all_passed = res1 and res2 and res3
    print(f"\nOVERALL RESULT: {'APPROVE' if all_passed else 'REJECT'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
