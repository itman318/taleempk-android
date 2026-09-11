from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'tools/v37_chat_identity_polish.py'
source = source_path.read_text(encoding='utf-8')
source = source.replace(
    "composer_start = text.find('  Widget _composer() => Container(')",
    "composer_start = text.find('  Widget _composer()')",
)
source = source.replace(
    "upload_start = text.find('  Widget _uploadBar() => Container(')",
    "upload_start = text.find('  Widget _uploadBar()')",
)
if "composer_start = text.find('  Widget _composer()')" not in source:
    raise RuntimeError('v3.7b could not relax composer boundary')
if "upload_start = text.find('  Widget _uploadBar()')" not in source:
    raise RuntimeError('v3.7b could not relax upload boundary')
exec(compile(source, str(source_path), 'exec'), {'__file__': str(source_path), '__name__': '__main__'})
