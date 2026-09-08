# TaleemPK Android

Current app version: **1.3.0**

Professional native Android client for **TaleemPK / StudyHub**.

- Kotlin and Jetpack Compose; no WebView or PWA wrapper.
- Package: `online.taleempk.studyhub`
- Minimum Android: 7.0 (API 24)
- Production API: `https://taleempk.online/api/mobile.php`
- Existing website accounts, roles and data are shared through the same backend.
- Premium native login and account registration, email/username sign-in, email 2FA,
  encrypted device token storage, dashboard,
  feed and premium native chat with search, replies, editing, delete-for-me/everyone,
  reactions, stars, pins, attachments and voice recording/playback with speed control.
- Native feed publishing, likes and replies; native study, library, quiz, group,
  planner, result, notification, profile, settings and support screens.
- Companion website backend **v23.44 or newer is required**. Upload it before
  installing this APK; the app cannot repair an older server from the phone.
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
