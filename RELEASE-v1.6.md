# TaleemPK Android 1.6 / website 23.49

Install the complete website 23.49 first, preserving the existing config/config.php,
uploads and database. The backend directory is a companion update, not a complete
website. It now includes the identity cache fix in includes/auth.php; replacing
api/mobile.php alone does not repair the original false logout.

Chat: stable send acknowledgements, failed text retry, incremental reconciliation,
older history, guarded conversation switching, foreground polling, expiring typing,
recording indicators, streaming upload progress, native full emoji picker with
recent selections and variants, inline photo viewer, guarded voice playback.

Feed: anonymous/Page bylines, photos and documents, subject, followers visibility,
questions, anonymous questions, multiple uploads (up to four), saved posts, like /
dislike, repost, comments, cursor pagination and moderation acknowledgements.
Notifications: header unread badge, native activity list, mark-read controls and
new-activity banner while the app is open. Polling pauses in the background.

Known scope: this release does not implement native WebRTC calls, website E2EE key
unlock, chat polls or Page publishing/scheduling. Encrypted history is shown as a
locked item. Native Firebase background push has not been configured. No claim of
WhatsApp-equivalent throughput or live-host end-to-end verification is made.

Validation: local PHP syntax and authentication regression suite, native merge
regression tests and Android lint/build in GitHub Actions. See release delivery
for the actual final build result. Real messages were not sent to live members.
