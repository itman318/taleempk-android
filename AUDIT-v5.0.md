# TaleemPK 5.0 — account and verification review

## Changes

- Signup has Profile, Contact and Security steps, clear role selection, an actual date picker, matching password confirmation and persistent server feedback.
- Login accepts existing passwords without imposing the new-account length policy; in-flight submissions cannot be duplicated.
- Email recovery and two-factor dialogs own their controllers, scroll above the keyboard, handle network errors and check widget lifetime after async clipboard/API work. Two-factor authentication remains enabled.
- Verification has separate Details, Documents and Review steps, an explicit declaration, upload progress, reviewer feedback and a guarded withdrawal action.
- Identity and role documents from previous submissions are reused only when the server status is `info`. Rejected, expired and withdrawn applications require fresh uploads, matching the supplied PHP API.
- Cancelling a picker preserves the selected file. Missing local paths, empty files, unsupported extensions and files over the supplied server's 6 MiB limit produce feedback. Replacement and undo are explicit.
- Role-specific fields, CNIC/B-Form and HTTP(S) website validation match the supplied deployment. The server still applies authoritative policy and file validation.
- Shared controls have consistent sizing, wrapping error text and light/dark styling. Existing v4.9 profile badge, secure outbox and session fixes are preserved.

## Validation scope

The build workflow regenerates the complete application before analysis, widget tests, regression assertions, PHP syntax checks and Node syntax checks. It produces a universal APK plus individual ABI APKs. Widget tests exercise narrow screens, enlarged text, both signup themes, validation, document retention, declarations and duplicate submissions. Form previews are produced from rendered widgets.

This is a source and automated workflow review, not an exhaustive production or physical-device certification. It does not establish that every existing feature or every Android device is bug-free.

## Deployment dependencies

- SMTP, email delivery, live admin verification and real-user registration require checks on the installed server. No email/2FA bypass is introduced.
- Push delivery, realtime calling and background behaviour depend on service configuration and real-device testing.
- The repository builds with its existing debug-signing fallback when private release signing is absent. Production updates require the same private signing key as the installed app. Do not recommend uninstalling an existing app as a substitute for signing continuity.
- Android minSdk remains 24 (Android 7.0); universal packaging includes ARM32, ARM64 and x86_64. Device policy, storage, signing and backend availability still affect installation/login.
- No website deployment or database mutation is required by the form redesign. The installed API must match the reviewed API contract.

## Source generation

The repository stores baseline screens that are rewritten by historical generators. `tools/v50_premium_forms.py` runs last, after v49, and installs the reviewed form templates. Keep that workflow order; editing generated baseline screens alone does not update the final APK.
