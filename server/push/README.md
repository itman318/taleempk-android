# TaleemPK Push Service

Deploy this folder as the cPanel Node.js application mounted at `/push`.

Required environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS=/home/pgbicnpel/firebase-private/firebase-service-account.json`
- `TALEEMPK_PUSH_SECRET=<same strong secret used by the PHP backend>`

The PHP backend should use `TALEEMPK_PUSH_URL=https://taleempk.online/push/send`.

Endpoints:
- `GET /health` — verifies that Firebase credentials can obtain an access token.
- `POST /send` — authenticated FCM multicast endpoint. Requires `Authorization: Bearer <TALEEMPK_PUSH_SECRET>`.

Never place the Firebase service-account JSON under public_html and never commit it to Git.
