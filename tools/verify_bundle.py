"""Verify offline bundle integrity using only Python standard library."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for entry in manifest['files']:
    p=root/entry['file']
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    if h.hexdigest()!=entry['sha256']:raise SystemExit('SHA256 mismatch: '+entry['file'])
print('Bundle hashes OK:',len(manifest['files']),'files')
