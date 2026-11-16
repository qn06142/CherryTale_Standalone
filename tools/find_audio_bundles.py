import json

with open('hcg_manifest/index_save.txt', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

for term in ['sound', 'audio', 'bgm', 'voice', 'music', 'b004', 'hstory', 'se_']:
    matches = [k for k in manifest.keys() if term in k.lower()]
    print(f'Term "{term}": {len(matches)} matches')
    if matches:
        print('  Sample:', matches[:5])
