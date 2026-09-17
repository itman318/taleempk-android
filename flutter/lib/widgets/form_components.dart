import 'package:flutter/material.dart';

class FormSection extends StatelessWidget {
  const FormSection({super.key, required this.title, required this.icon,
    this.subtitle, required this.children});
  final String title;
  final String? subtitle;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            Container(width: 38, height: 38,
              decoration: BoxDecoration(color: colors.primary.withValues(alpha: .09),
                borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, color: colors.primary, size: 21)),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              if (subtitle != null) Text(subtitle!, style: TextStyle(
                color: colors.onSurfaceVariant, fontSize: 12, height: 1.4)),
            ])),
          ]),
          const SizedBox(height: 20),
          ...children,
        ]),
      ),
    );
  }
}

class FlowSteps extends StatelessWidget {
  const FlowSteps({super.key, required this.labels, required this.current});
  final List<String> labels;
  final int current;
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (var i = 0; i < labels.length; i++) Expanded(child: Semantics(
        label: 'Step ${i + 1} of ${labels.length}, ${labels[i]}${i == current ? ', current' : ''}',
        child: Column(children: [
          AnimatedContainer(duration: const Duration(milliseconds: 180),
            width: 30, height: 30,
            decoration: BoxDecoration(shape: BoxShape.circle,
              color: i <= current ? colors.primary : colors.surfaceContainerHighest),
            child: Center(child: i < current
                ? Icon(Icons.check_rounded, color: colors.onPrimary, size: 17)
                : Text('${i + 1}', style: TextStyle(fontWeight: FontWeight.w800,
                    color: i == current ? colors.onPrimary : colors.onSurfaceVariant)))),
          const SizedBox(height: 6),
          Text(labels[i], textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, fontWeight: i == current ? FontWeight.w800 : FontWeight.w500,
              color: i == current ? colors.primary : colors.onSurfaceVariant)),
        ]),
      )),
    ]);
  }
}

class RoleSelector extends StatelessWidget {
  const RoleSelector({super.key, required this.value, required this.onChanged});
  final String value;
  final ValueChanged<String>? onChanged;
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    const roles = [
      ('student', 'Student', 'Learn, practise and connect', Icons.school_outlined),
      ('teacher', 'Teacher', 'Share knowledge and guide learners', Icons.co_present_outlined),
      ('institute', 'Institute', 'Represent your learning community', Icons.account_balance_outlined),
    ];
    return Column(children: [for (final role in roles) Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Semantics(selected: value == role.$1, child: Material(
        color: value == role.$1 ? colors.primary.withValues(alpha: .07) : colors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: value == role.$1 ? colors.primary : colors.outlineVariant)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(onTap: onChanged == null ? null : () => onChanged!(role.$1),
          child: Padding(padding: const EdgeInsets.all(13), child: Row(children: [
            Icon(role.$4, color: value == role.$1 ? colors.primary : colors.onSurfaceVariant),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(role.$2, style: const TextStyle(fontWeight: FontWeight.w800)),
              Text(role.$3, style: TextStyle(fontSize: 12, color: colors.onSurfaceVariant)),
            ])),
            const SizedBox(width: 8),
            Icon(value == role.$1 ? Icons.check_circle_rounded : Icons.radio_button_unchecked,
              color: value == role.$1 ? colors.primary : colors.outline, size: 21),
          ])),
        ),
      )),
    )]);
  }
}

class FormNotice extends StatelessWidget {
  const FormNotice(this.message, {super.key, this.isError = false,
    this.icon = Icons.info_outline_rounded});
  final String message;
  final bool isError;
  final IconData icon;
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final accent = isError ? colors.error : colors.primary;
    return Semantics(liveRegion: true, child: Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: accent.withValues(alpha: .07),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accent.withValues(alpha: .18))),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(isError ? Icons.error_outline_rounded : icon, size: 20, color: accent),
        const SizedBox(width: 10),
        Expanded(child: Text(message, style: TextStyle(color: colors.onSurface,
          height: 1.45, fontSize: 13))),
      ]),
    ));
  }
}

class PrimaryAction extends StatelessWidget {
  const PrimaryAction({super.key, required this.label, required this.onPressed,
    this.busy = false, this.icon = Icons.arrow_forward_rounded});
  final String label;
  final VoidCallback? onPressed;
  final bool busy;
  final IconData icon;
  @override
  Widget build(BuildContext context) => FilledButton.icon(
    onPressed: busy ? null : onPressed,
    icon: busy ? SizedBox(width: 18, height: 18,
      child: CircularProgressIndicator(strokeWidth: 2, color: Theme.of(context).colorScheme.primary))
        : Icon(icon, size: 20),
    label: Padding(padding: const EdgeInsets.symmetric(vertical: 6),
      child: Text(label, textAlign: TextAlign.center)),
  );
}
