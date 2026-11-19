#!/usr/bin/env node
/**
 * In-memory FIFO job queue for a single Claude container.
 * POST /chat enqueues and sets `from` to the sender's Docker container name (DNS reverse).
 * GET /next (localhost only) dequeues one job for the session.
 */

const http = require("http");
const dns = require("dns").promises;

// FIFO lives in this process only: push on enqueue, shift on dequeue.
// Jobs are lost if the process exits. A popped job is gone even if the turn stops early.
const queue = [];

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function isLocalhost(remoteAddress) {
  return (
    remoteAddress === "127.0.0.1" ||
    remoteAddress === "::ffff:127.0.0.1" ||
    remoteAddress === "::1"
  );
}

async function senderName(remoteAddress) {
  const ip = String(remoteAddress || "").replace(/^::ffff:/, "");
  if (isLocalhost(remoteAddress)) {
    return null;
  }
  try {
    const [host] = await dns.reverse(ip);
    return host ? host.split(".")[0] : null;
  } catch {
    return null;
  }
}

const ALLOW_ANON = process.env.SWARM_ALLOW_ANON === "1";
const REQUIRED = ["traceID", "repoUrl", "workingBranch", "prompt"];

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "POST" && req.url === "/chat") {
      let job;
      try {
        job = JSON.parse(await readBody(req));
      } catch {
        process.stderr.write("[queue.js] handleChat invalid json\n");
        res.writeHead(400, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "invalid json" }));
        return;
      }
      for (const key of REQUIRED) {
        if (job[key] == null || String(job[key]).trim() === "") {
          res.writeHead(400, { "content-type": "application/json" });
          res.end(JSON.stringify({ error: `missing ${key}` }));
          return;
        }
      }
      let from = await senderName(req.socket.remoteAddress);
      if (!from && ALLOW_ANON) {
        from = null;
      } else if (!from) {
        process.stderr.write(
          `[queue.js] handleChat rejected unknown sender ${req.socket.remoteAddress}\n`
        );
        res.writeHead(403, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "unknown sender" }));
        return;
      }
      queue.push({
        traceID: job.traceID,
        repoUrl: job.repoUrl,
        workingBranch: job.workingBranch,
        prompt: job.prompt,
        from,
      });
      process.stderr.write(
        `[queue.js] handleChat enqueued from=${from} traceID=${job.traceID} depth=${queue.length}\n`
      );
      res.writeHead(202, { "content-type": "application/json" });
      res.end(JSON.stringify({ queued: queue.length }));
      return;
    }

    if (req.method === "GET" && req.url === "/next") {
      // Only this container's Claude should dequeue (curl from inside the container).
      if (!isLocalhost(req.socket.remoteAddress)) {
        process.stderr.write(
          `[queue.js] handleNext forbidden ${req.socket.remoteAddress}\n`
        );
        res.writeHead(403, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "forbidden" }));
        return;
      }
      if (queue.length === 0) {
        res.writeHead(204);
        res.end();
        return;
      }
      const job = queue.shift();
      process.stderr.write(
        `[queue.js] handleNext dequeued from=${job.from} traceID=${job.traceID} depth=${queue.length}\n`
      );
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(job));
      return;
    }

    res.writeHead(404);
    res.end();
  } catch (err) {
    process.stderr.write(
      `[queue.js] handleRequest internal_error ${err?.message ?? err}\n`
    );
    res.writeHead(500, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "internal_error" }));
  }
});

const port = Number(process.env.QUEUE_PORT || 8080);
server.listen(port, "0.0.0.0", () => {
  process.stderr.write(`[queue.js] listen on 0.0.0.0:${port}\n`);
});