import os
import sys
import glob
import json
import re
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VIEWER_DIR = os.path.join(PROJECT_ROOT, "viewer")
DATA_DIR = os.path.join(VIEWER_DIR, "data")
DUMP_DIR = os.path.join(PROJECT_ROOT, "dump")
AUDIO_DIR = os.path.join(DUMP_DIR, "audio")
BGM_DIR = os.path.join(AUDIO_DIR, "bgm")
VOICE_DIR = os.path.join(AUDIO_DIR, "voice")
SE_DIR = os.path.join(AUDIO_DIR, "se")

sys.path.insert(0, PROJECT_ROOT)
try:
    from tools.audio_manager import audio_manager
except Exception as e:
    print(f"Warning: could not import audio_manager: {e}")
    audio_manager = None

# Pre-build lookup index for fast serving of spine assets
SKEL_INDEX = {}
ATLAS_INDEX = {}
TEX_INDEX = {}

def build_indices():
    # 1. Check dump/hcg_art
    for sk in glob.glob(os.path.join(DUMP_DIR, "hcg_art", "skel", "*.skel")):
        stem = os.path.splitext(os.path.basename(sk))[0]
        SKEL_INDEX[stem] = sk
        SKEL_INDEX[stem.lower()] = sk
    for at in glob.glob(os.path.join(DUMP_DIR, "hcg_art", "atlas", "*.atlas")):
        stem = os.path.splitext(os.path.basename(at))[0]
        ATLAS_INDEX[stem] = at
        ATLAS_INDEX[stem.lower()] = at
    for tx in glob.glob(os.path.join(DUMP_DIR, "hcg_art", "textures", "*.png")):
        name = os.path.basename(tx)
        stem = os.path.splitext(name)[0]
        TEX_INDEX[name] = tx
        TEX_INDEX[name.lower()] = tx
        TEX_INDEX[stem] = tx
        TEX_INDEX[stem.lower()] = tx

    # 2. Check dump/hcg_spine
    for sk in glob.glob(os.path.join(DUMP_DIR, "hcg_spine", "*", "*.skel")):
        stem = os.path.splitext(os.path.basename(sk))[0]
        if stem not in SKEL_INDEX:
            SKEL_INDEX[stem] = sk
            SKEL_INDEX[stem.lower()] = sk
    for at in glob.glob(os.path.join(DUMP_DIR, "hcg_spine", "*", "*.atlas")):
        stem = os.path.splitext(os.path.basename(at))[0]
        if stem not in ATLAS_INDEX:
            ATLAS_INDEX[stem] = at
            ATLAS_INDEX[stem.lower()] = at
    for tx in glob.glob(os.path.join(DUMP_DIR, "hcg_spine", "*", "*.png")):
        name = os.path.basename(tx)
        stem = os.path.splitext(name)[0]
        if name not in TEX_INDEX:
            TEX_INDEX[name] = tx
            TEX_INDEX[name.lower()] = tx
        if stem not in TEX_INDEX:
            TEX_INDEX[stem] = tx
            TEX_INDEX[stem.lower()] = tx

    print(f"Gallery Server Index Ready: {len(SKEL_INDEX)} skeletons, {len(ATLAS_INDEX)} atlases, {len(TEX_INDEX)} textures.")

build_indices()

class GalleryHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VIEWER_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS and caching headers for optimal performance
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

    def send_file_range(self, filepath, content_type="audio/wav"):
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
                            chunk_size = min(65536, bytes_left)
                            data = f.read(chunk_size)
                            if not data:
                                break
                            self.wfile.write(data)
                            bytes_left -= len(data)
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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Route /api/catalog
        if path == "/api/catalog":
            cat_f = os.path.join(DATA_DIR, "catalog.json")
            if os.path.exists(cat_f):
                with open(cat_f, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                super().end_headers()
                self.wfile.write(data)
                return
            else:
                self.send_error(404, "Catalog file not found")
                return

        # Route /api/bgm_list
        if path == "/api/bgm_list":
            if audio_manager and getattr(audio_manager, "bgm_catalog", None):
                data = json.dumps(audio_manager.bgm_catalog, ensure_ascii=False).encode("utf-8")
            else:
                bgm_tracks = []
                for bf in sorted(glob.glob(os.path.join(BGM_DIR, "*.wav"))):
                    bname = os.path.splitext(os.path.basename(bf))[0]
                    title = bname.replace("_", " ").title()
                    bgm_tracks.append({
                        "id": bname,
                        "title": title,
                        "category": "BGM",
                        "url": f"/audio/bgm/{bname}",
                        "size_mb": round(os.path.getsize(bf) / (1024 * 1024), 2)
                    })
                data = json.dumps(bgm_tracks, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
            self.wfile.write(data)
            return

        # Route /audio/<category>/<identifier>
        if path.startswith("/audio/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 3:
                category = parts[1]
                identifier = parts[2]
                clean_id = identifier[:-4] if identifier.endswith(".wav") else identifier

                # Tier 1: Check pre-extracted files on disk
                dest_dir = BGM_DIR if category == "bgm" else (SE_DIR if category in ("se", "ambientsound") else VOICE_DIR)
                fpath = os.path.join(dest_dir, f"{clean_id}.wav")
                if not os.path.exists(fpath):
                    for alt in (VOICE_DIR, SE_DIR, BGM_DIR):
                        cand = os.path.join(alt, f"{clean_id}.wav")
                        if os.path.exists(cand):
                            fpath = cand
                            break

                if os.path.exists(fpath):
                    self.send_file_range(fpath, "audio/wav")
                    return

                # Tier 2: On-demand extraction via audio_manager
                if audio_manager:
                    wav_path = audio_manager.get_or_extract_audio(category, clean_id)
                    if wav_path and os.path.exists(wav_path):
                        self.send_file_range(wav_path, "audio/wav")
                        return

                self.send_error(404, f"Audio not found or extraction failed: {category}/{identifier}")
                return

        # Route /spines/<stem>/<filename>
        if path.startswith("/spines/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 3:
                stem = parts[1]
                filename = parts[2]
                file_target = None
                mime_type = "application/octet-stream"

                if filename.endswith(".skel"):
                    file_target = SKEL_INDEX.get(stem) or SKEL_INDEX.get(stem.lower())
                    if not file_target:
                        fallback = os.path.join(DUMP_DIR, "hcg_art", "skel", f"{stem}.skel")
                        if os.path.exists(fallback):
                            file_target = fallback
                    mime_type = "application/octet-stream"
                elif filename.endswith(".atlas"):
                    file_target = ATLAS_INDEX.get(stem) or ATLAS_INDEX.get(stem.lower())
                    if not file_target:
                        fallback = os.path.join(DUMP_DIR, "hcg_art", "atlas", f"{stem}.atlas")
                        if os.path.exists(fallback):
                            file_target = fallback
                    mime_type = "text/plain; charset=utf-8"
                elif filename.endswith(".png"):
                    file_target = (TEX_INDEX.get(filename) or 
                                   TEX_INDEX.get(filename.lower()) or 
                                   TEX_INDEX.get(stem) or 
                                   TEX_INDEX.get(stem.lower()))
                    if not file_target:
                        fallback = os.path.join(DUMP_DIR, "hcg_art", "textures", filename)
                        if not os.path.exists(fallback):
                            fallback = os.path.join(DUMP_DIR, "hcg_art", "textures", f"{stem}.png")
                        if os.path.exists(fallback):
                            file_target = fallback
                    mime_type = "image/png"

                if file_target and os.path.exists(file_target):
                    self.send_file_range(file_target, mime_type)
                    return
                else:
                    self.send_error(404, f"Spine file not found: {filename} for {stem}")
                    return

        # Default handler serves viewer/
        return super().do_GET()

def run(port=8000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, GalleryHTTPHandler)
    print(f"Starting CherryTale Gallery High-Performance Server on http://localhost:{port} ...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    port = 8000
    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg in ("--port", "-p") and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])
        elif arg.isdigit():
            port = int(arg)
    run(port)
