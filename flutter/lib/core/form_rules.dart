/// Client-side guidance. The server remains authoritative for account policy.
abstract final class FormRules {
  static String? name(String? value) => (value ?? '').trim().runes.length < 3
      ? 'Enter your full name (at least 3 characters).' : null;

  static String? username(String? value) =>
      RegExp(r'^[a-zA-Z0-9_]{3,30}$').hasMatch((value ?? '').trim())
          ? null : 'Use 3–30 letters, numbers or underscores.';

  static String? email(String? value) =>
      RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch((value ?? '').trim())
          ? null : 'Enter a valid email address.';

  static String? password(String? value, {required bool creating}) {
    final length = (value ?? '').runes.length;
    if (length == 0) return 'Enter your password.';
    if (creating && length < 10) return 'Use at least 10 characters.';
    if (creating && length > 200) return 'Use no more than 200 characters.';
    return null;
  }

  static String dateLabel(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}-${value.month.toString().padLeft(2, '0')}-${value.year}';

  static String? identity(String? value) {
    final raw = (value ?? '').trim();
    if (!RegExp(r'^[0-9 -]+$').hasMatch(raw)) return 'Enter your 13-digit CNIC or B-Form number.';
    final digits = raw.replaceAll(RegExp(r'\D'), '');
    if (digits.length != 13) return 'A CNIC or B-Form number has 13 digits.';
    if (digits.startsWith('0') || RegExp(r'^(\d)\1{12}$').hasMatch(digits) ||
        '01234567890123456789'.contains(digits) || '98765432109876543210'.contains(digits)) {
      return 'Check the number on your identity document.';
    }
    return null;
  }

  static String? website(String? value) {
    final raw = (value ?? '').trim();
    if (raw.isEmpty) return null;
    final uri = Uri.tryParse(raw);
    return uri != null && const ['https', 'http'].contains(uri.scheme) &&
        uri.host.isNotEmpty && uri.userInfo.isEmpty
        ? null : 'Enter a website address starting with https://';
  }

  static bool reuseDocuments(String? status) => status == 'info';

  static String? document(String filename, int bytes) {
    final extension = filename.split('.').last.toLowerCase();
    if (!const ['jpg', 'jpeg', 'png', 'webp', 'pdf'].contains(extension)) {
      return 'Choose a JPG, PNG, WEBP or PDF file.';
    }
    if (bytes <= 0) return 'This file is empty. Choose another file.';
    // Matches the supplied server's MAX_IMAGE_SIZE * 2 (6 MiB).
    if (bytes > 6 * 1024 * 1024) return 'Choose a file smaller than 6 MB.';
    return null;
  }
}
