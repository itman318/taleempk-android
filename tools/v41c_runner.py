from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runner_path = ROOT / 'tools' / 'v41b_runner.py'
runner = runner_path.read_text(encoding='utf-8')

needle = "code = compile(source, str(script_path), 'exec')\n"
if needle not in runner:
    raise RuntimeError('v4.1c compile hook missing')

patch = r'''# v4.1c: the current VoiceBubble completion handler keeps the autoplay
# decision immediately after handlingCompletion. Teach the generated v4.1
# transform that exact boundary instead of assuming try follows directly.
old_completion = """completion_marker = '  Future<void> _handleCompleted() async {\\n    if (handlingCompletion) return;\\n    handlingCompletion = true;\\n'\nif completion_marker not in voice_class:\n    raise RuntimeError('v4.1 voice completion marker missing')\nvoice_class = voice_class.replace(\n    completion_marker,\n    r'''  Future<void> _handleCompleted() async {\n    if (handlingCompletion) return;\n    handlingCompletion = true;\n    final consumeViewOnce = _isViewOnceAttachmentName(widget.message.attachmentName) &&\n        !widget.message.mine &&\n        !widget.message.playedByMe;\n''',\n    1,\n)\n"""
new_completion = """completion_marker = '  Future<void> _handleCompleted() async {\\n    if (handlingCompletion) return;\\n    handlingCompletion = true;\\n    final shouldContinue = activeVoice == this;\\n    if (shouldContinue) activeVoice = null;\\n'\nif completion_marker not in voice_class:\n    raise RuntimeError('v4.1 voice completion marker missing')\nvoice_class = voice_class.replace(\n    completion_marker,\n    r'''  Future<void> _handleCompleted() async {\n    if (handlingCompletion) return;\n    handlingCompletion = true;\n    final shouldContinue = activeVoice == this;\n    if (shouldContinue) activeVoice = null;\n    final consumeViewOnce = _isViewOnceAttachmentName(widget.message.attachmentName) &&\n        !widget.message.mine &&\n        !widget.message.playedByMe;\n''',\n    1,\n)\n"""
if old_completion not in source:
    raise RuntimeError('v4.1c completion source block missing')
source = source.replace(old_completion, new_completion, 1)

'''
runner = runner.replace(needle, patch + needle, 1)
exec(compile(runner, str(runner_path), 'exec'), {'__name__': '__main__', '__file__': str(runner_path)})
