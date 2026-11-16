import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import UnityPy
from tools.fetch_and_extract_hcg import decode_bundle_stream
from UnityPy import Environment
from UnityPy.streams import EndianBinaryReader
from UnityPy.files.SerializedFile import SerializedFile

raw_bytes = open('test_audio_bundle.bundle', 'rb').read()
stream, entries = decode_bundle_stream(raw_bytes)
print(f"Decoded stream: {len(stream)} bytes, entries: {len(entries)}")
for e in entries:
    print('  Entry:', e[0], e[1], e[2])

env = Environment()
for entry_name, offset, size, flags in entries:
    sub_stream = stream[offset : offset + size]
    reader = EndianBinaryReader(sub_stream)
    clean_name = entry_name.split("/")[-1]
    env.register_cab(clean_name, reader)
    if clean_name.endswith('.resource'):
        env.register_cab(clean_name[:-9], reader)
        env.register_cab(clean_name, reader)
    elif clean_name.endswith('.resS'):
        env.register_cab(clean_name[:-5], reader)

main_entry = (entries[0][0], entries[0][1], entries[0][2])
sf = SerializedFile(EndianBinaryReader(stream[main_entry[1] : main_entry[1] + main_entry[2]]), main_entry[0])
sf.environment = env

print(f"Objects in SerializedFile: {len(sf.objects)}")
for pid, obj in sf.objects.items():
    print(f"  obj {pid}: type={obj.type} (int={int(obj.type)})")
    rd = obj.read()
    print(f"    name: {getattr(rd, 'm_Name', '')}")
    if int(obj.type) == 83:  # AudioClip
        print("    AudioClip found!")
        print("    samples:", list(rd.samples.keys()) if isinstance(rd.samples, dict) else type(rd.samples))
        for sname, sdata in rd.samples.items():
            with open('test_audio_sample.wav', 'wb') as f:
                f.write(sdata)
            print(f"    Saved {sname} ({len(sdata)} bytes)")
