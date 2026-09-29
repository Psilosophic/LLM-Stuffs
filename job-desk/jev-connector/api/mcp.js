// Jev job ranker: a minimal, stateless MCP server (Streamable HTTP, JSON responses) for Vercel.
// One tool, score_jobs, asks TypeSafe Jev a fixed set of typed questions per job and returns
// raw judgments plus a weighted fit score. The TypeSafe key never leaves this server.
//
// Env:
//   TYPESAFE_API_KEY  your TypeSafe key (required)
//   CONNECTOR_KEY     shared secret; requests must carry ?key=<CONNECTOR_KEY> (required)
//   JEV_MODEL         optional, defaults to jev-latest

export const config = { maxDuration: 60 };

const API = "https://api.typesafe.ai/v1/systemone";
const MODEL = process.env.JEV_MODEL || "jev-latest";
const MAX_JOBS = 60;
const PARALLEL = 12;

// Weights and bands from ai-job-search's 04-job-evaluation.md
const WEIGHTS = { technical: 0.30, experience: 0.25, workstyle: 0.15, career: 0.30 };

const QUESTIONS = {
  technical: {
    type: "score",
    instructions: "How well do the skills required by `job` match the skills `candidate` has actually demonstrated?",
    criteria: [
      "The job's core requirements are skills the candidate lacks",
      "Partial match: significant upskilling needed for the core requirements",
      "Most core requirements match, with one or two learnable gaps",
      "The core requirements are the candidate's primary, demonstrated skills"
    ]
  },
  experience: {
    type: "score",
    instructions: "How closely does the candidate's work history match the function and nature of the work in `job`? Judge the work itself, not literal job titles.",
    criteria: [
      "Unrelated work history",
      "Adjacent experience; the candidate would have to make the case",
      "Related experience with clearly transferable skills",
      "Direct experience in the same domain and type of role"
    ]
  },
  workstyle: {
    type: "score",
    instructions: "How well does the environment and day-to-day work described in `job` fit how `candidate` says they work best, including what energizes and drains them?",
    criteria: [
      "Significant mismatch with how the candidate works best",
      "Some friction with their preferences",
      "Mixed signals but mostly compatible",
      "Strong match with the environments and work they thrive in"
    ]
  },
  career: {
    type: "score",
    instructions: "Does `job` move `candidate` toward their stated career goals and contain work that energizes them?",
    criteria: [
      "A dead end or a step backwards for their goals",
      "A decent job that doesn't build toward their goals",
      "A good role that partly aligns with their goals",
      "Strongly aligned with their goals and the work that energizes them"
    ]
  },
  seniority: {
    type: "choice",
    instructions: "How does the seniority `job` asks for compare with the candidate's level of experience?",
    criteria: {
      far_below: "Much more junior than the candidate's experience",
      fit: "About right for the candidate's level",
      stretch: "One step above their level; a reasonable stretch",
      far_above: "Far above their level, for example years or leadership scope they clearly lack"
    }
  },
  clearance: {
    type: "noul",
    instructions: "Does `job` require a security clearance that `candidate` does not already hold?"
  },
  citizenship: {
    type: "noul",
    instructions: "Does `job` require citizenship, permanent residency, or no need for sponsorship in a way that conflicts with the candidate's stated work authorization?",
    criteria: { true: "The posting states a requirement the candidate does not meet", false: "No such requirement, the candidate meets it, or the posting is silent" }
  },
  language: {
    type: "noul",
    instructions: "Does `job` require, as a condition of doing the job, a language the candidate does not list among their languages?"
  },
  location: {
    type: "noul",
    instructions: "Would taking `job` force the candidate to relocate or commute beyond their stated limit, given the job's location and remote or hybrid arrangement and the candidate's location and work preference?",
    criteria: { true: "Clearly requires on-site presence outside their reach, or relocation", false: "Remote, within their commute, hybrid within reach, or the location is unclear" }
  },
  dealbreaker: {
    type: "noul",
    instructions: "Does `job` clearly violate one of the deal-breakers listed in `candidate`?"
  }
};
const GATES = ["clearance", "citizenship", "language", "location", "dealbreaker"];

const TOOL = {
  name: "score_jobs",
  title: "Score jobs against a profile",
  description: "Scores up to 60 job postings against one candidate profile with TypeSafe Jev. Returns, per job: a 0-100 fit (weighted technical 30%, experience 25%, work style 15%, career 30%), each dimension 0-100, the probability of each hard gate (clearance, citizenship, language, location, dealbreaker), a seniority judgment, and a flag naming the first gate that likely fails.",
  inputSchema: {
    type: "object",
    properties: {
      profile: { type: "string", description: "The candidate's profile and resume as plain text" },
      jobs: {
        type: "array",
        maxItems: MAX_JOBS,
        items: {
          type: "object",
          properties: {
            id: { type: "string" }, title: { type: "string" }, company: { type: "string" },
            location: { type: "string" }, pay: { type: "string" }, type: { type: "string" },
            description: { type: "string", description: "Full posting text if available, else a summary" }
          },
          required: ["id", "title"]
        }
      }
    },
    required: ["profile", "jobs"]
  },
  annotations: { readOnlyHint: true, openWorldHint: true }
};

