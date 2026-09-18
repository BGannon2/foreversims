// Cloudflare Worker in front of the static site.
//  * The workers.dev preview address requires HTTP Basic auth (SITE_USER / SITE_PASSWORD secrets);
//    the production domain is served without a prompt.
//  * POST /api/feedback stores visitor feedback in D1 (binding DB) and optionally forwards it to a
//    Discord webhook (FEEDBACK_WEBHOOK secret).  GET /feedback-admin lists entries behind the same
//    Basic auth credentials on every host.
const PROTECTED_HOSTS = [".workers.dev"];
const CATEGORIES = new Set(["bug", "idea", "data", "other"]);
const MAX_MESSAGE = 4000;
const RATE_WINDOW_MINUTES = 10;
const RATE_LIMIT = 5;

function unauthorized(realm) {
  return new Response(`Forever Sims ${realm}: sign in required.`, {
    status: 401,
    headers: { "WWW-Authenticate": `Basic realm="Forever Sims ${realm}", charset="UTF-8"`, "Cache-Control": "no-store" },
  });
}

function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  if (x.byteLength !== y.byteLength) return false;
  return crypto.subtle.timingSafeEqual(x, y);
}

function authorized(request, env) {
  if (!env.SITE_PASSWORD) return false;
  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Basic ")) return false;
  let user = "", pass = "";
  try {
    const decoded = atob(header.slice(6));
    const i = decoded.indexOf(":");
    user = decoded.slice(0, i); pass = decoded.slice(i + 1);
  } catch { return false; }
  return timingSafeEqual(user, env.SITE_USER || "forever") && timingSafeEqual(pass, env.SITE_PASSWORD);
}

function json(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function clean(value, max) {
  // eslint-disable-next-line no-control-regex -- intentional: strips control characters from user input
  return String(value ?? "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").trim().slice(0, max);
}

async function submitFeedback(request, env) {
  if (!env.DB) return json({ error: "Feedback storage is not configured." }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: "Send JSON." }, 400); }
  if (body.website) return json({ ok: true }); // honeypot field filled by bots
  const message = clean(body.message, MAX_MESSAGE);
  if (message.length < 5) return json({ error: "Please write a few words of feedback." }, 400);
  const category = CATEGORIES.has(body.category) ? body.category : "other";
  const contact = clean(body.contact, 200);
  const page = clean(body.page, 300);
  const spec = clean(body.spec, 80);
  const version = clean(body.version, 120);
  const userAgent = clean(request.headers.get("User-Agent"), 300);
  const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";
  const ipHash = (await sha256(`${ip}|${new Date().toISOString().slice(0, 10)}`)).slice(0, 32);
  const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM feedback WHERE ip_hash = ?1 AND created_at > strftime('%Y-%m-%dT%H:%M:%fZ','now', ?2)")
    .bind(ipHash, `-${RATE_WINDOW_MINUTES} minutes`).first("n");
  if (recent >= RATE_LIMIT) return json({ error: "Too many submissions; please try again in a few minutes." }, 429);
  const result = await env.DB.prepare("INSERT INTO feedback (category, message, contact, page, spec, version, user_agent, ip_hash) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)")
    .bind(category, message, contact || null, page || null, spec || null, version || null, userAgent || null, ipHash).run();
  const id = result.meta?.last_row_id;
  let issueUrl = null;
  if (env.GITHUB_TOKEN && env.GITHUB_REPO) {
    issueUrl = await createIssue(env, { id, category, message, contact, page, spec, version, userAgent });
    if (issueUrl) await env.DB.prepare("UPDATE feedback SET issue_url = ?1 WHERE id = ?2").bind(issueUrl, id).run();
  }
  if (env.FEEDBACK_WEBHOOK) {
    const text = `**Feedback #${id} · ${category}**${spec ? ` · ${spec}` : ""}\n${message.slice(0, 1500)}${contact ? `\n_contact: ${contact}_` : ""}${page ? `\n<${page}>` : ""}`;
    await fetch(env.FEEDBACK_WEBHOOK, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: text, allowed_mentions: { parse: [] } }) }).catch(() => {});
  }
  return json({ ok: true, id });
}

const CATEGORY_LABELS = { bug: "bug", data: "data", idea: "idea", other: "question" };

