// Sound Service stock fallback (2026-10-15): the SS pricing API sends an empty <stock/> for every product.
// mezeaudio.co.uk IS Sound Service's own backend (the sound-service.eu dealer portal calls it). Since 2026-10-16 stock and
// prices are only returned to logged-in dealers -> POST /api/login with SS_PORTAL_EMAIL / SS_PORTAL_PASSWORD from
// /srv/docker/imports/.ss_portal (written by the user, chmod 600, git-ignored) -> Bearer token.
// Crawls /api/brands/<slug>?page=N (20 per page) -> cache/mezeaudio_stock.json {ts, items:{code:{stock,eta}}}.
// sound_service.js uses it for items whose API stock is empty (cache must be < 36 h old).
const fs = require('fs'), path = require('path');
const UA = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', Accept: 'application/json' };
const OUT = path.join(__dirname, 'cache', 'mezeaudio_stock.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function portalCreds() {
  const out = {};
  try {
    for (const raw of fs.readFileSync(path.join(__dirname, '.ss_portal'), 'utf8').split('\n')) {
      const l = raw.trim(); const i = l.indexOf('='); if (i > 0) out[l.slice(0, i).trim()] = l.slice(i + 1).trim();
    }
  } catch (e) {}
  return out;
}
async function login() {
  const c = portalCreds(); if (!c.SS_PORTAL_EMAIL || !c.SS_PORTAL_PASSWORD) throw new Error('missing .ss_portal (SS_PORTAL_EMAIL / SS_PORTAL_PASSWORD)');
  const r = await fetch('https://mezeaudio.co.uk/api/login', { method: 'POST', headers: { ...UA, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: c.SS_PORTAL_EMAIL, password: c.SS_PORTAL_PASSWORD }) });
  const j = await r.json().catch(() => ({})); const tok = j.token || j.access_token || (j.data && (j.data.token || j.data.access_token));
  if (!tok) throw new Error('portal login failed: HTTP ' + r.status + ' ' + (j.message || ''));
  UA.Authorization = 'Bearer ' + tok;
}
async function get(url) {
  for (let a = 0; a < 4; a++) {
    try { const r = await fetch(url, { headers: UA }); if (r.ok) return await r.json(); if (r.status === 404) return null; } catch (e) {}
    await sleep(2000 * (a + 1));
  }
  throw new Error('failed ' + url);
}
(async () => {
  const t0 = Date.now();
  await login();
  const brands = await get('https://mezeaudio.co.uk/api/brands');
  const items = {}; let pages = 0, failed = 0;
  for (const b of brands) {
    let page = 1, last = 1;
    do {
      let j = null; try { j = await get(`https://mezeaudio.co.uk/api/brands/${b.slug}?page=${page}`); } catch (e) { failed++; console.log('skip', b.slug, page); page++; continue; }
      pages++;
      if (!j || !j.products) break;
      last = j.products.last_page || 1;
      for (const p of j.products.data || []) if (p.code) items[String(p.code)] = { stock: Number(p.stock) || 0, eta: p.eta ? String(p.eta).slice(0, 10) : '' };
      page++; await sleep(150);
    } while (page <= last);
  }
  const n = Object.keys(items).length, pos = Object.values(items).filter((x) => x.stock > 0).length;
  if (n < 1000) throw new Error(`only ${n} items — not overwriting cache`);
  if (pos < 300) throw new Error(`only ${pos} in stock — stock looks hidden/broken, not overwriting cache`);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ ts: new Date().toISOString(), items }));
  console.log(`mezeaudio: ${brands.length} brands, ${pages} pages (${failed} failed), ${n} items, ${pos} in stock, ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch((e) => { console.error('mezeaudio stock FAILED:', e.message); process.exit(1); });
