from pathlib import Path
import re
import runpy

# v32_upgrade.py injects Dart source snippets that intentionally contain
# backslashes (for example RegExp(r'\\s')). Python's re.sub normally treats
# backslashes in a replacement string as replacement escapes. For this
# source-patching script we always want replacement text to be literal.
_original_sub = re.sub


def _literal_sub(pattern, repl, string, count=0, flags=0):
    if isinstance(repl, str):
        return _original_sub(pattern, lambda _match: repl, string, count=count, flags=flags)
    return _original_sub(pattern, repl, string, count=count, flags=flags)


re.sub = _literal_sub
runpy.run_path(str(Path(__file__).with_name('v32_upgrade.py')), run_name='__main__')
