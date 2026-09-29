// @purpose: Public Refresh endpoint for the VOA CSV export site (0xsector.github.io).
// POST starts the repo's refresh GitHub Action (workflow_dispatch, trigger=button) at most once
// per COOLDOWN_MIN; GET reports the latest run and the head commit so the page can show progress
// and tell "new pull archived" apart from "nothing new on VOA". GH_TOKEN is a fine-grained PAT
// scoped to this one repo with Actions read/write only, so the most a caller can do is start one
// refresh an hour, and the Action itself refuses to publish a pull that fails its checks.
const REPO = process.env.GH_REPO || '0xSector/visaonchainanalytics-csv-export';
const WORKFLOW = 'refresh.yml';
const COOLDOWN_MIN = Number(process.env.COOLDOWN_MIN || 60);
const ALLOWED = (process.env.ALLOWED_ORIGINS || 'https://0xsector.github.io').split(',');

function gh(path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${process.env.GH_TOKEN}`,
      accept: 'application/vnd.github+json',
      'x-github-api-version': '2022-11-28',
      'user-agent': 'voa-refresh-api',
      ...(init.headers || {}),
    },
  });
}

function cors(req) {
  const origin = req.headers.get('origin');
  if (!ALLOWED.includes(origin)) return {};
  return {
    'access-control-allow-origin': origin,
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    vary: 'origin',
  };
}

const reply = (req, body, status = 200, extra = {}) =>
  Response.json(body, { status, headers: { ...cors(req), ...extra } });

async function state() {
  const [runs, commits] = await Promise.all([
    gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1`),
    gh('/commits?per_page=1'),
  ]);
  if (!runs.ok) throw new Error(`workflow runs: HTTP ${runs.status}`);
  const run = (await runs.json()).workflow_runs?.[0] || null;
  const head = commits.ok ? (await commits.json())[0] : null;
  return {
    last_run: run && {
      status: run.status,
      conclusion: run.conclusion,
      event: run.event,
      created_at: run.created_at,
      updated_at: run.updated_at,
      url: run.html_url,
    },
    head_commit: head && {
      message: head.commit.message.split('\n')[0],
      date: head.commit.committer.date,
    },
    cooldown_min: COOLDOWN_MIN,
    next_allowed_at: run
      ? new Date(Date.parse(run.created_at) + COOLDOWN_MIN * 60_000).toISOString()
      : null,
  };
}

export function OPTIONS(req) {
  return new Response(null, { status: 204, headers: cors(req) });
}

export async function GET(req) {
  try {
    return reply(req, await state(), 200, { 'cache-control': 'public, s-maxage=5' });
  } catch (e) {
    console.error(e);
    return reply(req, { error: 'status unavailable' }, 502);
  }
}

export async function POST(req) {
  if (!ALLOWED.includes(req.headers.get('origin'))) {
    return reply(req, { error: 'origin not allowed' }, 403);
  }
  let s;
  try {
    s = await state();
  } catch (e) {
    console.error(e);
    return reply(req, { error: 'status unavailable' }, 502);
  }
  const run = s.last_run;
  if (run && run.status !== 'completed') return reply(req, { started: false, reason: 'running', ...s }, 409);
  if (run && Date.now() < Date.parse(s.next_allowed_at)) {
    return reply(req, { started: false, reason: 'cooldown', ...s }, 429);
  }
  const r = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs: { trigger: 'button' } }),
  });
  if (r.status !== 204) {
    console.error('dispatch failed', r.status, await r.text());
    return reply(req, { error: `could not start refresh (HTTP ${r.status})` }, 502);
  }
  return reply(req, { started: true, ...s }, 202);
}
