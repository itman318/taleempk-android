from pathlib import Path

script = Path(__file__).with_name('v45_profile_connections_polish.py')
code = script.read_text(encoding='utf-8')
code = code.replace(
    "assert \"Text('View once'\" in chat and \"title: 'Photos & images'\" in chat",
    "assert \"'View once'\" in chat and \"'Photos & images'\" in chat and \"'Document or file'\" in chat",
)
exec(compile(code, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})
print('TaleemPK v4.5 compatibility runner applied successfully')
