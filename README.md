# 🌸 CherryTale Standalone — Web Viewer & Datamine Suite

A standalone, high-performance reverse-engineering, datamining, and interactive web gallery suite for **CherryTale**.

Featuring real-time Spine 4.0 60 FPS playback, multi-threaded asset extraction, full official English story & dialogue localization, timeline-choreographed voice & SFX playback, and an obsidian/sakura dark-mode web application.

---

## ⚡ Quickstart

### 1. Launch the Web Gallery
To start the gallery viewer server right away:
```bat
.\run.bat serve
```
Or directly via Python:
```bash
python cherrytale.py serve --port 8000
```
Open **`http://localhost:8000/index.html`** in any modern web browser.

---

## 🚀 Unified CLI Automation (`cherrytale.py`)

All maintenance, patching, extraction, and compilation tasks are controlled through the root CLI:

```bash
# 1. Sync live game patch (Node 1002), update master index, and decrypt game tables
python cherrytale.py sync --overwrite

# 2. Extract Spine animation models (.skel, .atlas, .png) and Audio clips (.wav)
python cherrytale.py extract --type all --workers 16

# 3. Compile WebP thumbnails, animation manifests, dialogue maps, and web viewer
python cherrytale.py build --workers 16

# 4. Run local interactive gallery server with HTTP 206 range streaming
python cherrytale.py serve --port 8000

# Full end-to-end automation in a single command:
python cherrytale.py run-all
```

---

## ✨ Web Viewer Highlights

* **499 Distinct Spine 4.0 Live Models**:
  * **250+ Adult H-Scenes / HCG Models** (`story_free_hcg01`, `ct001_hcg1`, `b004_01_hcg1`, etc.)
  * **200+ Character CG Models** (`a001_01_CG`, `d002_04_CG`, etc.)
  * **Anniversary & Special Releases**: `2.5th`, `3rd`, `3.5th`, `April Fools`, and Four Holy Beasts (`Seiryu`, `Byakko`, `Suzaku`, `Genbu`).
* **🎵 Complete Soundtrack & Sound FX**:
  * Persistent docked / floating BGM player with animated equalizer, volume sliders, and playlist drawer.
  * HTTP 206 partial-content streaming with on-demand decrypt & instant WAV/MP3 delivery.
* **🎙 22,700+ Authentic Voice Clips & Dialogue Choreography**:
  * **Touch & Intimacy Voices**: Direct 1-click playback for Touch 1, Touch 2, Special Touch, Bond Events, and Climax lines.
  * **Role & Favorability Dialogues**: Character home screen voice lines with side-by-side English & Traditional Chinese text.
  * **Interactive Story Reader**: Clickable audio buttons next to every voiced dialogue line with auto-scrolling.
  * **Animation-Synced SFX & Moans**: Realistic rhythmic audio playback synced to animation phase buttons (e.g. insertion, finishing).
* **⚡ High-Performance WebGL Runtime**:
  * **Context Management**: Explicit `WEBGL_lose_context` cleanup on modal transitions to prevent browser GPU exhaustion.
  * **Audio Singleton**: Web Audio API singleton with LRU buffer caching to eliminate audio latency.
  * **Quick-Jump Phase Bar & Composite Skin Deck**: Easily toggle between insertion, climax, and multi-costume states.
* **📖 Official English Localization**:
  * 96,000+ localized strings across character profiles, items, main stories, and H-scenes.

---

## 🛠️ Repository Structure

```
CherryTale_Standalone/
├── cherrytale.py                  # Master standalone CLI & extraction/build pipeline
├── run.bat                        # Windows quick-launcher script
├── requirements.txt               # Essential runtime dependencies
├── requirements-all.txt           # Complete development & headless rendering dependencies
├── README.md                      # Project documentation
│
├── viewer/
│   ├── index.html                 # Complete standalone single-page Web Gallery application
│   ├── gallery_server.py          # High-performance streaming HTTP server
│   ├── render_anim.exe            # C++ headless Spine 4.0 rasterizer & frame extractor
│   ├── vendor/                    # Local bundled spine-player.js and assets
│   ├── thumbs/                    # Pre-generated WebP card thumbnails
│   └── data/                      # Webapp static models & dialogue catalog
│
├── tools/
│   ├── build_gallery_webapp.py    # Multi-threaded web gallery compiler
│   ├── update_characters_index.py # Character registry synchronizer
│   ├── index_animations.py        # Spine animation manifest scanner
│   ├── render_all_hcg_frame0.py   # Multi-threaded setup pose rasterizer
│   └── audio_manager.py           # Audio indexing & BGM mapping helper
│
├── dump/
│   ├── characters_index.json      # Master character catalog (363 registered characters)
│   ├── metadata_summary.json      # Comprehensive game & asset statistics
│   ├── hscene_en/                 # Fully localized English story scripts
│   ├── textassets/                # Decrypted game configuration tables (.txt)
│   └── hcg_art/
│       └── animations_manifest.json # Complete database of 7,242 indexed animations
│
└── hcg_manifest/
    ├── access_token.txt           # Live patch authentication token
    └── index_save.txt             # Cached patch index
```

---

## 💻 Requirements & Installation

* **Python**: 3.10+ recommended (Windows / Linux / macOS)
* **Installation**:
  ```bash
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```

---

## ⚖️ Disclaimer

This project is developed strictly for educational, archival, and reverse-engineering research purposes. All original game assets, art, sounds, and characters belong to the original game developers and copyright holders.