async function createIssue(env, f) {
  const lines = f.message.split(/\r?\n/);
  const firstLine = lines[0].trim();
  const title = `[${f.category}] ${firstLine.length > 72 ? firstLine.slice(0, 69) + "..." : firstLine}`;
  const quoted = lines.map(l => `> ${l}`).join("\n");
  const meta = [["Feedback id", f.id], ["Spec", f.spec || "-"], ["Page", f.page || "-"], ["Version", f.version || "-"], ["Contact", f.contact || "-"], ["Browser", f.userAgent || "-"]]
    .map(([k, v]) => `| ${k} | ${String(v).replace(/\|/g, "\\|")} |`).join("\n");
  const body = `${quoted}\n\n| | |\n|---|---|\n${meta}\n\n_Submitted through the site feedback form._`;
  try {
    const res = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${env.GITHUB_TOKEN}`, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "foreversims-feedback", "Content-Type": "application/json" },
      body: JSON.stringify({ title, body, labels: ["feedback", CATEGORY_LABELS[f.category] || "question"] }),
    });
    if (!res.ok) { console.log("GitHub issue failed", res.status, await res.text()); return null; }
    return (await res.json()).html_url || null;
  } catch (err) { console.log("GitHub issue error", String(err)); return null; }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function feedbackAdmin(request, env, url) {
  if (!authorized(request, env)) return unauthorized("feedback");
  if (!env.DB) return new Response("Feedback storage is not configured.", { status: 503 });
  if (request.method === "POST") {
    const form = await request.formData();
    const id = Number(form.get("id")), status = String(form.get("status") || "new");
    if (id && ["new", "seen", "done"].includes(status)) await env.DB.prepare("UPDATE feedback SET status = ?1 WHERE id = ?2").bind(status, id).run();
    return Response.redirect(url.origin + url.pathname, 303);
  }
  const { results } = await env.DB.prepare("SELECT id, created_at, category, message, contact, page, spec, version, status, issue_url FROM feedback ORDER BY id DESC LIMIT 500").all();
  if (url.searchParams.get("format") === "json") return json(results);
  const rows = results.map(r => `<tr class="${r.status}"><td>${r.id}</td><td>${escapeHtml(r.created_at.slice(0, 16).replace("T", " "))}</td><td>${escapeHtml(r.category)}</td><td class="msg">${escapeHtml(r.message)}</td><td>${escapeHtml(r.contact || "")}</td><td>${r.page ? `<a href="${escapeHtml(r.page)}">${escapeHtml(r.spec || "page")}</a>` : escapeHtml(r.spec || "")}</td><td>${escapeHtml(r.version || "")}</td><td>${r.issue_url ? `<a href="${escapeHtml(r.issue_url)}">#${r.issue_url.split("/").pop()}</a>` : ""}</td><td><form method="post"><input type="hidden" name="id" value="${r.id}"><select name="status">${["new", "seen", "done"].map(s => `<option value="${s}"${s === r.status ? " selected" : ""}>${s}</option>`).join("")}</select><button>save</button></form></td></tr>`).join("");
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Forever Sims feedback</title><style>
body{font:14px/1.45 system-ui,sans-serif;background:#0d0a1f;color:#e8e6f0;margin:0;padding:24px}h1{font-size:20px;margin:0 0 14px}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #2a2547;padding:8px 10px;vertical-align:top;text-align:left}th{color:#3fc6e8;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
td.msg{white-space:pre-wrap;max-width:560px}tr.done{opacity:.45}tr.seen td.msg{color:#bdb8d6}a{color:#e3bd62}form{display:flex;gap:4px}select,button{background:#1a1533;color:#fff;border:1px solid #3a3466;padding:3px 6px}small{color:#8f89b0}</style></head>
<body><h1>Forever Sims feedback <small>${results.length} entries · <a href="?format=json">json</a></small></h1><table><thead><tr><th>#</th><th>When (UTC)</th><th>Type</th><th>Message</th><th>Contact</th><th>Page</th><th>Version</th><th>Issue</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="9">No feedback yet.</td></tr>'}</tbody></table></body></html>`;
  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex" } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/feedback" && request.method === "POST") return submitFeedback(request, env);
    if (url.pathname === "/feedback-admin") return feedbackAdmin(request, env, url);
    const protect = PROTECTED_HOSTS.some(s => url.hostname.endsWith(s)) && env.SITE_PASSWORD;
    if (protect && !authorized(request, env)) return unauthorized("preview");
    return env.ASSETS.fetch(request);
  },
};
