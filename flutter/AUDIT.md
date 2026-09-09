# TaleemPK Flutter v2.1 – audit and implementation summary

## Product direction

The app is a native Flutter client, not a browser wrapper. It uses TaleemPK's
existing accounts and database through a narrow JSON API. The visual system is
navy, electric blue and violet with restrained gradients, large touch targets,
clear hierarchy and lightweight transitions.

## Implemented areas

- Premium branded splash and education-themed authentication
- Student, teacher and institute registration
- Email/username login and email two-factor challenge
- Live dashboard statistics and learning shortcuts
- Paginated feed, post publishing, questions, likes and replies
- Study, library, quiz, group, planner, result and notification modules
- Profile editing, privacy controls, dark-mode preference and support tickets
- Native conversation list and fast incremental message polling
- Replies, editing, delete-for-me/everyone, reactions, stars and read receipts
- Photo, camera, document and voice-note sending
- Typing/recording presence, recording timer and authenticated audio playback
- Offline, timeout, maintenance, expired-session and empty states

## Security decisions

- HTTPS-only Android network policy
- Random 256-bit device tokens; database stores SHA-256 digests only
- Device token stored in Android encrypted storage, never preferences
- 30-day expiry, explicit logout revocation and ten-device session ceiling
- API files require bearer membership checks; browser sessions are not exported
- Registration/login rate limits and existing website moderation gates retained
- Native CSRF exemption applies only after the bearer token is authenticated
- Android backups disabled to avoid accidental token extraction
- Authorization-header fallback for shared Apache/FastCGI hosts
- Global 401 handling returns every protected screen to sign-in immediately

## Performance decisions

- A reused HTTP client enables connection keep-alive
- Feed uses server pagination and loads the next page near the scroll boundary
- Chat requests only messages newer than the latest local ID
- Presence polling is short-lived and failures back off without blocking input
- Images are cached; list screens avoid unnecessary nested scrolling
- Client tokens make retried sends idempotent on compatible website builds
- Debounced typing and guarded polling prevent duplicate/flooded chat requests
- Secure inline image preview, file download and upload progress
- Working conversation search, mute, pin and server-compatible reactions

## Deployment verification

The Dart formatter parsed every source file successfully. The included GitHub
workflow resolves dependencies, runs `flutter analyze`, runs model tests and
builds a release APK. PHP companion changes were checked against the v23.39
schema and shared API guards; the archive's brace checker reports no issue in
the new mobile endpoint.
