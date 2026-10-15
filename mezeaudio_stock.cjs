// Sound Service stock fallback (2026-10-15): the SS pricing API sends an empty <stock/> for every product, but the
// public frontend API of their UK/EU shop (mezeaudio.co.uk) still shows live stock per SS Item ID ("code").
// Crawls /api/brands/<slug>?page=N (20 per page) -> cache/mezeaudio_stock.json {ts, items:{code:{stock,eta}}}.
// sound_service.js uses it for items whose API stock is empty (cache must be < 36 h old).
const fs = require('fs'), path = require('path');
const UA = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', Accept: 'application/json' };
const OUT = path.join(__dirname, 'cache', 'mezeaudio_stock.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function get(url) {
  for (let a = 0; a < 4; a++) {
    try { const r = await fetch(url, { headers: UA }); if (r.ok) return await r.json(); if (r.status === 404) return null; } catch (e) {}
    await sleep(2000 * (a + 1));
  }
  throw new Error('failed ' + url);
}
(async () => {
  const t0 = Date.now();
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
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ ts: new Date().toISOString(), items }));
  console.log(`mezeaudio: ${brands.length} brands, ${pages} pages (${failed} failed), ${n} items, ${pos} in stock, ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch((e) => { console.error('mezeaudio stock FAILED:', e.message); process.exit(1); });
