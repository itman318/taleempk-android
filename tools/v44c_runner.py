from pathlib import Path

script = Path(__file__).with_name('v44_realtime_push.py')
code = script.read_text(encoding='utf-8')
start = code.index('def function_bounds(text: str, signature: str):')
end = code.index('\ndef replace_function', start)

replacement = r'''def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.4 missing function: {signature}')

    paren = text.find('(', start)
    if paren < 0:
        raise RuntimeError(f'v4.4 malformed function parameters: {signature}')
    pdepth = 0
    quote = None
    escape = False
    i = paren
    param_end = -1
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == '(':
            pdepth += 1
        elif ch == ')':
            pdepth -= 1
            if pdepth == 0:
                param_end = i
                break
        i += 1
    if param_end < 0:
        raise RuntimeError(f'v4.4 unterminated parameters: {signature}')

    arrow = text.find('=>', param_end + 1)
    body_brace = text.find('{', param_end + 1)
    if arrow >= 0 and (body_brace < 0 or arrow < body_brace):
        parens = brackets = braces = 0
        quote = None
        escape = False
        line_comment = False
        block_comment = False
        i = arrow + 2
        while i < len(text):
            ch = text[i]
            nxt = text[i + 1] if i + 1 < len(text) else ''
            if line_comment:
                if ch == '\n':
                    line_comment = False
                i += 1
                continue
            if block_comment:
                if ch == '*' and nxt == '/':
                    block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if quote is not None:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == quote:
                    quote = None
                i += 1
                continue
            if ch == '/' and nxt == '/':
                line_comment = True
                i += 2
                continue
            if ch == '/' and nxt == '*':
                block_comment = True
                i += 2
                continue
            if ch in ("'", '"'):
                quote = ch
            elif ch == '(':
                parens += 1
            elif ch == ')':
                parens -= 1
            elif ch == '[':
                brackets += 1
            elif ch == ']':
                brackets -= 1
            elif ch == '{':
                braces += 1
            elif ch == '}':
                braces -= 1
            elif ch == ';' and parens == 0 and brackets == 0 and braces == 0:
                return start, i + 1
            i += 1
        raise RuntimeError(f'v4.4 unterminated expression body: {signature}')

    brace = body_brace
    if brace < 0:
        raise RuntimeError(f'v4.4 missing function body: {signature}')
    depth = 0
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f'v4.4 unterminated function: {signature}')
'''

code = code[:start] + replacement + code[end:]
exec(compile(code, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})

# Do not assume a mute column name in older TaleemPK databases. Push delivery
# stays schema-compatible; per-chat mute handling can be added server-side once
# the canonical schema exposes a stable field.
root = script.resolve().parents[1]
for relative in ('backend/api/mobile_realtime_push_v44.php', 'flutter/backend/api/mobile_realtime_push_v44.php'):
    path = root / relative
    text = path.read_text(encoding='utf-8')
    text = text.replace(
        '"SELECT cm.user_id,COALESCE(cm.is_muted,0) is_muted\n'
        '           FROM conversation_members cm JOIN users u2 ON u2.id=cm.user_id\n',
        '"SELECT cm.user_id\n'
        '           FROM conversation_members cm JOIN users u2 ON u2.id=cm.user_id\n',
    )
    text = text.replace("        if ((int)$recipient['is_muted'] === 1) continue;\n", '')
    path.write_text(text, encoding='utf-8')

print('TaleemPK v4.4 expression-body + server compatibility runner applied successfully')
