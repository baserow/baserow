/**
 * Holds a request open until the test releases it.
 *
 * A slow endpoint only makes two clicks likely to overlap. With this one the
 * spec knows the backend's request has arrived, so it knows the row's lock is
 * held, and it decides when the request finishes.
 *
 *   GET  /hold/:key             waits until :key is released
 *   GET  /control/arrived/:key  {"count": n}, how many holds :key has had
 *   POST /control/release/:key  releases every waiting and future hold on :key
 *   POST /control/reset         releases everything and forgets all counts
 */

import http from "node:http";

const PORT = Number(process.env.PORT ?? 8080);
// Long enough for any test, short enough that a test that never releases does
// not keep a backend worker forever.
const HOLD_LIMIT_MS = 60_000;

const arrivals = new Map();
const released = new Set();
const waiting = new Map();

function reply(res, status, body) {
  if (res.writableEnded) return;
  if (body === undefined) {
    res.writeHead(status);
    res.end();
    return;
  }
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function releaseKey(key) {
  released.add(key);
  for (const resolve of waiting.get(key) ?? []) resolve();
  waiting.delete(key);
}

function hold(key, req, res) {
  arrivals.set(key, (arrivals.get(key) ?? 0) + 1);
  if (released.has(key)) {
    reply(res, 200, { key });
    return;
  }
  const resolvers = waiting.get(key) ?? new Set();
  waiting.set(key, resolvers);
  const resolve = () => {
    clearTimeout(timer);
    reply(res, 200, { key });
  };
  const timer = setTimeout(() => {
    resolvers.delete(resolve);
    reply(res, 504, { key, gaveUp: true });
  }, HOLD_LIMIT_MS);
  resolvers.add(resolve);
  // The backend gave up on its own deadline. `req`'s 'close' fires as soon as
  // the request is fully received, so it is `res`'s 'close' — which fires
  // only when the connection ends, before or after the reply — that tells us
  // the client is gone.
  res.on("close", () => {
    clearTimeout(timer);
    resolvers.delete(resolve);
  });
}

const server = http.createServer((req, res) => {
  req.resume();
  const parts = new URL(req.url, "http://barrier").pathname
    .split("/")
    .filter(Boolean)
    .map(decodeURIComponent);

  if (parts[0] === "hold" && parts.length === 2) {
    hold(parts[1], req, res);
    return;
  }
  if (parts[0] === "control") {
    const [, action, key] = parts;
    if (req.method === "GET" && action === "arrived" && key) {
      reply(res, 200, { count: arrivals.get(key) ?? 0 });
      return;
    }
    if (req.method === "POST" && action === "release" && key) {
      releaseKey(key);
      reply(res, 204);
      return;
    }
    if (req.method === "POST" && action === "reset") {
      for (const key of [...waiting.keys()]) releaseKey(key);
      arrivals.clear();
      released.clear();
      reply(res, 204);
      return;
    }
  }
  reply(res, 404, { error: "unknown path" });
});

server.listen(PORT, () => {
  console.log(`barrier listening on ${PORT}`);
});
