/*
 * create_products.js — OpenCart product creator (write-counterpart to product_audit.js)
 * =====================================================================================
 * Reads a product CSV (e.g. esp_family_products.csv produced by
 * generate_esp_family_products.py) and CREATES the products in the OpenCart
 * shop so they stop showing as "Unmatched (Prep)" / not connected.
 *
 * Connection is by SKU: oc_product.sku is set to the feed "Item ID" (CSV SKU),
 * which is exactly what the Sound Service feed config matches on
 * (feeds/sound_service.json -> match_by: "sku").
 *
 * SAFETY
 *   - DRY RUN BY DEFAULT. Nothing is written unless you pass --commit (or COMMIT=1).
 *   - IDEMPOTENT. A SKU that already exists in oc_product is skipped, so re-running
 *     only ever creates the still-missing products.
 *   - TRANSACTIONAL. Each product is inserted inside its own transaction; on any
 *     error that product is rolled back and the run continues.
 *
 * USAGE
 *   node create_products.js                         # dry run, all rows, esp_family_products.csv
 *   node create_products.js --commit                # actually create them
 *   node create_products.js --commit --limit 1      # create just the first missing one (test)
 *   node create_products.js --file out.csv --brands Edwards --commit
 *
 * ENV (same secrets as product_audit.js)
 *   DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
 *   LANGUAGE_ID (default 1), STORE_ID (default 0), TAX_CLASS_ID (default 0)
 *   STOCK_STATUS_ID (default 5), CATEGORY_ID (optional, assigns every product to it)
 */

const mysql = require('mysql2/promise');
const fs = require('fs');
const path = require('path');

// ---------- args ----------
const argv = process.argv.slice(2);
function flag(name) { return argv.includes(name); }
function opt(name, def) {
  const i = argv.indexOf(name);
  return i !== -1 && i + 1 < argv.length ? argv[i + 1] : def;
}

const COMMIT = flag('--commit') || process.env.COMMIT === '1';
const FILE = opt('--file', 'esp_family_products.csv');
const LIMIT = parseInt(opt('--limit', '0'), 10) || 0;
const BRAND_FILTER = (opt('--brands', '') || '').split(',').map(s => s.trim()).filter(Boolean);

const LANGUAGE_ID = parseInt(process.env.LANGUAGE_ID || '1', 10);
const STORE_ID = parseInt(process.env.STORE_ID || '0', 10);
const TAX_CLASS_ID = parseInt(process.env.TAX_CLASS_ID || '0', 10);
const STOCK_STATUS_ID = parseInt(process.env.STOCK_STATUS_ID || '5', 10);
const CATEGORY_ID = process.env.CATEGORY_ID ? parseInt(process.env.CATEGORY_ID, 10) : null;

const dbConfig = {
  host: process.env.DB_HOST || 'db.r6.websupport.sk',
  port: parseInt(process.env.DB_PORT || '3306', 10),
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
  connectTimeout: 30000,
};

// ---------- minimal RFC-4180 CSV parser (handles quotes, embedded commas/newlines) ----------
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', i = 0, inQuotes = false;
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1); // strip BOM
  while (i < text.length) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        inQuotes = false; i++; continue;
      }
      field += c; i++; continue;
    }
    if (c === '"') { inQuotes = true; i++; continue; }
    if (c === ',') { row.push(field); field = ''; i++; continue; }
    if (c === '\r') { i++; continue; }
    if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; i++; continue; }
    field += c; i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];
  const header = rows[0];
  return rows.slice(1)
    .filter(r => r.length && r.some(v => v !== ''))
    .map(r => Object.fromEntries(header.map((h, idx) => [h, r[idx] ?? ''])));
}

function slugify(s) {
  return s.toString().toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120) || 'product';
}

function metaDescription(name, brand) {
  const base = `Buy ${name} at All4music. ${brand} guitar — professional quality, in stock and ready to ship.`;
  return base.slice(0, 255);
}

