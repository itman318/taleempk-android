# TaleemPK Flutter

Premium Flutter Android app for `https://taleempk.online`, sharing the existing
TaleemPK users, content and chat data through a revocable bearer-token API.

## What is included

- Native premium splash, login, registration and email 2FA
- Home dashboard with live community statistics
- Native feed, publishing, likes and comments
- Learning modules: study, library, quizzes, groups, planner and results
- Native inbox and low-latency chat with replies, reactions, attachments,
  voice notes, typing/recording presence, delivered/read state and polling
- Notifications, profile editing, privacy controls and support requests
- Encrypted Android credential storage, HTTPS-only policy and session expiry
- GitHub Actions APK build on every push to `main`

## Server installation

Upload `backend/api/mobile.php` to the website as `api/mobile.php`. The supplied
`TaleemPK-v23.48-flutter-ready.zip` already includes the matching migration and
native API gateway support. Loading the website once creates the device-session
tables automatically.

## Build

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

The API URL can be changed without editing source:

```bash
flutter build apk --release --dart-define=STUDYHUB_API_URL=https://example.com/api/mobile.php
```
