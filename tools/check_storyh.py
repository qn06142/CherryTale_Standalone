with open('dump/textassets/StoryHData.txt', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

header = lines[0].strip().split('|')

b004_rows = []
for line in lines[1:]:
    if 'b004' in line:
        parts = line.strip().split('|')
        row = dict(zip(header, parts))
        b004_rows.append(row)

print(f"Rows for b004 in StoryHData: {len(b004_rows)}")
for i, r in enumerate(b004_rows[:10]):
    print(f"Row {i}: id={r.get('id')} bgm={r.get('music')} voice={r.get('charSound')} sfx={r.get('sceneSound')} anim={r.get('spineAnimName')} text={r.get('text')[:30] if r.get('text') else ''}")