const clip = (s, n) => String(s || "").slice(0, n);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function askJev(state) {
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Authorization": `Bearer ${process.env.TYPESAFE_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: MODEL, state, questions: QUESTIONS })
    });
    if (res.status === 429 && attempt < 3) {
      const wait = Number(res.headers.get("retry-after")) * 1000 || 800 * (attempt + 1);
      await sleep(wait + Math.random() * 300);
      continue;
    }
    if (!res.ok) throw new Error(`TypeSafe ${res.status}: ${clip(await res.text(), 200)}`);
    return res.json();
  }
}

const pct = (answer, levels) => Math.round((Number(answer && answer.score) || 0) / (levels - 1) * 100);

function summarize(job, out) {
  const a = out.answers || {};
  const dims = {
    technical: pct(a.technical, 4), experience: pct(a.experience, 4),
    workstyle: pct(a.workstyle, 4), career: pct(a.career, 4)
  };
  const fit = Math.round(Object.entries(WEIGHTS).reduce((s, [k, w]) => s + w * dims[k], 0));
  const gates = Object.fromEntries(GATES.map(g => [g, Math.round((Number(a[g] && a[g].noul) || 0) * 100) / 100]));
  const sen = a.seniority || {};
  const senP = sen.probabilities || {};
  let flag = GATES.find(g => gates[g] >= (g === "location" ? 0.7 : 0.6)) || "";
  if (!flag && ((senP.far_above || 0) >= 0.6 || (senP.far_below || 0) >= 0.6)) flag = "seniority";
  if (flag === "citizenship" || flag === "clearance") flag = "eligibility";
  const conf = ["technical", "experience", "workstyle", "career"].map(k => Number(a[k] && a[k].confidence) || 0);
  return {
    id: job.id, fit, dims, gates, flag,
    seniority: sen.choice || "", seniorityProbs: senP,
    confidence: Math.round(conf.reduce((x, y) => x + y, 0) / conf.length * 100) / 100
  };
}

async function scoreJobs({ profile, jobs }) {
  if (!process.env.TYPESAFE_API_KEY) throw new Error("TYPESAFE_API_KEY is not set on the server");
  if (!Array.isArray(jobs) || !jobs.length) return { model: MODEL, results: [] };
  const list = jobs.slice(0, MAX_JOBS);
  const candidate = clip(profile, 14000);
  const results = new Array(list.length);
  let next = 0, model = MODEL, tokens = 0;
  const worker = async () => {
    while (next < list.length) {
      const i = next++, j = list[i];
      const job = {
        title: clip(j.title, 200), company: clip(j.company, 200), location: clip(j.location, 200),
        pay: clip(j.pay, 120), type: clip(j.type, 120), description: clip(j.description, 6000)
      };
      try {
        const out = await askJev({ candidate, job });
        model = out.model || model; tokens += (out.usage && out.usage.input_tokens) || 0;
        results[i] = summarize({ id: String(j.id) }, out);
      } catch (e) {
        results[i] = { id: String(j.id), error: clip(e.message, 200) };
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(PARALLEL, list.length) }, worker));
  return { model, results, usage: { input_tokens: tokens } };
}

/* ---------- MCP over HTTP (stateless, JSON responses) ---------- */
async function handleRpc(msg) {
  const { id, method, params } = msg || {};
  const isNote = id === undefined || id === null;
  const reply = result => (isNote ? null : { jsonrpc: "2.0", id, result });
  const fail = (code, message) => (isNote ? null : { jsonrpc: "2.0", id, error: { code, message } });
  switch (method) {
    case "initialize":
      return reply({
        protocolVersion: (params && params.protocolVersion) || "2025-06-18",
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "jev-job-ranker", version: "1.0.0" },
        instructions: "Scores job postings against a candidate profile with TypeSafe Jev."
      });
    case "ping": return reply({});
    case "tools/list": return reply({ tools: [TOOL] });
    case "tools/call": {
      if (!params || params.name !== TOOL.name) return fail(-32602, `Unknown tool: ${params && params.name}`);
      try {
        const data = await scoreJobs(params.arguments || {});
        return reply({ content: [{ type: "text", text: JSON.stringify(data) }], structuredContent: data });
      } catch (e) {
        return reply({ content: [{ type: "text", text: `Error: ${e.message}` }], isError: true });
      }
    }
    default:
      if (method && method.startsWith("notifications/")) return null;
      return fail(-32601, `Method not found: ${method}`);
  }
}

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
