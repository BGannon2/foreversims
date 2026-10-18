// Tell IndexNow search engines (Bing, and through it DuckDuckGo/Yahoo; Yandex, Seznam) that the
// sitemap's pages changed. The key file web/1a8bf35c53d1fb87f971d4c63d0c414e.txt proves we own the host.
// Run standalone: node tools/indexnow.js
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
const HOST = 'foreversims.com';
const KEY = '1a8bf35c53d1fb87f971d4c63d0c414e';
function sitemapUrls() {
  const xml = fs.readFileSync(path.join(ROOT, 'web', 'sitemap.xml'), 'utf8');
  return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1].trim());
}
async function submit(urls = sitemapUrls(), post = fetch) {
  const response = await post('https://api.indexnow.org/indexnow', {
    method: 'POST', headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ host: HOST, key: KEY, keyLocation: `https://${HOST}/${KEY}.txt`, urlList: urls }),
  });
  if (!response.ok && response.status !== 202) throw new Error(`IndexNow returned ${response.status}`);
  return { status: response.status, count: urls.length };
}
if (require.main === module) submit().then(r => console.log(`IndexNow: submitted ${r.count} URLs (${r.status})`)).catch(e => { console.error(e.message); process.exitCode = 1; });
module.exports = { submit, sitemapUrls, KEY };