async function main() {
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME.');
    process.exit(1);
  }
  const fpath = path.resolve(__dirname, FILE);
  if (!fs.existsSync(fpath)) { console.error(`CSV not found: ${fpath}`); process.exit(1); }

  let products = parseCSV(fs.readFileSync(fpath, 'utf8'));
  if (BRAND_FILTER.length) {
    const set = new Set(BRAND_FILTER.map(b => b.toLowerCase()));
    products = products.filter(p => set.has((p.Brand || '').toLowerCase()));
  }
  if (LIMIT > 0) products = products.slice(0, LIMIT);

  console.log(`Mode:        ${COMMIT ? 'COMMIT (writing to DB)' : 'DRY RUN (no writes)'}`);
  console.log(`CSV:         ${FILE}  (${products.length} candidate rows)`);
  console.log(`DB:          ${dbConfig.database}@${dbConfig.host}`);
  console.log(`Defaults:    language_id=${LANGUAGE_ID} store_id=${STORE_ID} stock_status_id=${STOCK_STATUS_ID}`
    + (CATEGORY_ID ? ` category_id=${CATEGORY_ID}` : '') + '\n');

  const db = await mysql.createConnection(dbConfig);

  // Cache existing manufacturers (brand -> id), create on demand.
  const [mfrRows] = await db.query('SELECT manufacturer_id, name FROM oc_manufacturer');
  const mfrByName = new Map(mfrRows.map(m => [m.name.toLowerCase(), m.manufacturer_id]));

  async function getManufacturerId(brand) {
    const key = brand.toLowerCase();
    if (mfrByName.has(key)) return mfrByName.get(key);
    if (!COMMIT) return 0; // dry run: don't create
    const [res] = await db.query('INSERT INTO oc_manufacturer (name, sort_order) VALUES (?, 0)', [brand]);
    const id = res.insertId;
    await db.query(
      `INSERT INTO oc_seo_url (store_id, language_id, query, keyword)
       VALUES (?, ?, ?, ?)`,
      [STORE_ID, LANGUAGE_ID, `manufacturer_id=${id}`, slugify(brand)]
    ).catch(() => {});
    mfrByName.set(key, id);
    return id;
  }

  let created = 0, skipped = 0, failed = 0;

  for (const p of products) {
    const sku = (p.SKU || '').trim();
    const name = (p.Name || '').trim();
    if (!sku || !name) { skipped++; continue; }

    // Idempotency: skip if a product with this SKU already exists.
    const [exists] = await db.query('SELECT product_id FROM oc_product WHERE sku = ? LIMIT 1', [sku]);
    if (exists.length) { skipped++; continue; }

    const brand = (p.Brand || '').trim();
    const model = (p.Model || '').trim() || sku;
    const price = parseFloat(p.Price || '0') || 0;
    const quantity = parseInt(p.Quantity || '0', 10) || 0;
    const ean = (p.EAN || '').trim();
    const description = p.HTML_Description || '';
    const metaTitle = name.slice(0, 255);
    const metaDesc = metaDescription(name, brand);

    if (!COMMIT) {
      console.log(`[dry-run] would create: ${sku.padEnd(10)} ${brand.padEnd(8)} ${name}`);
      created++;
      continue;
    }

    try {
      await db.beginTransaction();
      const manufacturerId = await getManufacturerId(brand);
      const now = new Date();

      const [pr] = await db.query(
        `INSERT INTO oc_product
          (model, sku, upc, ean, jan, isbn, mpn, location, quantity, stock_status_id,
           image, manufacturer_id, shipping, price, points, tax_class_id, date_available,
           weight, weight_class_id, length, width, height, length_class_id, subtract,
           minimum, sort_order, status, viewed, date_added, date_modified)
         VALUES (?, ?, '', ?, '', '', '', '', ?, ?, '', ?, 1, ?, 0, ?, ?, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, ?, ?)`,
        [model, sku, ean, quantity, STOCK_STATUS_ID, manufacturerId, price, TAX_CLASS_ID,
         now, now, now]
      );
      const productId = pr.insertId;

      await db.query(
        `INSERT INTO oc_product_description
          (product_id, language_id, name, description, tag, meta_title, meta_description, meta_keyword)
         VALUES (?, ?, ?, ?, '', ?, ?, '')`,
        [productId, LANGUAGE_ID, name, description, metaTitle, metaDesc]
      );

      await db.query(
        'INSERT INTO oc_product_to_store (product_id, store_id) VALUES (?, ?)',
        [productId, STORE_ID]
      );

      // Unique SEO keyword (append sku on collision).
      let keyword = slugify(name);
      const [clash] = await db.query('SELECT seo_url_id FROM oc_seo_url WHERE keyword = ? LIMIT 1', [keyword]);
      if (clash.length) keyword = `${keyword}-${sku}`;
      await db.query(
        `INSERT INTO oc_seo_url (store_id, language_id, query, keyword) VALUES (?, ?, ?, ?)`,
        [STORE_ID, LANGUAGE_ID, `product_id=${productId}`, keyword]
      );

      if (CATEGORY_ID) {
        await db.query(
          'INSERT INTO oc_product_to_category (product_id, category_id) VALUES (?, ?)',
          [productId, CATEGORY_ID]
        );
      }

      await db.commit();
      created++;
      if (created % 50 === 0) console.log(`  ...created ${created}`);
    } catch (e) {
      await db.rollback().catch(() => {});
      failed++;
      console.error(`  FAILED ${sku} (${name}): ${e.message}`);
    }
  }

  await db.end();

  console.log('\n=== SUMMARY ===');
  console.log(`${COMMIT ? 'Created' : 'Would create'}: ${created}`);
  console.log(`Skipped (exists/invalid): ${skipped}`);
  if (COMMIT) console.log(`Failed: ${failed}`);
  if (!COMMIT) console.log('\nDRY RUN — no changes were made. Re-run with --commit to create these products.');
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
