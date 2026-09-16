import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';

Rect cropSelection(Offset first, Offset last) {
  final a = Offset(first.dx.clamp(0, 1), first.dy.clamp(0, 1));
  final b = Offset(last.dx.clamp(0, 1), last.dy.clamp(0, 1));
  return Rect.fromLTRB(math.min(a.dx, b.dx), math.min(a.dy, b.dy), math.max(a.dx, b.dx), math.max(a.dy, b.dy));
}
Future<ui.Image> cropPixels(ui.Image image, Rect selection) async {
  final r = selection.intersect(const Rect.fromLTWH(0, 0, 1, 1));
  if (r.isEmpty || r.width * image.width < 1 || r.height * image.height < 1) {
    throw ArgumentError('Choose a larger crop area.');
  }
  final width = (r.width * image.width).round(), height = (r.height * image.height).round();
  final recorder = ui.PictureRecorder();
  Canvas(recorder).drawImageRect(image, Rect.fromLTWH(r.left * image.width, r.top * image.height,
    r.width * image.width, r.height * image.height), Rect.fromLTWH(0, 0, width.toDouble(), height.toDouble()),
    Paint()..filterQuality = FilterQuality.none);
  final picture = recorder.endRecording();
  try { return await picture.toImage(width, height); } finally { picture.dispose(); }
}
class PhotoEditorScreen extends StatefulWidget {
  const PhotoEditorScreen({super.key, required this.path});
  final String path;
  @override
  State<PhotoEditorScreen> createState() => _PhotoEditorScreenState();
}
class _PhotoEditorScreenState extends State<PhotoEditorScreen> {
  ui.Image? photo;
  final history = <ui.Image>[];
  final strokes = <_Stroke>[];
  bool busy = true;
  String? error;
  String tool = 'none';
  double brightness = 0, contrast = 1;
  Color ink = const Color(0xFFFFCF52);
  Rect crop = const Rect.fromLTWH(.1, .1, .8, .8);
  Offset? anchor;
  String drag = 'new';
  Rect dragStart = Rect.zero;
  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() { photo?.dispose(); for (final i in history) { i.dispose(); } super.dispose(); }
  Future<void> _load() async {
    ui.ImmutableBuffer? buffer; ui.ImageDescriptor? descriptor; ui.Codec? codec;
    try {
      buffer = await ui.ImmutableBuffer.fromUint8List(await File(widget.path).readAsBytes());
      descriptor = await ui.ImageDescriptor.encoded(buffer);
      final scale = math.min(1.0, 2048 / math.max(descriptor.width, descriptor.height));
      codec = await descriptor.instantiateCodec(targetWidth: (descriptor.width * scale).round(),
        targetHeight: (descriptor.height * scale).round());
      final frame = await codec.getNextFrame();
      if (!mounted) { frame.image.dispose(); return; }
      setState(() { photo = frame.image; busy = false; error = null; });
    } catch (_) { if (mounted) setState(() { busy = false; error = 'This photo could not be opened.'; }); }
    finally { codec?.dispose(); descriptor?.dispose(); buffer?.dispose(); }
  }
  void _replace(ui.Image value, {ui.Image? before}) {
    if (!mounted) { value.dispose(); before?.dispose(); return; }
    if (photo != null) { history.add(before ?? photo!); if (before != null) photo!.dispose(); }
    while (history.length > 2) { history.removeAt(0).dispose(); }
    setState(() { photo = value; strokes.clear(); brightness = 0; contrast = 1; tool = 'none'; crop = const Rect.fromLTWH(.1, .1, .8, .8); });
  }
  Future<ui.Image> _flatten() async {
    final image = photo!, recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder)..drawImage(image, Offset.zero, Paint()..colorFilter = ColorFilter.matrix(photoAdjustments(brightness, contrast)));
    _paintStrokes(canvas, Size(image.width.toDouble(), image.height.toDouble()), strokes);
    final picture = recorder.endRecording();
    try { return await picture.toImage(image.width, image.height); } finally { picture.dispose(); }
  }
  Future<void> _change(String action) async {
    if (busy || photo == null) return;
    setState(() { busy = true; error = null; });
    ui.Image? source;
    try {
      source = await _flatten();
      ui.Image result;
      if (action == 'crop') {
        result = await cropPixels(source, crop);
      } else {
        final recorder = ui.PictureRecorder();
        // Each transform is rasterised against the true image bounds, never the screen frame.
        final target = Canvas(recorder);
        if (action == 'rotate') { target.translate(source.height.toDouble(), 0); target.rotate(math.pi / 2); }
        if (action == 'flip') { target.translate(source.width.toDouble(), 0); target.scale(-1, 1); }
        target.drawImage(source, Offset.zero, Paint()..filterQuality = FilterQuality.high);
        final picture = recorder.endRecording();
        result = await picture.toImage(action == 'rotate' ? source.height : source.width,
          action == 'rotate' ? source.width : source.height);
        picture.dispose();
      }
      _replace(result, before: source.clone());
    } catch (_) { if (mounted) setState(() => error = 'Could not apply the edit. Try a larger crop.'); }
    finally { source?.dispose(); if (mounted) setState(() => busy = false); }
  }
  Future<void> _save() async {
    if (busy || photo == null) return;
    if (tool == 'crop') { await _change('crop'); if (!mounted || error != null) return; }
    setState(() => busy = true);
    ui.Image? result;
    try {
      result = await _flatten();
      var bytes = await result.toByteData(format: ui.ImageByteFormat.png);
      // Keep even noisy/transparent images within the website's default 10 MB limit.
      if (bytes != null && bytes.lengthInBytes > 8 * 1024 * 1024) {
        final scale = math.min(1.0, 1536 / math.max(result.width, result.height));
        final w = (result.width * scale).round(), h = (result.height * scale).round();
        final recorder = ui.PictureRecorder();
        Canvas(recorder).drawImageRect(result, Rect.fromLTWH(0, 0, result.width.toDouble(), result.height.toDouble()),
          Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()), Paint()..filterQuality = FilterQuality.high);
        final picture = recorder.endRecording();
        final smaller = await picture.toImage(w, h); picture.dispose();
        try { bytes = await smaller.toByteData(format: ui.ImageByteFormat.png); } finally { smaller.dispose(); }
      }
      if (bytes == null) throw StateError('No image data');
      final folder = await Directory.systemTemp.createTemp('taleempk_edit_');
      final file = File('${folder.path}/edited.png');
      await file.writeAsBytes(bytes.buffer.asUint8List(), flush: true);
      if (mounted) Navigator.pop(context, file.path);
    } catch (_) { if (mounted) setState(() { busy = false; error = 'Could not save this edit. Your original photo is unchanged.'; }); }
    finally { result?.dispose(); }
  }
  void _undo() {
    if (busy) return;
    setState(() {
      if (brightness != 0 || contrast != 1) { brightness = 0; contrast = 1; }
      else if (strokes.isNotEmpty) { strokes.removeLast(); }
      else if (history.isNotEmpty) { photo?.dispose(); photo = history.removeLast(); }
      tool = 'none';
    });
  }
  void _preset(double? ratio) {
    if (photo == null) return;
    final imageRatio = photo!.width / photo!.height;
    final w = ratio == null ? .8 : math.min(.9, .9 * ratio / imageRatio);
    final h = ratio == null ? .8 : w * imageRatio / ratio;
    setState(() => crop = Rect.fromLTWH((1-w)/2, (1-h)/2, w, h));
  }
  void _start(DragStartDetails details, Size size) {
    final p = Offset(details.localPosition.dx / size.width, details.localPosition.dy / size.height);
    if (tool == 'crop') {
      anchor = p; dragStart = crop; drag = 'new';
      final corners = {'tl': crop.topLeft, 'tr': crop.topRight, 'bl': crop.bottomLeft, 'br': crop.bottomRight};
      for (final e in corners.entries) {
        if (Offset((e.value.dx-p.dx)*size.width, (e.value.dy-p.dy)*size.height).distance < 28) { drag = e.key; break; }
      }
      if (drag == 'new' && crop.contains(p)) drag = 'move';
    } else if (tool == 'draw' || tool == 'hide') {
      setState(() => strokes.add(_Stroke(tool == 'hide' ? Colors.black : ink, tool == 'hide' ? .055 : .008, [p])));
    }
  }
  void _drag(DragUpdateDetails details, Size size) {
    final p = Offset((details.localPosition.dx / size.width).clamp(0, 1), (details.localPosition.dy / size.height).clamp(0, 1));
    if (tool == 'crop' && anchor != null) {
      setState(() {
        if (drag == 'move') {
          crop = dragStart.shift(Offset((p.dx-anchor!.dx).clamp(-dragStart.left, 1-dragStart.right),
            (p.dy-anchor!.dy).clamp(-dragStart.top, 1-dragStart.bottom)));
        } else {
          final opposite = switch(drag) {'tl' => dragStart.bottomRight, 'tr' => dragStart.bottomLeft,
            'bl' => dragStart.topRight, 'br' => dragStart.topLeft, _ => anchor!};
          final next = cropSelection(opposite, p);
          if (next.width >= .03 && next.height >= .03) crop = next;
        }
      });
    } else if ((tool == 'draw' || tool == 'hide') && strokes.isNotEmpty) {
      setState(() => strokes.last.points.add(p));
    }
  }
  @override
  Widget build(BuildContext context) {
    final image = photo;
    return PopScope(canPop: !busy, child: Scaffold(backgroundColor: const Color(0xFF101521),
      appBar: AppBar(backgroundColor: const Color(0xFF101521), foregroundColor: Colors.white,
        title: const Text('Edit photo'), leading: IconButton(tooltip: 'Cancel edits', onPressed: busy ? null : () => Navigator.pop(context),
          icon: const Icon(Icons.close)), actions: [TextButton(onPressed: busy || image == null ? null : _save,
            child: const Text('Done', style: TextStyle(color: Color(0xFFC8F4DD), fontWeight: FontWeight.w800)))]),
      body: SafeArea(child: Column(children: [
        if (busy) const LinearProgressIndicator(),
        if (error != null) Padding(padding: const EdgeInsets.all(12), child: Text(error!, style: const TextStyle(color: Colors.orangeAccent))),
        Expanded(child: Padding(padding: const EdgeInsets.all(18), child: image == null ? const SizedBox() :
          Center(child: AspectRatio(aspectRatio: image.width / image.height, child: LayoutBuilder(builder: (context, box) =>
            GestureDetector(onPanStart: busy ? null : (d) => _start(d, box.biggest),
              onPanUpdate: busy ? null : (d) => _drag(d, box.biggest),
              child: CustomPaint(size: box.biggest, painter: _EditorPainter(image, strokes, tool == 'crop' ? crop : null, brightness, contrast)))))))),
        if (tool == 'crop') ...[
          const Padding(padding: EdgeInsets.symmetric(horizontal: 16), child: Text('Drag corners to resize. Drag inside to move.',
            textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 12))),
          SingleChildScrollView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.all(8), child: Row(children: [
            for (final preset in <String,double?>{'Free': null, '1:1': 1, '4:5': .8, '16:9': 16/9, '9:16': 9/16}.entries)
              Padding(padding: const EdgeInsets.only(right: 8), child: ActionChip(label: Text(preset.key),
                onPressed: busy ? null : () => _preset(preset.value))),
            FilledButton(onPressed: busy ? null : () => _change('crop'), child: const Text('Apply crop'))]))],
        if (tool == 'adjust') Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: Column(children: [
          Row(children: [const SizedBox(width: 85, child: Text('Brightness', style: TextStyle(color: Colors.white70))),
            Expanded(child: Slider(value: brightness, min: -.5, max: .5,
              onChanged: busy ? null : (v) => setState(() => brightness = v)))]),
          Row(children: [const SizedBox(width: 85, child: Text('Contrast', style: TextStyle(color: Colors.white70))),
            Expanded(child: Slider(value: contrast, min: .5, max: 1.5,
              onChanged: busy ? null : (v) => setState(() => contrast = v)))])])),
        if (tool == 'draw') Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          for (final color in [const Color(0xFFFFCF52), Colors.white, const Color(0xFFF25959)])
            IconButton(tooltip: color == Colors.white ? 'White pen' : color == const Color(0xFFF25959) ? 'Red pen' : 'Yellow pen',
              onPressed: busy ? null : () => setState(() => ink = color),
              icon: Icon(ink == color ? Icons.check_circle : Icons.circle, color: color))]),
        SingleChildScrollView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.fromLTRB(12, 8, 12, 20),
          child: Row(children: [
            _button('Crop', Icons.crop, () => setState(() => tool = tool == 'crop' ? 'none' : 'crop'), active: tool == 'crop'),
            _button('Rotate', Icons.rotate_right, () => _change('rotate')),
            _button('Flip', Icons.flip, () => _change('flip')),
            _button('Draw', Icons.draw_outlined, () => setState(() => tool = tool == 'draw' ? 'none' : 'draw'), active: tool == 'draw'),
            _button('Hide', Icons.visibility_off_outlined, () => setState(() => tool = tool == 'hide' ? 'none' : 'hide'), active: tool == 'hide'),
            _button('Adjust', Icons.tune, () => setState(() => tool = tool == 'adjust' ? 'none' : 'adjust'), active: tool == 'adjust'),
            _button('Undo', Icons.undo, strokes.isEmpty && history.isEmpty && brightness == 0 && contrast == 1 ? null : _undo),
          ])),
      ]))));
  }
  Widget _button(String label, IconData icon, VoidCallback? onTap, {bool active = false}) => Padding(
    padding: const EdgeInsets.only(right: 8), child: OutlinedButton.icon(style: OutlinedButton.styleFrom(
      foregroundColor: Colors.white, backgroundColor: active ? const Color(0xFF405AC5) : Colors.transparent),
      onPressed: busy || photo == null ? null : onTap, icon: Icon(icon, size: 18), label: Text(label)));
}
class _Stroke {
  _Stroke(this.color, this.width, this.points);
  final Color color;
  final double width;
  final List<Offset> points;
}
void _paintStrokes(Canvas canvas, Size size, List<_Stroke> strokes) {
  for (final stroke in strokes) {
    final points = stroke.points.map((p) => Offset(p.dx * size.width, p.dy * size.height)).toList();
    final paint = Paint()..color = stroke.color..strokeWidth = stroke.width * size.shortestSide..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round..style = PaintingStyle.stroke;
    if (points.length == 1) { canvas.drawPoints(ui.PointMode.points, points, paint); continue; }
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final p in points.skip(1)) { path.lineTo(p.dx, p.dy); }
    canvas.drawPath(path, paint);
  }
}
class _EditorPainter extends CustomPainter {
  const _EditorPainter(this.image, this.strokes, this.crop, this.brightness, this.contrast);
  final double brightness, contrast;
  final ui.Image image;
  final List<_Stroke> strokes;
  final Rect? crop;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawImageRect(image, Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble()), Offset.zero & size,
      Paint()..filterQuality = FilterQuality.high..colorFilter = ColorFilter.matrix(photoAdjustments(brightness, contrast)));
    _paintStrokes(canvas, size, strokes);
    final r = crop;
    if (r == null) return;
    final box = Rect.fromLTRB(r.left*size.width, r.top*size.height, r.right*size.width, r.bottom*size.height);
    canvas.drawPath(Path.combine(PathOperation.difference, Path()..addRect(Offset.zero & size), Path()..addRect(box)),
      Paint()..color = const Color(0x88000000));
    canvas.drawRect(box, Paint()..color = Colors.white..style = PaintingStyle.stroke..strokeWidth = 2);
    final grid = Paint()..color = Colors.white38..strokeWidth = 1;
    for (var i=1;i<3;i++) {
      canvas.drawLine(Offset(box.left+box.width*i/3,box.top), Offset(box.left+box.width*i/3,box.bottom), grid);
      canvas.drawLine(Offset(box.left,box.top+box.height*i/3), Offset(box.right,box.top+box.height*i/3), grid);
    }
    for (final corner in [box.topLeft, box.topRight, box.bottomLeft, box.bottomRight]) {
      canvas.drawCircle(corner, 6, Paint()..color = Colors.white);
    }
  }
  @override
  bool shouldRepaint(covariant _EditorPainter oldDelegate) => true;
}

List<double> photoAdjustments(double brightness, double contrast) {
  final t = 128 * (1 - contrast) + brightness * 255;
  return [contrast,0,0,0,t, 0,contrast,0,0,t, 0,0,contrast,0,t, 0,0,0,1,0];
}
