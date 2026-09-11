from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/screens/chat_screen.dart'
text = path.read_text(encoding='utf-8')

signature = 'Uint8List _processOutgoingPhoto(Map<String, dynamic> args) {'
start = text.find(signature)
if start >= 0:
    brace = text.find('{', start)
    depth = 0
    end = None
    for index in range(brace, len(text)):
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError('v3.5 cleanup could not locate end of legacy photo processor')
    while end < len(text) and text[end] == '\n':
        end += 1
    text = text[:start] + text[end:]

# The legacy processor owned these imports. The new integrated editor uses
# RenderRepaintBoundary + native processing instead, so remove dead imports.
text = text.replace("import 'dart:typed_data';\n", '')
text = text.replace("import 'package:image/image.dart' as img;\n", '')
text = text.replace("import 'package:image/image.dart';\n", '')

if '_processOutgoingPhoto' in text:
    raise RuntimeError('v3.5 cleanup failed to remove legacy photo processor')
if "package:image/image.dart" in text:
    raise RuntimeError('v3.5 cleanup failed to remove legacy image import')

path.write_text(text, encoding='utf-8')
print('TaleemPK v3.5 analyzer cleanup applied successfully')
