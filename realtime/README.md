# TaleemPK realtime gateway

This tiny Node service is the WebSocket invalidation layer for TaleemPK v4.4.

It does **not** store or proxy chat message bodies. The PHP website/API remains the source of truth. Android still sends normal messages through `api/mobile.php`; after a successful send it publishes a room event over WebSocket so other active Android clients refresh immediately.

## WebSocket deployment

Set this environment variable on the realtime service:

- `TALEEMPK_REALTIME_SECRET` — a long random secret.

After deployment, set these on the website/PHP hosting:

- `TALEEMPK_WS_URL=wss://<your-realtime-host>`
- `TALEEMPK_REALTIME_SECRET=<the-same-secret>`

The app receives short-lived signed room tickets from the authenticated mobile API. The WebSocket service never receives passwords or mobile bearer tokens.

## Firebase Cloud Messaging

The v4.4 website API supports FCM HTTP v1. Configure these environment variables on the PHP hosting:

- `FIREBASE_PROJECT_ID`
- `FIREBASE_ANDROID_APP_ID`
- `FIREBASE_SENDER_ID`
- `FIREBASE_API_KEY`
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_PRIVATE_KEY`

The first four are public Android Firebase options returned only to an authenticated app session. The client email/private key remain server-side. The app registers each FCM token against the current revocable mobile session; revoked/expired sessions are excluded from delivery.

If WebSocket or Firebase is not configured, TaleemPK stays usable: polling remains the fallback and login/message sending do not fail.
