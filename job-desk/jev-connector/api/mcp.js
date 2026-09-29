// Vercel host for the Jev job ranker. Logic lives in ../core.js.
// Env: TYPESAFE_API_KEY, CONNECTOR_KEY, optional JEV_MODEL. Requests must carry ?key=<CONNECTOR_KEY>.
import { handleRpc, setEnv } from "../core.js";

export const config = { maxDuration: 60 };
setEnv(k => process.env[k]);

export default async function handler(req, res) {
  const key = process.env.CONNECTOR_KEY;
  const url = new URL(req.url, "http://x");
  if (!key || url.searchParams.get("key") !== key) { res.statusCode = 404; return res.end("Not found"); }
  if (req.method !== "POST") { res.statusCode = 405; res.setHeader("Allow", "POST"); return res.end(); }
  let body = req.body;
  if (body === undefined || typeof body === "string") {
    const raw = typeof body === "string" ? body : await new Promise(r => { let d = ""; req.on("data", c => d += c); req.on("end", () => r(d)); });
    try { body = JSON.parse(raw || "null"); } catch { res.statusCode = 400; return res.end(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } })); }
  }
  const batch = Array.isArray(body);
  const replies = (await Promise.all((batch ? body : [body]).map(handleRpc))).filter(Boolean);
  if (!replies.length) { res.statusCode = 202; return res.end(); }
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(batch ? replies : replies[0]));
}
