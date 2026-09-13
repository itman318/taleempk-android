import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/theme.dart';

class UserAvatar extends StatelessWidget {
  const UserAvatar({
    super.key,
    this.url,
    required this.name,
    this.radius = 24,
    this.online = false,
  });
  final String? url;
  final String name;
  final double radius;
  final bool online;
  @override
  Widget build(BuildContext context) => Stack(
    children: [
      CircleAvatar(
        radius: radius,
        backgroundColor: const Color(0x183157E8),
        backgroundImage: url == null ? null : CachedNetworkImageProvider(url!),
        child: url == null
            ? Text(
                name.isEmpty ? '?' : name.substring(0, 1).toUpperCase(),
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: radius * .72,
                  color: AppColors.blue,
                ),
              )
            : null,
      ),
      if (online)
        Positioned(
          right: 0,
          bottom: 1,
          child: Container(
            width: radius * .45,
            height: radius * .45,
            decoration: BoxDecoration(
              color: AppColors.success,
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 2.5),
            ),
          ),
        ),
    ],
  );
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, required this.retry});
  final String message;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(30),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.wifi_tethering_error_rounded,
            size: 48,
            color: AppColors.muted,
          ),
          const SizedBox(height: 14),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.muted),
          ),
          const SizedBox(height: 18),
          OutlinedButton.icon(
            onPressed: retry,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Try again'),
          ),
        ],
      ),
    ),
  );
}

class EmptyView extends StatelessWidget {
  const EmptyView({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
  });
  final IconData icon;
  final String title, message;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(30),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: const BoxDecoration(
              color: Color(0x123157E8),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 38, color: AppColors.blue),
          ),
          const SizedBox(height: 18),
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 7),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.muted),
          ),
        ],
      ),
    ),
  );
}

void showMessage(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

String apiMessage(Object error) =>
    error.toString().replaceFirst('ApiException: ', '');
