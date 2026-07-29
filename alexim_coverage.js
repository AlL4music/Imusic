/*
 * alexim_coverage.js — read-only: would match_by "sku" cover the Alexim feed?
 * Reads alexim_sklad.csv (SKU;Nazov;Pocet_ks;URL) and checks how many of the
 * Alexim codes exist as oc_product.sku vs oc_product.model, so we can safely
 * decide whether to switch feeds/alexim.json from old_shop_sku -> sku.
 */
const mysql = require('mysql2/promise');
const fs = require('fs');
const clean = (v) => (v == null ? v : String(v).trim());
const db = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER), password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME), connectTimeout: 30000,
};

function readCodes(path) {
  const text = fs.readFileSync(path, 'utf8').replace(/^﻿/, '');
  const lines = text.split(/\r?\n/).filter(Boolean);
  const header = lines[0].split(';');
  const skuIdx = header.findIndex(h => h.trim().toLowerCase() === 'sku');
  const codes = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(';');
    const s = (cols[skuIdx] || '').trim();
    if (s) codes.push(s);
  }
  return codes;
}

async function countIn(c, column, codes) {
  let matched = 0; const unmatched = [];
  for (let i = 0; i < codes.length; i += 500) {
    const batch = codes.slice(i, i + 500);
    const [rows] = await c.query(
      `SELECT DISTINCT \`${column}\` AS v FROM oc_product WHERE \`${column}\` IN (${batch.map(()=>'?').join(',')})`, batch);
    const found = new Set(rows.map(r => String(r.v)));
    for (const b of batch) (found.has(b) ? matched++ : unmatched.push(b));
  }
  return { matched, unmatched };
}

(async () => {
  const codes = readCodes('alexim_sklad.csv');
  const uniq = [...new Set(codes)];
  console.log(`Alexim feed rows: ${codes.length}  (unique SKUs: ${uniq.length})`);

  const c = await mysql.createConnection(db);
  try {
    const bySku = await countIn(c, 'sku', uniq);
    const byModel = await countIn(c, 'model', uniq);
    const pct = (n) => (100 * n / uniq.length).toFixed(1);
    console.log(`\nmatch_by sku   : ${bySku.matched}/${uniq.length} (${pct(bySku.matched)}%) match oc_product.sku`);
    console.log(`match_by model : ${byModel.matched}/${uniq.length} (${pct(byModel.matched)}%) match oc_product.model`);
    console.log('\nExamples NOT matching by sku (first 15):');
    console.log('  ' + bySku.unmatched.slice(0, 15).join(', '));
  } finally { await c.end(); }
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
