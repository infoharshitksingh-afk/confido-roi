// Vercel serverless function: forwards a fixed, small set of requests to Claude.
// The API key comes only from the ANTHROPIC_API_KEY environment variable and is never
// returned to the browser or written to logs. Prompts and responses are not logged either.
import { timingSafeEqual } from "node:crypto";

const MODELS = { classify: "claude-haiku-5-5", memo: "claude-sonnet-5-5" };
const MAX_TOKENS = { classify: 2000, memo: 1200 };
const MAX_PROMPT_CHARS = 60000;
const WINDOW_MS = 60_000, MAX_PER_WINDOW = 20;   // per IP, per warm instance (best effort)
const hits = new Map();

function sameOrigin(req) {
  const origin = req.headers.origin;
  if (!origin) return true;                       // same-origin GETs and some browsers omit it
  try { return new URL(origin).host === (req.headers["x-forwarded-host"] || req.headers.host); }
  catch { return false; }
}
function codeOk(given) {
  const want = process.env.ACCESS_CODE;
  if (!want) return true;
  const a = Buffer.from(String(given || "")), b = Buffer.from(want);
  return a.length === b.length && timingSafeEqual(a, b);
}
function limited(ip) {
  const now = Date.now(), h = (hits.get(ip) || []).filter(t => now - t < WINDOW_MS);
  h.push(now); hits.set(ip, h);
  return h.length > MAX_PER_WINDOW;
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  const key = process.env.ANTHROPIC_API_KEY;

  if (req.method === "GET") return res.status(200).json({ serverKey: Boolean(key), needsCode: Boolean(process.env.ACCESS_CODE) });
  if (req.method !== "POST") return res.status(405).json({ error: "method_not_allowed" });
  if (!key) return res.status(503).json({ error: "no_server_key" });
  if (!sameOrigin(req)) return res.status(403).json({ error: "forbidden" });
  if (!codeOk(req.headers["x-access-code"])) return res.status(403).json({ error: "forbidden" });
  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  if (limited(ip)) return res.status(429).json({ error: "rate_limited" });

  const body = typeof req.body === "string" ? safeParse(req.body) : (req.body || {});
  const { task, prompt } = body;
  if (!MODELS[task] || typeof prompt !== "string" || !prompt.trim() || prompt.length > MAX_PROMPT_CHARS)
    return res.status(400).json({ error: "bad_request" });

  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: MODELS[task], max_tokens: MAX_TOKENS[task], messages: [{ role: "user", content: prompt }] }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const map = { 401: "upstream_auth", 429: "rate_limited", 529: "overloaded", 503: "overloaded" };
      return res.status(r.status === 429 ? 429 : 502).json({ error: map[r.status] || "upstream_error" });
    }
    const text = (data.content || []).filter(b => b.type === "text").map(b => b.text).join("");
    return res.status(200).json({ text, stop_reason: data.stop_reason });
  } catch {
    return res.status(502).json({ error: "upstream_error" });
  }
}
function safeParse(s) { try { return JSON.parse(s); } catch { return {}; } }
