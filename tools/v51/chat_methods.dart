  bool _pickingAttachment = false;
  Future<void> _pickAttachment() async {
    if (_chatBlocked || sending || _pickingAttachment) return;
    _pickingAttachment = true;
    try {
      final choice = await showModalBottomSheet<AttachmentChoice>(context: context,
        useSafeArea: true, isScrollControlled: true,
        builder: (_) => AttachmentSheet(isGroup: widget.conversation.isGroup));
      if (!mounted || choice == null) return;
      if (choice.kind == AttachmentKind.poll) { await _createPoll(); return; }
      if (choice.kind == AttachmentKind.file) {
        final file = await FilePicker.pickFile();
        if (file?.path != null && mounted) await _upload(file!.path!);
        return;
      }
      List<String> paths;
      if (choice.kind == AttachmentKind.camera || choice.viewOnce) {
        final image = await ImagePicker().pickImage(source: choice.kind == AttachmentKind.camera
          ? ImageSource.camera : ImageSource.gallery, imageQuality: 92, maxWidth: 2600, maxHeight: 2600);
        paths = image == null ? [] : [image.path];
      } else {
        paths = (await ImagePicker().pickMultiImage(imageQuality: 92, maxWidth: 2600, maxHeight: 2600))
          .map((image) => image.path).toList();
      }
      if (paths.isNotEmpty && mounted) await _reviewImages(paths, viewOnce: choice.viewOnce);
    } catch (e) { if (mounted) showMessage(context, apiMessage(e)); }
    finally { _pickingAttachment = false; }
  }
  Future<void> _reviewImages(List<String> initialPaths, {bool viewOnce = false}) async {
    final paths = <String>[];
    for (final path in initialPaths.toSet()) {
      final file = File(path);
      if (await file.exists() && await file.length() > 256) paths.add(path);
      if (paths.length == (viewOnce ? 1 : 20)) break;
    }
    if (!mounted) return;
    if (paths.isEmpty) { showMessage(context, 'No readable photos were selected. Please try again.'); return; }
    final selected = await Navigator.push<List<String>>(context, MaterialPageRoute(
      builder: (_) => MediaPreviewScreen(paths: paths, viewOnce: viewOnce)));
    if (selected != null && selected.isNotEmpty && mounted) await _uploadManyImages(selected, viewOnce: viewOnce);
  }

