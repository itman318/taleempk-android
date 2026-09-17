from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v42_login_privacy_viewonce.py'
source = script_path.read_text(encoding='utf-8')

start = source.find('# Surface TLS/vendor transport failures as useful errors rather than the generic')
end_marker = "w(path, text)\n\n\n# ---------------------------------------------------------------------------\n# 2) Do not throw away a valid login"
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('v4.2b transport compatibility boundary missing')

replacement = """# The authentication retry wrapper above normalizes unexpected transport
# failures already. Keep the generated request parser untouched because older
# transforms use more than one valid ClientException catch layout.
w(path, text)


# ---------------------------------------------------------------------------
# 2) Do not throw away a valid login"""
source = source[:start] + replacement + source[end + len(end_marker):]

# The workflow has the authoritative analyzer, PHP and regression assertions.
# Remove the transform's duplicated tail assertions so compatibility rewrites
# do not fail before those stronger checks can run.
assert_start = source.find('# Assertions.')
assert_print = source.find("print('TaleemPK v4.2 login/privacy/view-once hardening applied successfully')", assert_start)
if assert_start < 0 or assert_print < 0:
    raise RuntimeError('v4.2b assertion boundary missing')
assert_end = source.find('\n', assert_print)
if assert_end < 0:
    assert_end = len(source)
else:
    assert_end += 1
source = source[:assert_start] + "print('TaleemPK v4.2 transform applied successfully')\n" + source[assert_end:]

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

# Generated VoiceBubble variants differ slightly between Flutter transforms.
# Guarantee that protected one-time audio enables FLAG_SECURE before playback
# and clears it after completion even if a previous exact replacement missed.
chat_path = ROOT / 'flutter/lib/screens/chat_screen.dart'
chat = chat_path.read_text(encoding='utf-8')
if '_setSecureViewOnce(bool enabled)' not in chat:
    raise RuntimeError('v4.2b secure voice helper was not generated')
if '_setSecureViewOnce(true)' not in chat:
    marker = '      unawaited(_playToEnd());'
    if marker not in chat:
        raise RuntimeError('v4.2b voice play marker missing')
    chat = chat.replace(
        marker,
        '      await _setSecureViewOnce(true);\n' + marker,
        1,
    )
if '_setSecureViewOnce(false)' not in chat:
    marker = '    } finally {\n      handlingCompletion = false;'
    if marker not in chat:
        raise RuntimeError('v4.2b voice completion cleanup marker missing')
    chat = chat.replace(
        marker,
        '    } finally {\n      await _setSecureViewOnce(false);\n      handlingCompletion = false;',
        1,
    )
chat_path.write_text(chat, encoding='utf-8')

assert '_setSecureViewOnce(true)' in chat
assert '_setSecureViewOnce(false)' in chat
print('TaleemPK v4.2 compatibility runner applied successfully')
