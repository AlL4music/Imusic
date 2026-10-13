// Best Acoustics (Reinhardt GmbH) B2B stock -> stock/bestacoustics_sklad.csv (Oct 2026).
// Logs in with BA_USER/BA_PASS from /srv/docker/bestacoustics/.env, posts the product filter with ALL brands ticked
// (one page = whole catalogue), reads the traffic light per article: gruen=3, gelb=1, rot=0.
// Feed feeds/bestacoustics.json matches by sku (= "BA-<order code>", set by ba_create.cjs). Also refreshes b2b_products.json.
const fs = require('fs');
const env = Object.fromEntries(fs.readFileSync('/srv/docker/bestacoustics/.env', 'utf8').split(/\r?\n/).filter((l) => l.includes('=')).map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()]));
const BASE = 'https://www.bestacoustics.eu';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';
const QTY = { gruen: 3, gelb: 1, rot: 0 };
const jar = new Map();
const cookieHeader = () => [...jar].map(([k, v]) => k + '=' + v).join('; ');
async function req(url, opt = {}) {
  let u = url.startsWith('http') ? url : BASE + url, r;
  for (let hop = 0; hop < 6; hop++) {
    r = await fetch(u, { ...opt, redirect: 'manual', headers: { 'User-Agent': UA, Cookie: cookieHeader(), ...(opt.headers || {}) } });
    for (const sc of r.headers.getSetCookie ? r.headers.getSetCookie() : []) { const [kv] = sc.split(';'); const i = kv.indexOf('='); jar.set(kv.slice(0, i).trim(), kv.slice(i + 1).trim()); }
    if (r.status >= 300 && r.status < 400 && r.headers.get('location')) { u = new URL(r.headers.get('location'), u).href; opt = { method: 'GET' }; continue; }
    break;
  }
  return { status: r.status, text: await r.text() };
}
const decode = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#039;/g, "'");
function formOf(html, actionPart) {
  const m = [...html.matchAll(/<form[^>]*action="([^"]*)"[^>]*>([\s\S]*?)<\/form>/g)].find((f) => decode(f[1]).includes(actionPart));
  if (!m) return null;
  const fields = [];
  for (const i of m[2].matchAll(/<input([^>]*)>/g)) {
    const a = i[1]; const name = (a.match(/name="([^"]*)"/) || [])[1]; if (!name) continue;
    const type = ((a.match(/type="([^"]*)"/) || [])[1] || 'text').toLowerCase(); const value = decode((a.match(/value="([^"]*)"/) || [, ''])[1]);
    fields.push({ name: decode(name), type, value });
  }
  for (const sel of m[2].matchAll(/<select[^>]*name="([^"]*)"[^>]*>([\s\S]*?)<\/select>/g)) {
    const opt = sel[2].match(/<option[^>]*selected[^>]*value="([^"]*)"/) || sel[2].match(/<option[^>]*value="([^"]*)"/);
    fields.push({ name: decode(sel[1]), type: 'select', value: opt ? decode(opt[1]) : '' });
  }
  return { action: decode(m[1]), fields };
}
(async () => {
  if (!env.BA_USER || !env.BA_PASS) throw new Error('BA_USER/BA_PASS missing in /srv/docker/bestacoustics/.env');
  const lp = await req('/en/login');
  const lf = formOf(lp.text, 'tx_felogin_login'); if (!lf) throw new Error('login form not found');
  const body = new URLSearchParams();
  for (const f of lf.fields) if (f.type === 'hidden') body.append(f.name, f.value);
  body.set('user', env.BA_USER); body.set('pass', env.BA_PASS); body.set('submit', 'Login'); body.set('logintype', 'login');
  await req(lf.action, { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  const pp = await req('/en/b2b/products');
  const ff = formOf(pp.text, 'produktfilter'); if (!ff) throw new Error('not logged in (product filter missing) — check BA_USER/BA_PASS');
  const fb = new URLSearchParams();
  for (const f of ff.fields) {
    if (f.type === 'checkbox') { if (/\[Brand\d+\]/.test(f.name)) fb.append(f.name, f.value || '1'); }
    else if (!['submit', 'button', 'image'].includes(f.type)) fb.append(f.name, f.value);   // hidden, text, select — like the browser
  }
  const res = await req(ff.action, { method: 'POST', body: fb, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  const sections = res.text.split('<section class="produkt"').slice(1);
  const rows = [], prods = [];
  for (const s of sections) {
    const a = (s.match(/class="prodArtNr">\s*Art\.No\.\s*([^<\s]+)/) || [])[1]; if (!a) continue;
    const st = (s.match(/class="bestand (\w+)"/) || [])[1] || 'rot';
    const n1 = decode(((s.match(/class="prodBezeichnung1">([^<]*)/) || [])[1] || '').trim());
    const br = decode(((s.match(/class="prodBrand">([^<]*)/) || [])[1] || '').trim());
    rows.push([`BA-${a}`, QTY[st] ?? 0, `${br} ${n1}`.replace(/;/g, ',').trim()]);
    prods.push({ a, br, n1, st });
  }
  if (rows.length < 300) throw new Error(`only ${rows.length} products parsed — refusing to write a partial feed`);
  const out = '﻿SKU;Pocet_ks;Nazov\n' + rows.map((r) => r.join(';')).join('\n') + '\n';
  fs.writeFileSync('/srv/docker/imports/stock/bestacoustics_sklad.csv', out);
  fs.writeFileSync('/srv/docker/bestacoustics/stock_latest.json', JSON.stringify({ ts: new Date().toISOString(), prods }));
  const c = rows.reduce((o, r) => ((o[r[1]] = (o[r[1]] || 0) + 1), o), {});
  console.log(`Best Acoustics: ${rows.length} articles -> qty3 ${c[3] || 0}, qty1 ${c[1] || 0}, qty0 ${c[0] || 0}`);
})().catch((e) => { console.error('Best Acoustics stock FAILED:', e.message); process.exit(1); });
