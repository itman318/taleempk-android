import 'package:flutter/material.dart';

/// Keeps the badge beside short names, while reserving room for it on long names.
class ProfileIdentity extends StatelessWidget {
  const ProfileIdentity({
    super.key,
    required this.name,
    required this.verified,
    required this.badgeColor,
  });

  final String name;
  final bool verified;
  final Color badgeColor;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: Text(
              name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w900,
                letterSpacing: -.55,
              ),
            ),
          ),
          if (verified) ...[
            const SizedBox(width: 6),
            Icon(Icons.verified_rounded,
                color: badgeColor, size: 20, semanticLabel: 'Verified account'),
          ],
        ],
      );
}
