/*
 * reverb_probe.js — read-only diagnostics for a product's price/stock and any
 * Reverb integration tables. Helps explain why a Reverb listing's price didn't
 * update from the OpenCart DB.
 * USAGE: node reverb_probe.js --sku LECLIPSE87BLKLH
 */
const mysql = require('mysql2/promise');
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };
const SKU = (opt('--sku', 'LECLIPSE87BLKLH') || '').trim();
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
    // 1) the product itself
    const [p] = await c.query(
      `SELECT p.product_id, p.sku, p.model, p.price, p.quantity, p.status, p.date_modified,
              m.name AS brand
         FROM oc_product p LEFT JOIN oc_manufacturer m ON m.manufacturer_id=p.manufacturer_id
        WHERE p.sku = ? OR p.model = ? LIMIT 5`, [SKU, SKU]);
    console.log('=== oc_product match for', SKU, '===');
    if (!p.length) console.log('  (no product found by sku or model!)');
    for (const r of p) console.log(`  id=${r.product_id} sku=${r.sku} model=${r.model} price=${r.price} qty=${r.quantity} status=${r.status==1?'ENABLED':'disabled'} brand=${r.brand} modified=${r.date_modified instanceof Date ? r.date_modified.toISOString() : r.date_modified}`);

    const pid = p.length ? p[0].product_id : null;

    // 2) find Reverb-related tables
    const [tbls] = await c.query("SHOW TABLES LIKE '%reverb%'");
    const tables = tbls.map(row => Object.values(row)[0]);
    console.log('\n=== tables matching %reverb% ===');
    console.log(tables.length ? '  ' + tables.join('\n  ') : '  (none — Reverb sync may not store a mapping table, or uses a different name)');

    // 3) for each reverb table, show columns + any row referencing this product
    for (const t of tables) {
      const [cols] = await c.query(`SHOW COLUMNS FROM \`${t}\``);
      const colNames = cols.map(x => x.Field);
      console.log(`\n--- ${t} columns: ${colNames.join(', ')}`);
      const pidCol = colNames.find(x => /product_id/i.test(x));
      const skuCol = colNames.find(x => /sku|model/i.test(x));
      if (pid && pidCol) {
        const [rows] = await c.query(`SELECT * FROM \`${t}\` WHERE \`${pidCol}\` = ? LIMIT 5`, [pid]);
        console.log(`    rows for product_id=${pid}: ${rows.length}`);
        rows.forEach(r => console.log('      ' + JSON.stringify(r)));
      }
      if (skuCol) {
        const [rows] = await c.query(`SELECT * FROM \`${t}\` WHERE \`${skuCol}\` = ? LIMIT 5`, [SKU]);
        if (rows.length) rows.forEach(r => console.log(`      [by ${skuCol}] ` + JSON.stringify(r)));
      }
    }
  } finally { await c.end(); }
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
