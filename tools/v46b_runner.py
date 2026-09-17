from pathlib import Path

script = Path(__file__).with_name('v46_deep_stability_audit.py')
source = script.read_text(encoding='utf-8')
old = """    brace = text.find('{', start)\n    if brace < 0:\n        raise RuntimeError(f'v4.6 malformed block: {signature}')\n"""
new = """    # Some Dart method signatures contain named-parameter braces before the\n    # actual function body. When the supplied signature includes the body's\n    # opening brace, use that exact final brace instead of the first one.\n    if signature.rstrip().endswith('{'):\n        brace = start + signature.rfind('{')\n    else:\n        brace = text.find('{', start)\n    if brace < 0:\n        raise RuntimeError(f'v4.6 malformed block: {signature}')\n"""
if old not in source:
    raise RuntimeError('v4.6 boundary parser marker missing')
source = source.replace(old, new, 1)
exec(compile(source, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})
print('TaleemPK v4.6 named-parameter boundary compatibility fix applied successfully')
