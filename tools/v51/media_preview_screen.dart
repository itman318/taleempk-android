import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'photo_editor_screen.dart';

class MediaPreviewScreen extends StatefulWidget {
  const MediaPreviewScreen({super.key, required this.paths, this.viewOnce = false});
  final List<String> paths;
  final bool viewOnce;
  @override
  State<MediaPreviewScreen> createState() => _MediaPreviewScreenState();
}
class _MediaPreviewScreenState extends State<MediaPreviewScreen> {
  late final List<String> paths = List.of(widget.paths);
  int selected = 0;
  bool busy = false;
  String? notice;
  Future<void> _edit() async {
    if (busy || paths.isEmpty) return;
    setState(() => busy = true);
    try {
      final result = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => PhotoEditorScreen(path: paths[selected])));
      if (mounted && result != null) setState(() => paths[selected] = result);
    } finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> _add() async {
    if (busy || widget.viewOnce || paths.length >= 20) return;
    setState(() => busy = true);
    try {
      final images = await ImagePicker().pickMultiImage(imageQuality: 92, maxWidth: 2600, maxHeight: 2600);
      if (!mounted) return;
      setState(() {
        final additions = images.map((i) => i.path).where((p) => !paths.contains(p)).toList();
        if (additions.length + paths.length > 20) notice = 'You can send up to 20 photos at a time.';
        paths.addAll(additions.take(20-paths.length));
      });
    } catch (_) { if (mounted) setState(() => notice = 'Could not select photos. Please try again.'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    return PopScope(canPop: !busy, child: Scaffold(
      appBar: AppBar(title: const Text('Review photos'), leading: IconButton(tooltip: 'Cancel sending',
        onPressed: busy ? null : () => Navigator.pop(context), icon: const Icon(Icons.close)),
        actions: [IconButton(tooltip: 'Remove selected photo', onPressed: busy ? null : () {
          if (paths.length == 1) { Navigator.pop(context); return; }
          setState(() { paths.removeAt(selected); selected = selected.clamp(0, paths.length-1); });
        }, icon: const Icon(Icons.delete_outline))]),
      body: SafeArea(child: Column(children: [
        Padding(padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6), child: Row(children: [
          Expanded(child: Text(widget.viewOnce ? 'View once photo' : '${selected+1} of ${paths.length} photos',
            style: TextStyle(color: c.onSurfaceVariant))),
          TextButton.icon(onPressed: busy ? null : _edit, icon: const Icon(Icons.crop), label: const Text('Edit / Crop'))])),
        if (notice != null) Padding(padding: const EdgeInsets.all(12), child: Text(notice!)),
        Expanded(child: Container(width: double.infinity, color: c.surfaceContainerLow,
          child: Image.file(File(paths[selected]), fit: BoxFit.contain, errorBuilder: (_, _, _) =>
            const Center(child: Text('This photo is no longer available. Remove it and select it again.'))))),
        if (paths.length > 1) SizedBox(height: 88, child: ListView.separated(scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.all(12), itemCount: paths.length, separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (context, i) => Semantics(label: 'Photo ${i+1}', selected: selected == i,
            child: InkWell(onTap: busy ? null : () => setState(() => selected = i), child: Container(width: 64,
              decoration: BoxDecoration(border: Border.all(color: selected == i ? c.primary : c.outlineVariant, width: 3),
                borderRadius: BorderRadius.circular(12)), clipBehavior: Clip.antiAlias,
              child: Image.file(File(paths[i]), fit: BoxFit.cover, errorBuilder: (_, _, _) => const Icon(Icons.broken_image_outlined))))))),
        Padding(padding: const EdgeInsets.fromLTRB(18, 14, 18, 8), child: Text('Photos are sent only when you tap Send.',
          textAlign: TextAlign.center, style: TextStyle(color: c.onSurfaceVariant, fontSize: 12))),
        Padding(padding: const EdgeInsets.fromLTRB(18, 8, 18, 18), child: Wrap(alignment: WrapAlignment.end, spacing: 12, runSpacing: 10, children: [
          if (!widget.viewOnce) OutlinedButton.icon(onPressed: busy || paths.length >= 20 ? null : _add,
            icon: const Icon(Icons.add_photo_alternate_outlined), label: const Text('Add photos')),
          FilledButton.icon(onPressed: busy ? null : () { setState(() => busy = true); Navigator.pop(context, List<String>.of(paths)); },
            icon: const Icon(Icons.send_rounded, size: 18), label: Text(widget.viewOnce ? 'Send once' : 'Send ${paths.length}')),
        ])),
      ]))));
  }
}
