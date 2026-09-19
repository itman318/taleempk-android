'use strict';

const http = require('http');
const crypto = require('crypto');
const admin = require('firebase-admin');

const PORT = Number(process.env.PORT || 3000);
const SECRET = String(process.env.TALEEMPK_PUSH_SECRET || '').trim();

if (!SECRET) {
  throw new Error('TALEEMPK_PUSH_SECRET is required');
}

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.applicationDefault(),
  });
}

function json(res, status, body) {
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  });
  res.end(JSON.stringify(body));
}

function authorized(req) {
  const header = String(req.headers.authorization || '');
  const expected = `Bearer ${SECRET}`;
  const a = Buffer.from(header);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.setEncoding('utf8');
    req.on('data', chunk => {
      raw += chunk;
      if (raw.length > 262144) {
        reject(new Error('payload_too_large'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        reject(new Error('invalid_json'));
      }
    });
    req.on('error', reject);
  });
}

function cleanData(data) {
  const out = {};
  if (!data || typeof data !== 'object' || Array.isArray(data)) return out;
  for (const [key, value] of Object.entries(data)) {
    if (!key) continue;
    out[String(key)] = value == null ? '' : String(value);
  }
  return out;
}

async function sendPush(body) {
  const tokens = [...new Set(
    (Array.isArray(body.tokens) ? body.tokens : [])
      .map(value => String(value || '').trim())
      .filter(Boolean),
  )].slice(0, 500);
  if (!tokens.length) return { sent: 0, failed: 0, invalid_tokens: [] };

  const title = String(body.title || 'TaleemPK').slice(0, 120);
  const text = String(body.body || 'You have a new update.').slice(0, 500);
  const data = cleanData(body.data);

  const response = await admin.messaging().sendEachForMulticast({
    tokens,
    notification: { title, body: text },
    data,
    android: {
      priority: 'high',
      notification: {
        channelId: 'taleempk_messages',
        sound: 'default',
        visibility: 'private',
        priority: 'high',
      },
    },
  });

  const invalid = [];
  response.responses.forEach((item, index) => {
    if (item.success) return;
    const code = String(item.error && item.error.code || '');
    if (
      code.includes('registration-token-not-registered') ||
      code.includes('invalid-registration-token')
    ) invalid.push(tokens[index]);
  });
  return {
    sent: response.successCount,
    failed: response.failureCount,
    invalid_tokens: invalid,
  };
}

const server = http.createServer(async (req, res) => {
  const path = String(req.url || '').split('?')[0].replace(/\/+$/, '') || '/';

  if (req.method === 'GET' && (path === '/' || path === '/health' || path === '/push' || path === '/push/health')) {
    try {
      await admin.app().options.credential.getAccessToken();
      json(res, 200, { success: true, service: 'TaleemPK Push Service', firebase: 'connected' });
    } catch {
      json(res, 503, { success: false, service: 'TaleemPK Push Service', firebase: 'credential_error' });
    }
    return;
  }

  if (req.method === 'POST' && (path === '/send' || path === '/push/send')) {
    if (!authorized(req)) {
      json(res, 401, { success: false, error: 'unauthorized' });
      return;
    }
    try {
      const body = await readJson(req);
      const result = await sendPush(body);
      json(res, 200, { success: true, ...result });
    } catch (error) {
      const message = String(error && error.message || 'push_failed');
      const status = message === 'payload_too_large' ? 413 : message === 'invalid_json' ? 400 : 500;
      json(res, status, { success: false, error: message });
    }
    return;
  }

  json(res, 404, { success: false, error: 'not_found' });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`TaleemPK push service listening on :${PORT}`);
});
