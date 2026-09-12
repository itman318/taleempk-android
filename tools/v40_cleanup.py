from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/core/api_client.dart'
text = path.read_text(encoding='utf-8')

# Legacy v3.2 generated an in-memory attachment cache. The secure attachment
# downloader later moved to direct authenticated GETs, leaving only the map
# declaration behind. Remove that dead declaration so analyzer stays clean.
patterns = [
    r'^\s*(?:static\s+)?final\s+Map<[^\n;]+>\s+_attachmentCache\s*=\s*<[^\n;]+>\{\};\s*\n',
    r'^\s*(?:static\s+)?final\s+_attachmentCache\s*=\s*<[^\n;]+>\{\};\s*\n',
    r'^\s*(?:static\s+)?final\s+Map<[^\n;]+>\s+_attachmentCache\s*=\s*\{\};\s*\n',
]
removed = 0
for pattern in patterns:
    text, count = re.subn(pattern, '', text, count=1, flags=re.M)
    removed += count
    if count:
        break

# Fallback for a single-line typed declaration in case formatting changes.
if removed == 0:
    lines = text.splitlines(True)
    kept = []
    for line in lines:
        if '_attachmentCache' in line and ('final ' in line or 'static final ' in line):
            removed += 1
            continue
        kept.append(line)
    text = ''.join(kept)

if '_attachmentCache' in text:
    raise RuntimeError('v4 cleanup: legacy _attachmentCache still referenced after cleanup')
if removed != 1:
    raise RuntimeError(f'v4 cleanup: expected one legacy cache declaration, removed {removed}')

path.write_text(text, encoding='utf-8')
print('TaleemPK v4.0 analyzer cleanup applied successfully')
