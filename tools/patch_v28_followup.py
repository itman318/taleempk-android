from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / 'flutter/lib/screens/auth_screen.dart'
CONV = ROOT / 'flutter/lib/screens/conversations_screen.dart'

# 2FA: digitsOnly is a static formatter object, not a const list element.
auth = AUTH.read_text()
old = "inputFormatters: const [FilteringTextInputFormatter.digitsOnly],"
new = "inputFormatters: [FilteringTextInputFormatter.digitsOnly],"
if old not in auth:
    raise RuntimeError('2FA formatter anchor missing')
auth = auth.replace(old, new, 1)
AUTH.write_text(auth)

# Messages search: clearing the filter must also clear visible input text.
conv = CONV.read_text()
old_state = "class _ConversationsScreenState extends State<ConversationsScreen> {\n  List<Conversation> all = const [];"
new_state = "class _ConversationsScreenState extends State<ConversationsScreen> {\n  final searchController = TextEditingController();\n  List<Conversation> all = const [];"
if old_state not in conv:
    raise RuntimeError('inbox state anchor missing')
conv = conv.replace(old_state, new_state, 1)

old_dispose = "  void dispose() {\n    refreshTimer?.cancel();\n    super.dispose();\n  }"
new_dispose = "  void dispose() {\n    refreshTimer?.cancel();\n    searchController.dispose();\n    super.dispose();\n  }"
if old_dispose not in conv:
    raise RuntimeError('inbox dispose anchor missing')
conv = conv.replace(old_dispose, new_dispose, 1)

old_field = "            child: TextField(\n              onChanged: (v) => setState(() => query = v),"
new_field = "            child: TextField(\n              controller: searchController,\n              onChanged: (v) => setState(() => query = v),"
if old_field not in conv:
    raise RuntimeError('inbox search field anchor missing')
conv = conv.replace(old_field, new_field, 1)

old_clear = "onPressed: () => setState(() => query = ''),"
new_clear = "onPressed: () {\n                          searchController.clear();\n                          setState(() => query = '');\n                        },"
if old_clear not in conv:
    raise RuntimeError('inbox clear anchor missing')
conv = conv.replace(old_clear, new_clear, 1)
CONV.write_text(conv)

print('v2.8 follow-up applied')
