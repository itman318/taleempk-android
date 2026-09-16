import 'package:flutter/material.dart';
enum AttachmentKind { photos, camera, file, poll }
class AttachmentChoice {
  const AttachmentChoice(this.kind, this.viewOnce);
  final AttachmentKind kind;
  final bool viewOnce;
}
class AttachmentSheet extends StatefulWidget {
  const AttachmentSheet({super.key, required this.isGroup});
  final bool isGroup;
  @override
  State<AttachmentSheet> createState() => _AttachmentSheetState();
}
class _AttachmentSheetState extends State<AttachmentSheet> {
  bool once = false;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    Widget option(AttachmentKind kind, IconData icon, String title, String description, Color color) =>
      Padding(padding: const EdgeInsets.only(bottom: 10), child: Material(color: c.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20), child: InkWell(borderRadius: BorderRadius.circular(20),
          onTap: () => Navigator.pop(context, AttachmentChoice(kind, once)), child: Padding(
            padding: const EdgeInsets.all(16), child: Row(children: [Container(width: 46, height: 46,
              decoration: BoxDecoration(color: color.withValues(alpha: .13), borderRadius: BorderRadius.circular(15)),
              child: Icon(icon, color: color)), const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)), const SizedBox(height: 3),
                Text(description, style: TextStyle(fontSize: 12, color: c.onSurfaceVariant, height: 1.4))])),
              const SizedBox(width: 8), Icon(Icons.chevron_right_rounded, color: c.onSurfaceVariant)])))));
    return SingleChildScrollView(padding: EdgeInsets.fromLTRB(20, 12, 20, MediaQuery.paddingOf(context).bottom + 24),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Center(child: Container(width: 36, height: 4, decoration: BoxDecoration(color: c.outlineVariant,
          borderRadius: BorderRadius.circular(4)))), const SizedBox(height: 16),
        Row(children: [Expanded(child: Text('Share something', style: Theme.of(context).textTheme.headlineSmall)),
          IconButton(tooltip: 'Close attachments', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close))]),
        Text('Pick a photo. Make it yours. Then send.', style: TextStyle(color: c.onSurfaceVariant, fontSize: 13)),
        const SizedBox(height: 20),
        option(AttachmentKind.photos, Icons.photo_library_outlined, 'Photos & images', 'Preview, crop and edit before sending', c.primary),
        option(AttachmentKind.camera, Icons.photo_camera_outlined, 'Camera', 'Take a photo and review it', const Color(0xFF278273)),
        if (!once) ...[
          option(AttachmentKind.file, Icons.description_outlined, 'Document or file', 'Share a document from your device', const Color(0xFF9A6531)),
          option(AttachmentKind.poll, Icons.poll_outlined, 'Create poll', 'Ask your chat a question', const Color(0xFF8960BC))],
        if (!widget.isGroup) SwitchListTile.adaptive(contentPadding: EdgeInsets.zero,
          value: once, onChanged: (v) => setState(() => once = v),
          secondary: Icon(Icons.looks_one_outlined, color: c.primary),
          title: const Text('View once', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          subtitle: const Text('For a photo that can be opened once.', style: TextStyle(fontSize: 12))),
      ]));
  }
}
