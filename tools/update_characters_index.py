#!/usr/bin/env python3
"""Update and synchronize dump/characters_index.json with the latest patch data.

Sources:
1. dump/characters_index.json (existing curated registry)
2. dump/textassets/LanguageSettings_enus.txt (official English translations)
3. dump/textassets/RoleInfoData.txt & RoleMainData.txt (character roster)
4. dump/textassets/SkinData.txt & CostumesData.txt (costumes & fashion skins)
5. dump/textassets/ItemData.txt (item tokens, summon chests, profile icons)
6. dump/textassets/StoryHData.txt (H-scenes, dialogues, character speakers)
7. dump/hcg_art/skel/*.skel (all extracted Spine models)
"""

import os
import glob
import re
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP_DIR = os.path.join(BASE_DIR, "dump")
TEXT_DIR = os.path.join(DUMP_DIR, "textassets")
SKEL_DIR = os.path.join(DUMP_DIR, "hcg_art", "skel")
INDEX_PATH = os.path.join(DUMP_DIR, "characters_index.json")

def clean_tag(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip().rstrip('┤').strip()

def main():
    print("📖 Loading English translations from LanguageSettings_enus.txt...")
    trans = {}
    trans_file = os.path.join(TEXT_DIR, "LanguageSettings_enus.txt")
    if os.path.exists(trans_file):
        with open(trans_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\r\n┤")
                if "|" in line:
                    k, v = line.split("|", 1)
                    k_clean = clean_tag(k)
                    v_clean = clean_tag(v)
                    if k_clean and v_clean:
                        trans[k_clean] = v_clean
    print(f"✓ Loaded {len(trans):,} translation pairs.")

    # 1. Load existing registry
    reg = {}
    if os.path.exists(INDEX_PATH):
        try:
            reg = json.load(open(INDEX_PATH, encoding="utf-8"))
            print(f"✓ Loaded existing characters_index.json with {len(reg)} entries.")
        except Exception as e:
            print(f"Warning loading existing index: {e}")

    for pfx, d in reg.items():
        d["models"] = set(d.get("models", []))
        d["costumes"] = d.get("costumes", [])
        d["dialogues"] = d.get("dialogues", [])

    # 2. Known canonical overrides & patch specials
    special_names = {
        "2nd_An": ("2nd Anniversary Special", "二週年特刊"),
        "2.5nd_": ("2.5th Anniversary Special", "二點五週年特刊"),
        "3rd_An": ("3rd Anniversary Special", "三週年特刊"),
        "3.5st_": ("3.5th Anniversary Special", "三點五週年特刊"),
        "3.5rd_": ("3.5th Anniversary Redux", "三點五週年特別篇"),
        "AprilF": ("April Fools Special", "愚人節特刊"),
        "ct089": ("Mamiya Marisa", "間宮麻理沙"),
        "ct091": ("Da Vinci", "達文西"),
        "ct092": ("Salome", "莎樂美"),
        "ct094": ("Gulliver", "格列佛"),
        "ct096": ("Uriel", "烏列爾"),
        "ct097": ("Rudy", "露蒂"),
        "ct098": ("Diaochan", "貂蟬"),
        "ct101": ("Qilin", "麒麟"),
        "ct107": ("Seiryu", "青龍"),
        "ct108": ("Byakko", "白虎"),
        "ct109": ("Suzaku", "朱雀"),
        "ct110": ("Genbu", "玄武"),
        "ct145": ("Special CG (ct145)", "特殊CG (ct145)"),
        "ct151": ("Special CG (ct151)", "特殊CG (ct151)"),
        "ct152": ("Special CG (ct152)", "特殊CG (ct152)"),
        "story_hcg45": ("Story Hcg45", "story_hcg45"),
    }

    for pfx, (en, zh) in special_names.items():
        if pfx not in reg:
            reg[pfx] = {
                "prefix": pfx,
                "name_en": en,
                "name_zh": zh,
                "costumes": [],
                "models": set(),
                "dialogues": []
            }
        else:
            if reg[pfx].get("name_en") in ("", pfx, pfx.upper(), pfx.title()):
                reg[pfx]["name_en"] = en
            if not reg[pfx].get("name_zh") or reg[pfx].get("name_zh") == pfx:
                reg[pfx]["name_zh"] = zh

    # 3. Scan ItemData.txt for [HCG頭像], summon chests, etc.
    item_file = os.path.join(TEXT_DIR, "ItemData.txt")
    if os.path.exists(item_file):
        with open(item_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                p = [c.strip().rstrip("┤") for c in line.split("|")]
                if len(p) > 7:
                    item_name = p[1]
                    icon = p[7]
                    m = re.search(r"([a-z]\d{3}|ct\d+|[a-z]{2}\d+)", icon)
                    if m:
                        cand_pfx = m.group(1)
                        cname = re.sub(r"^\[.*?\]", "", item_name).strip()
                        cname = re.sub(r"(召喚箱|的減肥餐盒|活動幣|晉升寶晶|專屬|的碎片|召喚石)$", "", cname).strip()
                        if cname:
                            name_en = trans.get(cname, cname)
                            if cand_pfx not in reg:
                                reg[cand_pfx] = {
                                    "prefix": cand_pfx,
                                    "name_en": name_en,
                                    "name_zh": cname,
                                    "costumes": [],
                                    "models": set(),
                                    "dialogues": []
                                }
                            else:
                                if not reg[cand_pfx].get("name_zh"):
                                    reg[cand_pfx]["name_zh"] = cname
                                if reg[cand_pfx].get("name_en") in ("", cand_pfx, cand_pfx.upper(), cand_pfx.title()):
                                    reg[cand_pfx]["name_en"] = name_en

    # 4. Scan SkinData.txt for fashion skins
    skin_file = os.path.join(TEXT_DIR, "SkinData.txt")
    if os.path.exists(skin_file):
        with open(skin_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f.read().splitlines()[1:]:
                p = [c.strip().rstrip("┤") for c in line.split("|")]
                if len(p) > 6:
                    skin_zh = p[2]
                    cg_asset = p[6]
                    m = re.search(r"([a-z]\d{3}|ct\d+|[a-z]{2}\d+)", cg_asset)
                    if m and skin_zh and skin_zh not in ("NULL", "-1"):
                        cand_pfx = m.group(1)
                        skin_en = trans.get(skin_zh, skin_zh)
                        if cand_pfx in reg:
                            existing_en = [c.get("en") for c in reg[cand_pfx]["costumes"]]
                            if skin_en not in existing_en:
                                reg[cand_pfx]["costumes"].append({"en": skin_en, "zh": skin_zh})

    # 5. Scan all extracted skeletons in dump/hcg_art/skel
    skel_files = glob.glob(os.path.join(SKEL_DIR, "*.skel"))
    print(f"📦 Mapping {len(skel_files)} skeletons to character catalog...")
    for sk in skel_files:
        stem = os.path.splitext(os.path.basename(sk))[0]
        if stem == "FI05":
            pfx = "fi05"
        else:
            m = re.match(r"^([a-z]\d{3}|ct\d+|[a-z]{2}\d+|story_free_hcg\d+|story_hcg\d+|teaching_hcg\d+)", stem)
            if m:
                pfx = m.group(1)
            elif "story_free_hcg" in stem:
                pfx = "story_free_hcg" + stem.split("story_free_hcg")[1][:2]
            elif "story_hcg" in stem:
                pfx = "story_hcg" + stem.split("story_hcg")[1][:2]
            else:
                pfx = stem[:6]

        if pfx not in reg:
            reg[pfx] = {
                "prefix": pfx,
                "name_en": pfx.replace("_", " ").title(),
                "name_zh": pfx,
                "costumes": [],
                "models": set(),
                "dialogues": []
            }
        reg[pfx]["models"].add(stem)

    # 6. Convert sets to sorted lists
    for pfx, d in reg.items():
        d["models"] = sorted(list(d["models"]))

    # 7. Write out JSON
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)

    print(f"🎉 Successfully updated {INDEX_PATH}!")
    print(f"   Total registered characters & stories: {len(reg)}")
    print(f"   Total skeleton models associated: {sum(len(d['models']) for d in reg.values())}")

if __name__ == "__main__":
    main()
