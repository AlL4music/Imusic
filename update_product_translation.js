/*
 * update_product_translation.js — write a product's translation into one language slot
 * ===================================================================================
 * Sets name / description / meta_title / meta_description / meta_keyword / tag on
 * oc_product_description for a given language_id (e.g. 2 = Slovak). The description
 * HTML is read from a file (--desc-file); the rest come from env vars so punctuation
 * stays clean: TR_NAME, TR_META_TITLE, TR_META_DESC, TR_META_KEYWORD, TR_TAG.
 *
 * SAFE: dry run by default (needs --commit). Only the one product + language row is
 * touched. If the row is missing it's inserted.
 *
 * USAGE: node update_product_translation.js --sku RGR8820QM-BRE --language-id 2 \
 *          --desc-file translations/rgr8820qm-bre.sk.html [--commit]
 */
const mysql = require('mysql2/promise');
const fs = require('fs');
const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };

const COMMIT = flag('--commit') || process.env.COMMIT === '1';
const SKU = (opt('--sku', '') || '').trim();
const LANGUAGE_ID = parseInt(opt('--language-id', '2'), 10);
const DESC_FILE = opt('--desc-file', '');

const NAME = process.env.TR_NAME || '';
const META_TITLE = process.env.TR_META_TITLE || '';
const META_DESC = process.env.TR_META_DESC || '';
const META_KEYWORD = process.env.TR_META_KEYWORD || '';
const TAG = process.env.TR_TAG || '';

const clean = (v) => (v == null ? v : String(v).trim());
const dbConfig = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER), password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME), connectTimeout: 30000,
};

async function main() {
  if (!SKU || !NAME || !DESC_FILE) { console.error('Need --sku, TR_NAME and --desc-file.'); process.exit(1); }
  const description = fs.readFileSync(DESC_FILE, 'utf8');

  const db = await mysql.createConnection(dbConfig);
  try {
    const [rows] = await db.query('SELECT product_id FROM oc_product WHERE sku = ? LIMIT 1', [SKU]);
    if (!rows.length) { console.error(`No product ${SKU}`); process.exit(2); }
    const productId = rows[0].product_id;

    console.log(`Mode: ${COMMIT ? 'COMMIT' : 'DRY RUN'}   product_id=${productId}   language_id=${LANGUAGE_ID}`);
    console.log(`name             : ${NAME}`);
    console.log(`meta_title  (${META_TITLE.length}): ${META_TITLE}`);
    console.log(`meta_desc   (${META_DESC.length}): ${META_DESC}`);
    console.log(`meta_keyword     : ${META_KEYWORD}`);
    console.log(`tag              : ${TAG}`);
    console.log(`description       : ${description.length} chars from ${DESC_FILE}`);

    if (!COMMIT) { console.log('\nDRY RUN — nothing written. Re-run with --commit.'); return; }

    const [exists] = await db.query(
      'SELECT product_id FROM oc_product_description WHERE product_id = ? AND language_id = ? LIMIT 1',
      [productId, LANGUAGE_ID]);
    if (exists.length) {
      await db.query(
        `UPDATE oc_product_description
            SET name = ?, description = ?, meta_title = ?, meta_description = ?, meta_keyword = ?, tag = ?
          WHERE product_id = ? AND language_id = ?`,
        [NAME, description, META_TITLE, META_DESC, META_KEYWORD, TAG, productId, LANGUAGE_ID]);
      console.log(`\nUpdated existing language_id=${LANGUAGE_ID} row for product ${productId}.`);
    } else {
      await db.query(
        `INSERT INTO oc_product_description
           (product_id, language_id, name, description, tag, meta_title, meta_description, meta_keyword)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [productId, LANGUAGE_ID, NAME, description, TAG, META_TITLE, META_DESC, META_KEYWORD]);
      console.log(`\nInserted new language_id=${LANGUAGE_ID} row for product ${productId}.`);
    }
    console.log('If the shop caches pages, the Slovak text shows after its cache refreshes.');
  } finally {
    await db.end();
  }
}
main().catch(e => { console.error('Error:', e.message); process.exit(1); });
