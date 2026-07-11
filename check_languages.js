/*
 * check_languages.js — read-only: list store languages and a product's
 * per-language description rows, so we know which language_id holds Slovak.
 * USAGE: node check_languages.js --sku RGR8820QM-BRE
 */
const mysql = require('mysql2/promise');
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };
const SKU = (opt('--sku', 'RGR8820QM-BRE') || '').trim();
const clean = (v) => (v == null ? v : String(v).trim());
const db = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER), password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME), connectTimeout: 30000,
};
(async () => {
  const c = await mysql.createConnection(db);
  try {
    const [langs] = await c.query('SELECT language_id, name, code, status FROM oc_language ORDER BY language_id');
    console.log('=== Store languages ===');
    for (const l of langs) console.log(`  id=${l.language_id}  ${l.code}  ${l.name}  ${l.status ? '(enabled)' : '(disabled)'}`);
    const [rows] = await c.query('SELECT product_id FROM oc_product WHERE sku = ? LIMIT 1', [SKU]);
    if (!rows.length) { console.log(`\nNo product ${SKU}`); return; }
    const pid = rows[0].product_id;
    const [descs] = await c.query(
      'SELECT language_id, name, CHAR_LENGTH(description) AS dlen, meta_title FROM oc_product_description WHERE product_id = ?', [pid]);
    console.log(`\n=== product_id ${pid} (${SKU}) description rows ===`);
    for (const d of descs) console.log(`  language_id=${d.language_id}  name="${d.name}"  desc_len=${d.dlen}`);
  } finally { await c.end(); }
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
