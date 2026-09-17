# TaleemPK v4.9 audit and upgrade notes

Scope: Flutter branch `flutter-premium-v2`, including its final build-time
transforms, shared widgets, API clients, chat/outbox, profile, feed, security,
inbox and Android build configuration. The supplied website API files were
compared with the client's 67 literal action names: none were absent. This is
an interface-name check, not proof of live endpoint behavior or feature parity.

## Corrected

- Profile badge was pushed to the far edge by an Expanded name. The new
  ProfileIdentity widget keeps a six-pixel gap and handles long/scaled text.
- Verification-only cards no longer show a divider followed by empty space;
  profiles with only experience/availability still show those details.
- Profile tabs, feed filters/pagination and archive/inbox requests reject stale
  results rather than mixing data between views.
- Profile activity failures show an error and retry instead of claiming empty.
- Security screen now actually loads blocked users; unblock is protected from
  duplicate taps. Hosting guidance no longer assumes public_html is the root.
- Social API preserves the real server validation message/status.
- Viewer-dependent profile caches are isolated by API client and login session.
- Late mobile/social responses cannot invalidate a newly signed-in session.
- Upload response-body reads have deadlines as well as request-send deadlines.
- Empty 2xx responses are no longer treated as confirmed message delivery.
- Chat duplicate sends and restoring an already-disposed composer are guarded.
- Outbox writes are serialized; drafts and outbox records are account-scoped.
- Local sign-out completes on network failure; theme switching works even when
  storing the preference fails.
- Avatar initials remain available when images fail; Unicode initials are not
  split into invalid surrogate fragments.
- Inbox background refresh stops requesting data while the app is not resumed.

## Verification

All existing source-generation stages and deep source assertions reproduced
successfully from a clean checkout. Dart source parsing and the realtime
JavaScript syntax check succeeded locally. New tests cover name/badge layout
in light/dark themes and large text, avatar initials, blocked-user loading,
server errors, session/cache isolation, empty responses, concurrent outbox writes
and separate account queues. GitHub Actions is the authoritative analyzer,
Flutter-test, PHP-syntax and APK-build result for the final commit.

## Important limitations and upgrade notes

- This is not a claim that every workflow is bug-free. Live authenticated
  two-device messaging, calls, camera/microphone, offline/resume and push-delivery
  testing still require real devices and configured services.
- SMTP/email delivery is server configuration. No email account, password,
  database, installer or two-factor requirement was changed.
- Firebase/push, realtime hosting and production signing need the owner's
  configuration. The current workflow falls back to debug signing when private
  release signing is absent; its APK is a test build, not a Play Store release.
  Update installation requires the same signing certificate as the installed
  APK. Do not uninstall blindly: local-only drafts/downloads could be lost.
- Existing unscoped drafts/outboxes are preserved but not automatically assigned
  to the current account. Send/review pending messages in the old app before
  upgrading. New v4.9 queues are separate per account.
- No live website deployment, database reset, branch merge or production data
  change is included. Backend files are unchanged by v4.9.
- The repository still has a long build-time rewrite pipeline. This patch adds
  fail-fast markers and tests; consolidating generated source is a separate
  maintainability project, not silently mixed into this release.

Version: `4.9.0+490`. Universal output: `TaleemPK-v4.9.0-Universal.apk`.
