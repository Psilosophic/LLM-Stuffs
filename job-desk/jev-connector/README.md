# Jev job ranker connector

A tiny MCP server that lets Pocket Job Desk rank jobs with TypeSafe Jev instead of Claude.
It exposes one tool, `score_jobs`. For each job it asks Jev in a single request:
- the four ai-job-search fit dimensions (technical, experience, work style, career), each as a Score
- the hard gates as Nouls: clearance, citizenship, language, location, deal-breaker
- a seniority Choice

Weights (30/25/15/30) and gate thresholds are applied in code.

The TypeSafe key stays on the server. Requests must carry `?key=<CONNECTOR_KEY>`.

## Layout

- `core.js`: all the logic (questions, scoring, MCP method handling)
- `supabase/index.ts`: Supabase Edge Function host. Deploy it with `core.js` uploaded next to it, with `verify_jwt` off, because the `?key=` check is the auth.
- `api/mcp.js`: Vercel host (alternative)

Currently deployed as the Supabase Edge Function `jev-ranker` at `https://krnecparblhtgrcqlomt.supabase.co/functions/v1/jev-ranker`.

## Environment

- `TYPESAFE_API_KEY`: your TypeSafe key
- `CONNECTOR_KEY`: a long random shared secret that goes in the connector URL. Pick it yourself; it never needs to be shared anywhere else.

On Supabase, set these under Project → Edge Functions → Secrets.
- `JEV_MODEL` (optional): defaults to `jev-latest`

## Connect it

Add it in claude.ai under Settings → Connectors → Add custom connector. Name it exactly `Jev`, and use this URL: `https://<host>/api/mcp?key=<CONNECTOR_KEY>`.

The app falls back to Claude ranking whenever the connector is missing or fails.
