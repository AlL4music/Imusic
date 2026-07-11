/*
 * update_product_seo.js — set SEO meta fields for one OpenCart product
 * ====================================================================
 * Updates meta_title / meta_description / meta_keyword / tag on
 * oc_product_description, and optionally the SEO URL slug on oc_seo_url.
 * Values come from env vars so long text with punctuation stays clean:
 *   SEO_TITLE, SEO_DESC, SEO_KEYWORDS, SEO_TAG, SEO_SLUG
 *
 * SAFE: dry run by default (needs --commit). Only the product matched by
 * --sku is touched. Slug uniqueness is checked; on collision the SKU is
 * appended instead of clobbering another product's URL.
 *
 * USAGE: node update_product_seo.js --sku RGR8820QM-BRE [--commit]
 * ENV: DB_HOST DB_PORT DB_USER DB_PASS DB_NAME + the SEO_* vars above
 */

const mysql = require('mysql2/promise');
const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };

const COMMIT = flag('--commit') || process.env.COMMIT === '1';
const SKU = (opt('--sku', 'RGR8820QM-BRE') || '').trim();
const LANGUAGE_ID = parseInt(process.env.LANGUAGE_ID || '1', 10);
const STORE_ID = parseInt(process.env.STORE_ID || '0', 10);

const TITLE = process.env.SEO_TITLE || '';
const DESC = process.env.SEO_DESC || '';
const KEYWORDS = process.env.SEO_KEYWORDS || '';
const TAG = process.env.SEO_TAG || '';
const SLUG = (process.env.SEO_SLUG || '').trim();

const clean = (v) => (v == null ? v : String(v).trim());
const dbConfig = {
  host: clean(process.env.DB_HOST) || 'db.r6.websupport.sk',
  port: parseInt(clean(process.env.DB_PORT) || '3306', 10),
  user: clean(process.env.DB_USER),
  password: process.env.DB_PASS,
  database: clean(process.env.DB_NAME),
  connectTimeout: 30000,
};

async function main() {
  if (!TITLE || !DESC) { console.error('SEO_TITLE and SEO_DESC are required.'); process.exit(1); }
  const db = await mysql.createConnection(dbConfig);
  try {
    const [rows] = await db.query('SELECT product_id FROM oc_product WHERE sku = ? LIMIT 1', [SKU]);
    if (!rows.length) { console.error(`No product with sku ${SKU}`); process.exit(2); }
    const productId = rows[0].product_id;

    console.log(`Mode: ${COMMIT ? 'COMMIT' : 'DRY RUN'}   product_id=${productId}   sku=${SKU}\n`);
    console.log(`meta_title       (${TITLE.length}): ${TITLE}`);
    console.log(`meta_description (${DESC.length}): ${DESC}`);
    console.log(`meta_keyword     : ${KEYWORDS}`);
    console.log(`tag              : ${TAG}`);
    console.log(`slug             : ${SLUG || '(unchanged)'}`);

    // Resolve slug uniqueness (schema uses query/keyword columns).
    let finalSlug = SLUG;
    if (SLUG) {
      const [clash] = await db.query(
        'SELECT query FROM oc_seo_url WHERE keyword = ? LIMIT 1', [SLUG]);
      if (clash.length && clash[0].query !== `product_id=${productId}`) {
        finalSlug = `${SLUG}-${SKU.toLowerCase()}`;
        console.log(`  (slug '${SLUG}' taken → using '${finalSlug}')`);
      }
    }

    if (!COMMIT) {
      console.log('\nDRY RUN — nothing written. Re-run with --commit to apply.');
      return;
    }

    await db.beginTransaction();
    await db.query(
      `UPDATE oc_product_description
          SET meta_title = ?, meta_description = ?, meta_keyword = ?, tag = ?
        WHERE product_id = ? AND language_id = ?`,
      [TITLE, DESC, KEYWORDS, TAG, productId, LANGUAGE_ID]);

    if (finalSlug) {
      const [ex] = await db.query(
        'SELECT seo_url_id FROM oc_seo_url WHERE query = ? AND language_id = ? LIMIT 1',
        [`product_id=${productId}`, LANGUAGE_ID]);
      if (ex.length) {
        await db.query('UPDATE oc_seo_url SET keyword = ? WHERE seo_url_id = ?', [finalSlug, ex[0].seo_url_id]);
      } else {
        await db.query(
          'INSERT INTO oc_seo_url (store_id, language_id, query, keyword) VALUES (?, ?, ?, ?)',
          [STORE_ID, LANGUAGE_ID, `product_id=${productId}`, finalSlug]);
      }
    }
    await db.commit();
    console.log(`\nUpdated SEO for product ${productId}. New URL slug: ${finalSlug || '(unchanged)'}`);
    console.log('If the shop caches pages, the new title/description show after its cache refreshes.');
  } catch (e) {
    await db.rollback().catch(() => {});
    console.error('FAILED:', e.message);
    process.exit(1);
  } finally {
    await db.end();
  }
}
main().catch(e => { console.error('Error:', e.message); process.exit(1); });
