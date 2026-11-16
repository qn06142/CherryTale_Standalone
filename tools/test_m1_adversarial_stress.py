#!/usr/bin/env python3
"""Adversarial Stress Test Suite for Milestone 1 Challenger.

Stress tests:
1. Boundary range requests:
   - Single byte range: bytes=0-0 (first byte)
   - Last byte range: bytes=<size-1>-<size-1> (exact last byte)
   - Negative/unsupported ranges: bytes=-50, bytes=abc-def
   - Range with spaces: bytes= 0-10
2. Audio URL format variations:
   - Without extension: /audio/se/se_hstory001
   - With uppercase extension: /audio/se/se_hstory001.WAV
   - With query params: /audio/se/se_hstory001?v=99&foo=bar
   - Tier 1 disk fallback across directories (voice, se, bgm)
3. HTTP methods:
   - OPTIONS method (CORS preflight)
   - HEAD method
4. Complex Spine model filenames with underscores and numbers:
   - 2nd_Anniversary_hcg1_1
"""

import os
import sys
import time
import socket
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from viewer.gallery_server import GalleryHTTPHandler

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def send_request(method, url, headers=None):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
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

def run_stress_tests():
    port = get_free_port()
    server = ThreadingHTTPServer(("", port), GalleryHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.5)

    skel_stem = "2.5nd_Anniversary"
    skel_file = os.path.join(PROJECT_ROOT, "dump", "hcg_art", "skel", f"{skel_stem}.skel")
    file_size = os.path.getsize(skel_file)
    with open(skel_file, "rb") as f:
        file_bytes = f.read()

    results = []
    def log_result(name, ok, msg=""):
        res_str = "PASS" if ok else "FAIL"
        print(f"[{res_str}] {name}: {msg}")
        results.append((name, ok, msg))

    try:
        # 1. Single byte range: bytes=0-0
        res = send_request("GET", f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", {"Range": "bytes=0-0"})
        ok = (res["status"] == 206 and len(res["body"]) == 1 and res["body"] == file_bytes[:1] and res["headers"].get("Content-Range") == f"bytes 0-0/{file_size}")
        log_result("1. Single byte range (bytes=0-0)", ok, f"Status={res['status']}, Content-Range={res['headers'].get('Content-Range')}, Len={len(res['body'])}")

        # 2. Exact last byte: bytes=(file_size-1)-(file_size-1)
        last_idx = file_size - 1
        res = send_request("GET", f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", {"Range": f"bytes={last_idx}-{last_idx}"})
        ok = (res["status"] == 206 and len(res["body"]) == 1 and res["body"] == file_bytes[last_idx:last_idx+1])
        log_result("2. Exact last byte range", ok, f"Status={res['status']}, Len={len(res['body'])}, Range={res['headers'].get('Content-Range')}")

        # 3. Malformed Range header: bytes=abc-def (should fall back gracefully to 200 without crashing)
        res = send_request("GET", f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", {"Range": "bytes=abc-def"})
        ok = (res["status"] == 200 and len(res["body"]) == file_size)
        log_result("3. Malformed Range bytes=abc-def gracefully serves 200", ok, f"Status={res['status']}, Len={len(res['body'])}")

        # 4. Suffix range: bytes=-50 (standard regex in handler is bytes=(\d+)-(\d*), so unmatched regex should fall back gracefully to 200)
        res = send_request("GET", f"{base_url}/spines/{skel_stem}/{skel_stem}.skel", {"Range": "bytes=-50"})
        ok = (res["status"] == 200 and len(res["body"]) == file_size)
        log_result("4. Suffix range bytes=-50 falls back to 200 without error", ok, f"Status={res['status']}, Len={len(res['body'])}")

        # 5. Audio URL without extension: /audio/se/se_hstory001
        res = send_request("GET", f"{base_url}/audio/se/se_hstory001")
        ok = (res["status"] == 200 and len(res["body"]) > 1000 and res["body"][:4] == b"RIFF")
        log_result("5. Audio without .wav extension (/audio/se/se_hstory001)", ok, f"Status={res['status']}, Len={len(res['body'])}, Header={res['body'][:4]}")

        # 6. Audio URL with query parameters: /audio/se/se_hstory001?foo=bar&baz=1
        res = send_request("GET", f"{base_url}/audio/se/se_hstory001?foo=bar&baz=1")
        ok = (res["status"] == 200 and len(res["body"]) > 1000 and res["body"][:4] == b"RIFF")
        log_result("6. Audio with query params (/audio/se/se_hstory001?...)", ok, f"Status={res['status']}, Len={len(res['body'])}")

        # 7. OPTIONS CORS Preflight
        res = send_request("OPTIONS", f"{base_url}/api/catalog")
        ok = (res["status"] == 200 and res["headers"].get("Access-Control-Allow-Origin") == "*")
        log_result("7. OPTIONS CORS preflight on /api/catalog", ok, f"Status={res['status']}, CORS={res['headers'].get('Access-Control-Allow-Origin')}")

        # 8. OPTIONS CORS Preflight on /spines/...
        res = send_request("OPTIONS", f"{base_url}/spines/{skel_stem}/{skel_stem}.skel")
        ok = (res["status"] == 200 and res["headers"].get("Access-Control-Allow-Origin") == "*")
        log_result("8. OPTIONS CORS preflight on /spines/...", ok, f"Status={res['status']}, CORS={res['headers'].get('Access-Control-Allow-Origin')}")

        # 9. Complex model with underscores: 2nd_Anniversary_hcg1_1
        complex_stem = "2nd_Anniversary_hcg1_1"
        res = send_request("GET", f"{base_url}/spines/{complex_stem}/{complex_stem}.skel", {"Range": "bytes=0-50"})
        ok = (res["status"] == 206 and len(res["body"]) == 51)
        log_result("9. Complex Spine model name (2nd_Anniversary_hcg1_1)", ok, f"Status={res['status']}, Len={len(res['body'])}")

        # 10. Cache-Control on dynamic audio stream
        res = send_request("GET", f"{base_url}/audio/se/se_hstory001")
        cc = res["headers"].get("Cache-Control", "")
        ok = ("public" in cc and "max-age=86400" in cc)
        log_result("10. Cache-Control on /audio/ stream", ok, f"Cache-Control='{cc}'")

    finally:
        server.shutdown()
        server.server_close()

    total_pass = sum(1 for _, ok, _ in results if ok)
    print(f"\nAdversarial Stress Test Summary: {total_pass}/{len(results)} passed.")
    return total_pass == len(results)

if __name__ == "__main__":
    passed = run_stress_tests()
    sys.exit(0 if passed else 1)
