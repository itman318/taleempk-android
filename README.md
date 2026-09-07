# TaleemPK Android

Current app version: **1.0.1**

Professional native Android client for **TaleemPK / StudyHub**.

- Kotlin and Jetpack Compose; no WebView or PWA wrapper.
- Package: `online.taleempk.studyhub`
- Minimum Android: 7.0 (API 24)
- Production API: `https://taleempk.online/api/mobile.php`
- Existing website accounts, roles and data are shared through the same backend.
- Native email/username login, email 2FA, encrypted device token storage, dashboard,
  feed, conversations, text messages, attachments and voice-note recording/playback.
- HTTPS-only network policy and verified TaleemPK App Link foundation.
- The app requests only network and microphone permissions; microphone access is
  requested when the member starts a voice note.

## Required website version

Upload the companion StudyHub **v23.40 mobile API** package to the website before
signing in from the APK. Loading any website page once runs schema migration 85,
which creates revocable native-device sessions and short-lived 2FA challenges.

## Build

GitHub Actions runs Android lint and creates an installable debug-signed APK on
every push to `main`. Open **Actions → Build TaleemPK Android APK**, then download
the `TaleemPK-Android-APK` artifact.

For Play Store publishing, create a private release keystore and add a release
signing configuration. Never commit the keystore or passwords to the repository.
