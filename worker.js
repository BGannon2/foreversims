// Cloudflare Worker in front of the static site.
// The workers.dev preview address requires HTTP Basic auth (SITE_USER / SITE_PASSWORD secrets);
// the production domain is served without a prompt.
const PROTECTED_HOSTS = [".workers.dev"];

function unauthorized() {
  return new Response("Forever Sims preview: sign in required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Forever Sims preview", charset="UTF-8"', "Cache-Control": "no-store" },
  });
}

function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  if (x.byteLength !== y.byteLength) return false;
  return crypto.subtle.timingSafeEqual(x, y);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const protect = PROTECTED_HOSTS.some(s => url.hostname.endsWith(s)) && env.SITE_PASSWORD;
    if (protect) {
      const header = request.headers.get("Authorization") || "";
      if (!header.startsWith("Basic ")) return unauthorized();
      let user = "", pass = "";
      try {
        const decoded = atob(header.slice(6));
        const i = decoded.indexOf(":");
        user = decoded.slice(0, i); pass = decoded.slice(i + 1);
      } catch { return unauthorized(); }
      const okUser = timingSafeEqual(user, env.SITE_USER || "forever");
      const okPass = timingSafeEqual(pass, env.SITE_PASSWORD);
      if (!(okUser && okPass)) return unauthorized();
    }
    return env.ASSETS.fetch(request);
  },
};
