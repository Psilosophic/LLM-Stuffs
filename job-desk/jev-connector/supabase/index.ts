// Supabase Edge Function host for the Jev job ranker. Logic lives in ./core.js.
// Secrets: TYPESAFE_API_KEY (required), CONNECTOR_KEY (required), JEV_MODEL (optional).
// Requests must carry ?key=<CONNECTOR_KEY>. Deploy with verify_jwt off: the key check below is the auth.
// Deploy index.ts together with ../core.js uploaded as core.js.
import { handleRpc, setEnv } from "./core.js";

setEnv((k: string) => Deno.env.get(k));

Deno.serve(async (req: Request) => {
  const key = Deno.env.get("CONNECTOR_KEY");
  const url = new URL(req.url);
  if (!key || url.searchParams.get("key") !== key) return new Response("Not found", { status: 404 });
  if (req.method !== "POST") return new Response(null, { status: 405, headers: { Allow: "POST" } });
  let body: unknown;
  try { body = await req.json(); }
  catch { return Response.json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }, { status: 400 }); }
  const batch = Array.isArray(body);
  const replies = (await Promise.all((batch ? body as unknown[] : [body]).map(handleRpc))).filter(Boolean);
  if (!replies.length) return new Response(null, { status: 202 });
  return Response.json(batch ? replies : replies[0]);
});
