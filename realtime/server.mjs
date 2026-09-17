import crypto from 'node:crypto';
import http from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';

const port = Number(process.env.PORT || 10000);
const secret = String(process.env.TALEEMPK_REALTIME_SECRET || '');
if (!secret) {
  console.error('TALEEMPK_REALTIME_SECRET is required');
  process.exit(1);
}

const b64urlDecode = (value) => {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/')
    + '='.repeat((4 - (value.length % 4)) % 4);
  return Buffer.from(padded, 'base64').toString('utf8');
};

function verifyTicket(ticket) {
  const [payloadPart, signaturePart] = String(ticket || '').split('.', 2);
  if (!payloadPart || !signaturePart) return null;
  const expected = crypto
    .createHmac('sha256', secret)
    .update(payloadPart)
    .digest('base64url');
  const left = Buffer.from(signaturePart);
  const right = Buffer.from(expected);
  if (left.length !== right.length || !crypto.timingSafeEqual(left, right)) return null;
  try {
    const payload = JSON.parse(b64urlDecode(payloadPart));
    if (!payload || Number(payload.exp || 0) <= Math.floor(Date.now() / 1000)) return null;
    const rooms = new Set(
      Array.isArray(payload.rooms)
        ? payload.rooms.map(Number).filter((value) => value > 0)
        : [],
    );
    return { uid: Number(payload.uid || 0), exp: Number(payload.exp), rooms };
  } catch {
    return null;
  }
}

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, {
      'content-type': 'application/json',
      'cache-control': 'no-store',
    });
    res.end(JSON.stringify({ ok: true, service: 'TaleemPK realtime' }));
    return;
  }
  res.writeHead(404, { 'content-type': 'text/plain' });
  res.end('Not found');
});

const wss = new WebSocketServer({ noServer: true });
const roomSockets = new Map();

function join(ws, room) {
  if (!ws.auth.rooms.has(room)) return false;
  ws.rooms.add(room);
  if (!roomSockets.has(room)) roomSockets.set(room, new Set());
  roomSockets.get(room).add(ws);
  return true;
}

function leave(ws, room) {
  ws.rooms.delete(room);
  const set = roomSockets.get(room);
  if (!set) return;
  set.delete(ws);
  if (set.size === 0) roomSockets.delete(room);
}

function cleanup(ws) {
  for (const room of [...ws.rooms]) leave(ws, room);
}

function broadcast(sender, room, payload) {
  const peers = roomSockets.get(room);
  if (!peers) return;
  const wire = JSON.stringify(payload);
  for (const peer of peers) {
    if (peer === sender || peer.readyState !== WebSocket.OPEN) continue;
    try {
      peer.send(wire);
    } catch {}
  }
}

server.on('upgrade', (req, socket, head) => {
  let ticket = '';
  try {
    const url = new URL(req.url || '/', 'http://localhost');
    ticket = url.searchParams.get('ticket') || '';
  } catch {}
  const auth = verifyTicket(ticket);
  if (!auth || auth.uid <= 0) {
    socket.write('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n');
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => {
    ws.auth = auth;
    ws.rooms = new Set();
    ws.alive = true;
    wss.emit('connection', ws);
  });
});

wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'hello', expires_at: ws.auth.exp }));

  ws.on('pong', () => {
    ws.alive = true;
  });

  ws.on('message', (raw) => {
    let frame;
    try {
      frame = JSON.parse(raw.toString());
    } catch {
      return;
    }
    const type = String(frame.type || '');
    if (type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong' }));
      return;
    }

    const room = Number(frame.conversation_id || 0);
    if (!room || !ws.auth.rooms.has(room)) return;

    if (type === 'subscribe') {
      join(ws, room);
      return;
    }
    if (type === 'unsubscribe') {
      leave(ws, room);
      return;
    }
    if (type !== 'event' || !ws.rooms.has(room)) return;

    const requested = String(frame.event || 'message');
    const event = ['message', 'presence', 'presence_clear', 'reaction', 'pin'].includes(requested)
      ? requested
      : 'message';
    broadcast(ws, room, {
      type: 'event',
      event,
      conversation_id: room,
      message_id: Math.max(0, Number(frame.message_id || 0)),
      from_user: ws.auth.uid,
    });
  });

  ws.on('close', () => cleanup(ws));
  ws.on('error', () => cleanup(ws));
});

const sweep = setInterval(() => {
  const now = Math.floor(Date.now() / 1000);
  for (const ws of wss.clients) {
    if (ws.auth.exp <= now) {
      try {
        ws.close(4001, 'Ticket expired');
      } catch {}
      cleanup(ws);
      continue;
    }
    if (!ws.alive) {
      try {
        ws.terminate();
      } catch {}
      cleanup(ws);
      continue;
    }
    ws.alive = false;
    try {
      ws.ping();
    } catch {}
  }
}, 30000);
sweep.unref();

server.listen(port, '0.0.0.0', () => {
  console.log(`TaleemPK realtime listening on :${port}`);
});
