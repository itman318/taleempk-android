from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'tools/v37_chat_identity_polish.py'
source = source_path.read_text(encoding='utf-8')
source = source.replace(
    "composer_start = text.find('  Widget _composer() => Container(')",
    "composer_start = text.find('  Widget _composer()')",
)
source = source.replace(
    "composer_end = text.find('  Future<void> _loadRecentEmojis()', composer_start)",
    "composer_end = text.find('  Future<void> _loadMentionMembers()', composer_start)",
)
source = source.replace(
    "upload_start = text.find('  Widget _uploadBar() => Container(')",
    "upload_start = text.find('  Widget _uploadBar()')",
)
if "composer_start = text.find('  Widget _composer()')" not in source:
    raise RuntimeError('v3.7b could not relax composer boundary')
if "composer_end = text.find('  Future<void> _loadMentionMembers()', composer_start)" not in source:
    raise RuntimeError('v3.7b could not preserve mention helpers')
if "upload_start = text.find('  Widget _uploadBar()')" not in source:
    raise RuntimeError('v3.7b could not relax upload boundary')
exec(compile(source, str(source_path), 'exec'), {'__file__': str(source_path), '__name__': '__main__'})

# Reconnect the v3.2 group-mention experience to the polished v3.7 composer.
# This keeps the cleaner messenger UI without regressing @mentions.
chat_path = ROOT / 'flutter/lib/screens/chat_screen.dart'
text = chat_path.read_text(encoding='utf-8')
start = text.find('  Widget _composer()')
end = text.find('  Future<void> _loadMentionMembers()', start)
if start < 0 or end < 0:
    raise RuntimeError('v3.7b generated composer boundary missing')
composer = r'''  Widget _composer() {
    final suggestions = _mentionSuggestions();
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .45),
          ),
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0C08142F),
            blurRadius: 14,
            offset: Offset(0, -3),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(10, 7, 10, 10),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (suggestions.isNotEmpty) ...[
            SizedBox(
              height: 42,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: suggestions.length,
                separatorBuilder: (_, _) => const SizedBox(width: 6),
                itemBuilder: (_, i) {
                  final member = suggestions[i];
                  return ActionChip(
                    visualDensity: VisualDensity.compact,
                    avatar: const Icon(
                      Icons.alternate_email_rounded,
                      size: 15,
                      color: AppColors.blue,
                    ),
                    label: Text(
                      '${member['name'] ?? member['username'] ?? ''}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onPressed: () => _insertMention(member),
                  );
                },
              ),
            ),
            const SizedBox(height: 5),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              SizedBox(
                width: 46,
                height: 46,
                child: IconButton.filledTonal(
                  tooltip: 'Photo or file',
                  onPressed: sending ? null : _pickAttachment,
                  style: IconButton.styleFrom(
                    backgroundColor: AppColors.blue.withValues(alpha: .10),
                    foregroundColor: AppColors.blue,
                  ),
                  icon: const Icon(Icons.add_rounded, size: 26),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: Theme.of(context).brightness == Brightness.dark
                        ? const Color(0xFF121D2E)
                        : const Color(0xFFF7F9FC),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55),
                    ),
                  ),
                  child: TextField(
                    controller: textController,
                    minLines: 1,
                    maxLines: 6,
                    maxLength: 4000,
                    buildCounter: (
                      _, {
                      required currentLength,
                      required isFocused,
                      maxLength,
                    }) => null,
                    onTap: () => setState(() => showEmoji = false),
                    style: TextStyle(
                      fontSize: 15.5,
                      height: 1.35,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                    decoration: InputDecoration(
                      hintText: 'Write a message…',
                      hintStyle: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant.withValues(alpha: .72),
                        fontSize: 15,
                      ),
                      isDense: true,
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: const EdgeInsets.fromLTRB(15, 12, 4, 12),
                      suffixIconConstraints: const BoxConstraints(
                        minWidth: 44,
                        minHeight: 44,
                      ),
                      suffixIcon: IconButton(
                        tooltip: 'Emoji',
                        onPressed: () => setState(() => showEmoji = !showEmoji),
                        icon: Icon(
                          showEmoji
                              ? Icons.keyboard_rounded
                              : Icons.emoji_emotions_outlined,
                          color: showEmoji
                              ? AppColors.blue
                              : Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 48,
                height: 48,
                child: IconButton.filled(
                  tooltip: textController.text.trim().isEmpty
                      ? 'Voice message'
                      : 'Send message',
                  onPressed: sending
                      ? null
                      : (textController.text.trim().isEmpty
                            ? _toggleRecording
                            : _sendText),
                  style: IconButton.styleFrom(
                    backgroundColor: AppColors.blue,
                    foregroundColor: Colors.white,
                  ),
                  icon: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 160),
                    child: Icon(
                      textController.text.trim().isEmpty
                          ? (recording ? Icons.stop_rounded : Icons.mic_rounded)
                          : Icons.send_rounded,
                      key: ValueKey(textController.text.trim().isEmpty),
                      size: 23,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

'''
text = text[:start] + composer + text[end:]
if '_mentionSuggestions();' not in text or '_insertMention(member)' not in text:
    raise RuntimeError('v3.7b mention UI was not reconnected')
chat_path.write_text(text, encoding='utf-8')
print('TaleemPK v3.7 group mention UI reconnected successfully')
