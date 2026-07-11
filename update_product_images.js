/*
 * update_product_images.js — repoint an existing OpenCart product's images
 * =========================================================================
 * Sets oc_product.image (main) and rebuilds oc_product_image (gallery) for a
 * product identified by SKU. Use it when the photo files live at a different
 * path than the product currently points to (e.g. uploaded to catalog/ via
 * the OpenCart Image Manager instead of catalog/ibanez/).
 *
 * SAFE: dry run by default (needs --commit). Only touches the one product
 * matched by --sku. Paths are OpenCart-relative (no leading 'image/').
 *
 * USAGE
 *   node update_product_images.js --sku RGR8820QM-BRE \
 *     --main catalog/0.C50.jpg \
 *     --gallery catalog/16.26EA.jpg,catalog/78.3222.jpg            # dry run
 *   ... --commit                                                    # apply
 *
 * ENV (same DB secrets as create_products.js): DB_HOST DB_PORT DB_USER DB_PASS DB_NAME
 */

const mysql = require('mysql2/promise');

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => { const i = argv.indexOf(n); return i !== -1 && i + 1 < argv.length ? argv[i + 1] : d; };

const COMMIT = flag('--commit') || process.env.COMMIT === '1';
const SKU = (opt('--sku', '') || '').trim();
const MAIN = (opt('--main', '') || '').trim();
const GALLERY = (opt('--gallery', '') || '').split(',').map(s => s.trim()).filter(Boolean);

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
  if (!SKU || !MAIN) {
    console.error('Usage: --sku <SKU> --main <path> [--gallery a,b] [--commit]');
    process.exit(1);
  }
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME.');
    process.exit(1);
  }

  console.log(`Mode:    ${COMMIT ? 'COMMIT (writing to DB)' : 'DRY RUN (no writes)'}`);
  console.log(`DB:      ${dbConfig.database}@${dbConfig.host}`);
  console.log(`SKU:     ${SKU}`);
  console.log(`Main:    ${MAIN}`);
  console.log(`Gallery: ${GALLERY.length ? GALLERY.join(', ') : '(none)'}\n`);

  const db = await mysql.createConnection(dbConfig);
  try {
    const [rows] = await db.query('SELECT product_id FROM oc_product WHERE sku = ? LIMIT 1', [SKU]);
    if (!rows.length) {
      console.error(`No product found with sku = ${SKU}. Nothing to do.`);
      process.exit(2);
    }
    const productId = rows[0].product_id;
    console.log(`Found product_id = ${productId}`);

    if (!COMMIT) {
      console.log('\n[dry-run] would set main image and replace gallery as above.');
      console.log('DRY RUN — no changes were made. Re-run with --commit to apply.');
      return;
    }

    await db.beginTransaction();
    await db.query('UPDATE oc_product SET image = ?, date_modified = NOW() WHERE product_id = ?', [MAIN, productId]);
    await db.query('DELETE FROM oc_product_image WHERE product_id = ?', [productId]);
    for (let i = 0; i < GALLERY.length; i++) {
      await db.query(
        'INSERT INTO oc_product_image (product_id, image, sort_order) VALUES (?, ?, ?)',
        [productId, GALLERY[i], i + 1]
      );
    }
    await db.commit();
    console.log(`\nUpdated product ${productId}: main image + ${GALLERY.length} gallery image(s).`);
    console.log('Note: OpenCart caches resized thumbnails — if the shop still shows the old/blank');
    console.log('image, clear image cache (Dashboard) or delete image/cache/ so it regenerates.');
  } catch (e) {
    await db.rollback().catch(() => {});
    console.error('FAILED:', e.message);
    process.exit(1);
  } finally {
    await db.end();
  }
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
