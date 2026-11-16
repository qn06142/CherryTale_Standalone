#!/usr/bin/env python3
"""CherryTale Audio Pack Downloader.

Downloads and caches essential CherryTale audio:
- Top 15 prominent BGM tracks (Anniversaries, Vocals, Romance, Battle themes)
- Touch voice lines for main heroines (Cinderella, Gretel, Aladdin, Alice, etc.)
- Can also be run with --all-bgm to download all 90 BGM tracks.
"""

import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from tools.audio_manager import audio_manager, BGM_DIR, VOICE_DIR

DEFAULT_TOP_BGMS = [
    "1st_anniv_1st_anniv",
    "2nd_anniv_2nd_anniv",
    "2.5nd_anniv_2.5nd_anniv",
    "a01_a01_bpm140_210_vocal",
    "a01_a01_bpm140_210_inst",
    "a04_a04_bpm60",
    "a04_a04_bpm72_revise",
    "attribute_altar_attributealtar_bgm",
    "alliance_alliance_bgm",
    "b04_b04_bpm94",
    "c04_c04_bpm70",
    "c03_c03_bpm85",
    "a01_a01_bpm140_210_2mix",
    "bgm_song_220421",
    "bgm_song_230510"
]

DEFAULT_HEROINE_VOICES = [
    # Cinderella (e001)
    "vic_e001_01_019", "vic_e001_01_020", "vic_e001_01_021", "vic_e001_01_022",
    "vic_hstory_main1-1_001", "vic_hstory_main1-1_002", "vic_hstory_main1-1_003",
    # Gretel (a001)
    "vic_a001_01_tou_01", "vic_a001_01_tou_02", "vic_a001_03_tou_01", "vic_a001_03_tou_02", "vic_a001_03_tou_bom",
    # Aladdin (a002)
    "vic_a002_02_tou_01", "vic_a002_02_tou_02", "vic_a002_02_tou_bom",
    # Alice (a005)
    "vic_a005_03_tou_01", "vic_a005_03_tou_02", "vic_a005_03_tou_bom",
    # March Hare (b004)
    "vic_b004_01_tou_01", "vic_b004_01_tou_02", "vic_b004_01_tou_bom",
    # Tintagel / ct001
    "vic_ct001_tou_01", "vic_ct001_tou_02", "vic_ct001_tou_bon"
]

def download_bgm(b_id):
    path = audio_manager.get_or_extract_audio("bgm", b_id)
    return b_id, bool(path)

def download_voice(v_id):
    path = audio_manager.get_or_extract_audio("voice", v_id)
    return v_id, bool(path)

def main():
    parser = argparse.ArgumentParser(description="Fetch CherryTale Audio Pack")
    parser.add_argument("--all-bgm", action="store_true", help="Download all 90 BGM tracks")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker threads")
    args = parser.parse_args()

    bgm_list = [b["id"] for b in audio_manager.bgm_catalog] if args.all_bgm else DEFAULT_TOP_BGMS

    print(f"🎵 Pre-downloading {len(bgm_list)} BGM tracks with {args.workers} workers...")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_bgm, b): b for b in bgm_list}
        for f in as_completed(futures):
            b_id, success = f.result()
            print(f"  [{'OK' if success else 'FAIL'}] BGM: {b_id}")

    print(f"\n🎙 Pre-downloading {len(DEFAULT_HEROINE_VOICES)} Heroine Voice Lines...")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_voice, v): v for v in DEFAULT_HEROINE_VOICES}
        for f in as_completed(futures):
            v_id, success = f.result()
            print(f"  [{'OK' if success else 'FAIL'}] Voice: {v_id}")

    print("\n✅ Audio Pack Download Complete!")

if __name__ == "__main__":
    main()
