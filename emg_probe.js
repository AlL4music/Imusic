/*
 * emg_probe.js — read-only: why do EMG pickups show "In Stock" (warehouse 1)
 * instead of "Skladom u dodávateľa" (warehouse 2 / Alexim)? Inspects the EMG
 * products, the multi-warehouse stock tables, and whether the Alexim codes
 * resolve to these products (old_shop_sku -> model chain).
 */
const mysql = require('mysql2/promise');
const clean = (v) => (v == null ? v : String(v).trim());
const db = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER), password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME), connectTimeout: 30000,
};
const ALEXIM_CODES = ['77321.01', '7710.01', '77092.01', '7709.01']; // 35HZ,35J,35P,35P4

(async () => {
  const c = await mysql.createConnection(db);
  const q = async (sql, p) => (await c.query(sql, p))[0];
  try {
    // 1) EMG products
    const emg = await q(
      `SELECT p.product_id, p.sku, p.model, p.quantity, p.stock_status_id, p.location,
              pd.name
         FROM oc_product p
         JOIN oc_product_description pd ON pd.product_id=p.product_id AND pd.language_id=1
         LEFT JOIN oc_manufacturer m ON m.manufacturer_id=p.manufacturer_id
        WHERE p.model LIKE 'EMG%' OR pd.name LIKE 'EMG %' OR m.name='EMG'
        ORDER BY pd.name LIMIT 12`);
    console.log(`=== EMG products (showing ${emg.length}) ===`);
    for (const r of emg) console.log(`  id=${r.product_id} sku=${r.sku} model=${r.model} qty=${r.quantity} stock_status_id=${r.stock_status_id} loc="${r.location||''}" | ${r.name}`);
    const ids = emg.map(r => r.product_id);

    // 2) stock status labels
    const ss = await q(`SELECT stock_status_id, name FROM oc_stock_status WHERE language_id=1`);
    console.log('\n=== stock statuses ===');
    ss.forEach(s => console.log(`  ${s.stock_status_id} = ${s.name}`));

    // 3) discover warehouse / stock / old-shop tables
    const tbls = (await q('SHOW TABLES')).map(r => Object.values(r)[0]);
    const cand = tbls.filter(t => /(warehouse|multistock|stock_location|product_quantity|oldshop|old_shop|migrat|_sku_map|location)/i.test(t));
    console.log('\n=== candidate warehouse/stock/old-shop tables ===\n  ' + (cand.join('\n  ') || '(none matched by name)'));

    for (const t of cand) {
      const cols = (await q(`SHOW COLUMNS FROM \`${t}\``)).map(x => x.Field);
      console.log(`\n--- ${t}: ${cols.join(', ')}`);
      const pidCol = cols.find(x => /^product_id$/i.test(x)) || cols.find(x => /product_id/i.test(x));
      if (pidCol && ids.length) {
        const rows = await q(`SELECT * FROM \`${t}\` WHERE \`${pidCol}\` IN (${ids.map(()=>'?').join(',')}) LIMIT 40`, ids);
        console.log(`    rows for EMG products: ${rows.length}`);
        rows.slice(0, 20).forEach(r => console.log('      ' + JSON.stringify(r)));
      }
      // old-shop-sku style table: try to resolve the Alexim codes
      const skuCol = cols.find(x => /sku|code|old/i.test(x));
      if (skuCol) {
        const rows = await q(`SELECT * FROM \`${t}\` WHERE \`${skuCol}\` IN (${ALEXIM_CODES.map(()=>'?').join(',')}) LIMIT 20`, ALEXIM_CODES);
        if (rows.length) { console.log(`    Alexim codes found in ${t}.${skuCol}: ${rows.length}`); rows.forEach(r => console.log('      ' + JSON.stringify(r))); }
      }
    }
  } finally { await c.end(); }
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
