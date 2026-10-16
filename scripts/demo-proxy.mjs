#!/usr/bin/env node
/**
 * Single-hostname reverse proxy for shareable DevDeploy demos.
 *
 *   /api/*  → API (default http://127.0.0.1:8741)
 *   /*      → Web (default http://127.0.0.1:43127)
 *
 * Point one cloudflared quick tunnel at this proxy so session cookies
 * stay first-party (SameSite=Lax) on the public hostname.
 */
import http from "node:http";
import net from "node:net";
import { URL } from "node:url";

const PROXY_PORT = Number(process.env.DEMO_PROXY_PORT || 18080);
const API_TARGET = process.env.DEMO_API_TARGET || "http://127.0.0.1:8741";
const WEB_TARGET = process.env.DEMO_WEB_TARGET || "http://127.0.0.1:43127";

function targetFor(pathname) {
  return pathname === "/api" || pathname.startsWith("/api/")
    ? API_TARGET
    : WEB_TARGET;
}

function forwardHeaders(req) {
  const headers = { ...req.headers };
  const host = req.headers.host || `127.0.0.1:${PROXY_PORT}`;
  // Upstream sees its own Host; Cloudflare TLS is terminated before us.
  delete headers.host;
  headers["x-forwarded-host"] = host;
  headers["x-forwarded-proto"] = "https";
  if (req.socket?.remoteAddress) {
    const prior = headers["x-forwarded-for"];
    headers["x-forwarded-for"] = prior
      ? `${prior}, ${req.socket.remoteAddress}`
      : req.socket.remoteAddress;
  }
  return headers;
}

function proxyHttp(req, res) {
  const incoming = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  const base = targetFor(incoming.pathname);
  const target = new URL(incoming.pathname + incoming.search, base);

  const proxyReq = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || 80,
      path: target.pathname + target.search,
      method: req.method,
      headers: {
        ...forwardHeaders(req),
        host: target.host,
      },
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );

  proxyReq.on("error", (err) => {
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    }
    res.end(`Bad gateway (${base}): ${err.message}`);
  });

  req.pipe(proxyReq);
}

function proxyUpgrade(req, socket, head) {
  const incoming = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  const base = targetFor(incoming.pathname);
  const target = new URL(incoming.pathname + incoming.search, base);
  const port = Number(target.port || 80);

  const upstream = net.connect(port, target.hostname, () => {
    const headers = forwardHeaders(req);
    headers.host = target.host;
    const lines = [
      `${req.method} ${target.pathname}${target.search} HTTP/${req.httpVersion}`,
    ];
    for (const [key, value] of Object.entries(headers)) {
      if (value === undefined) continue;
      if (Array.isArray(value)) {
        for (const item of value) lines.push(`${key}: ${item}`);
      } else {
        lines.push(`${key}: ${value}`);
      }
    }
    lines.push("", "");
    upstream.write(lines.join("\r\n"));
    if (head?.length) upstream.write(head);
    upstream.pipe(socket);
    socket.pipe(upstream);
  });

  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
}

const server = http.createServer(proxyHttp);
server.on("upgrade", proxyUpgrade);

server.listen(PROXY_PORT, "127.0.0.1", () => {
  console.log(
    `[demo-proxy] http://127.0.0.1:${PROXY_PORT}  (api=${API_TARGET}  web=${WEB_TARGET})`,
  );
});
