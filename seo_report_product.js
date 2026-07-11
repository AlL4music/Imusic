/*
 * seo_report_product.js — read-only SEO snapshot of one OpenCart product
 * ======================================================================
 * Prints the fields that decide how a product looks / ranks on Google:
 * status (indexable?), name, meta title/description, SEO URL slug, price,
 * availability, manufacturer, categories, images and description size.
 * READ ONLY — runs only SELECTs.
 *
 * USAGE: node seo_report_product.js --sku RGR8820QM-BRE
 * ENV: DB_HOST DB_PORT DB_USER DB_PASS DB_NAME  (same secrets as the others)
 */

const mysql = require('mysql2/promise');
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };
const SKU = (opt('--sku', 'RGR8820QM-BRE') || '').trim();
const BASE = (opt('--base', 'https://all4music.sk') || '').replace(/\/$/, '');

const clean = (v) => (v == null ? v : String(v).trim());
const dbConfig = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER),
  password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME),
  connectTimeout: 30000,
};

const len = (s) => (s ? String(s).length : 0);
const trunc = (s, n) => (s && s.length > n ? s.slice(0, n) : (s || ''));

async function main() {
  const db = await mysql.createConnection(dbConfig);
  try {
    const [prod] = await db.query(
      `SELECT p.product_id, p.sku, p.model, p.price, p.quantity, p.status,
              p.image, p.date_available, p.manufacturer_id, p.tax_class_id, p.stock_status_id,
              m.name AS manufacturer
         FROM oc_product p
         LEFT JOIN oc_manufacturer m ON m.manufacturer_id = p.manufacturer_id
        WHERE p.sku = ? LIMIT 1`, [SKU]);
    if (!prod.length) { console.error(`No product with sku ${SKU}`); process.exit(2); }
    const p = prod[0];

    const [desc] = await db.query(
      `SELECT name, meta_title, meta_description, meta_keyword, tag,
              CHAR_LENGTH(description) AS desc_len
         FROM oc_product_description WHERE product_id = ? AND language_id = 1`, [p.product_id]);
    const d = desc[0] || {};

    const [seo] = await db.query(
      `SELECT keyword FROM oc_seo_url WHERE query = ? LIMIT 1`, [`product_id=${p.product_id}`]);
    const keyword = seo.length ? seo[0].keyword : null;

    const [imgs] = await db.query(
      `SELECT COUNT(*) AS n FROM oc_product_image WHERE product_id = ?`, [p.product_id]);
    const [cats] = await db.query(
      `SELECT c.category_id, cd.name FROM oc_product_to_category c
         LEFT JOIN oc_category_description cd
           ON cd.category_id = c.category_id AND cd.language_id = 1
        WHERE c.product_id = ?`, [p.product_id]);
    const [ss] = await db.query(
      `SELECT name FROM oc_stock_status WHERE stock_status_id = ? AND language_id = 1`, [p.stock_status_id]);

    const url = keyword ? `${BASE}/${keyword}` : `${BASE}/index.php?route=product/product&product_id=${p.product_id}`;

    console.log('================ SEO SNAPSHOT: ' + SKU + ' ================');
    console.log(`product_id      : ${p.product_id}`);
    console.log(`STATUS          : ${p.status == 1 ? 'ENABLED (visible & indexable)' : 'DISABLED (hidden — NOT on storefront or Google)'}`);
    console.log(`Name            : ${d.name}`);
    console.log(`Manufacturer    : ${p.manufacturer || '(none)'}`);
    console.log(`Price           : ${p.price}  (tax_class_id=${p.tax_class_id})`);
    console.log(`Quantity        : ${p.quantity}   Stock status: ${ss[0] ? ss[0].name : p.stock_status_id}`);
    console.log(`Date available  : ${p.date_available instanceof Date ? p.date_available.toISOString().slice(0,10) : p.date_available}`);
    console.log(`Main image      : ${p.image || '(none)'}`);
    console.log(`Gallery images  : ${imgs[0].n}`);
    console.log(`Categories      : ${cats.length ? cats.map(c => c.name || c.category_id).join(', ') : '(none — not in any category)'}`);
    console.log(`SEO URL         : ${url}`);
    console.log('');
    console.log(`meta_title      : (${len(d.meta_title)} chars) ${d.meta_title}`);
    console.log(`meta_description: (${len(d.meta_description)} chars) ${d.meta_description}`);
    console.log(`meta_keyword    : ${d.meta_keyword ? d.meta_keyword : '(empty)'}`);
    console.log(`product tags    : ${d.tag ? d.tag : '(empty)'}`);
    console.log(`description size : ${d.desc_len} chars of HTML`);
    console.log('');
    console.log('---- Google result preview (approx) ----');
    console.log(trunc(d.meta_title || d.name, 60) + (len(d.meta_title || d.name) > 60 ? ' …' : ''));
    console.log(url.replace(/^https?:\/\//, '') + ' ›');
    console.log(trunc(d.meta_description, 160) + (len(d.meta_description) > 160 ? ' …' : ''));
    console.log('');
    console.log('---- Flags ----');
    const flags = [];
    if (p.status != 1) flags.push('STATUS is DISABLED → the page is hidden and will NOT appear on Google. Enable it to publish.');
    if (!keyword) flags.push('No SEO URL keyword → ugly index.php URL, weaker for SEO.');
    if (len(d.meta_title) < 15) flags.push('meta_title is very short.');
    if (len(d.meta_title) > 60) flags.push('meta_title > 60 chars → Google may truncate it.');
    if (len(d.meta_description) < 70) flags.push('meta_description is short (<70) → thin snippet.');
    if (len(d.meta_description) > 160) flags.push('meta_description > 160 chars → Google may truncate it.');
    if (!d.meta_keyword) flags.push('meta_keyword empty (minor — Google ignores it, but your shop may use it).');
    if (!cats.length) flags.push('Product is in NO category → not reachable via menu/breadcrumbs, weaker internal linking.');
    if (!p.image) flags.push('No main image → no thumbnail in Google Shopping / poor social preview.');
    if (Number(p.price) === 0) flags.push('Price is 0.');
    console.log(flags.length ? flags.map(f => ' - ' + f).join('\n') : ' none — looks good.');
  } finally {
    await db.end();
  }
}
main().catch(e => { console.error('Error:', e.message); process.exit(1); });
