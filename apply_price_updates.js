// Applies dealer x 1.35 prices to underpriced products.
// Keys updates by product_id. Snapshots every old price for rollback.
// Safety: skips any item whose current DB price no longer matches the audited price.
const mysql = require('mysql2/promise');
const fs = require('fs');
const path = require('path');

const dbConfig = {
  host: process.env.DB_HOST || 'db.r6.websupport.sk',
  port: parseInt(process.env.DB_PORT || '3306'),
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
  connectTimeout: 30000,
};

async function main() {
  const dry = process.env.DRY_RUN === '1';
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME.');
    process.exit(1);
  }
  const updates = JSON.parse(fs.readFileSync(path.resolve(__dirname, 'price_updates.json'), 'utf8'));
  console.log(`${dry ? '[DRY RUN] ' : ''}Loaded ${updates.length} intended updates.`);

  const db = await mysql.createConnection(dbConfig);
  const backup = [];
  let applied = 0, skipped = 0;

  for (const u of updates) {
    const [rows] = await db.query('SELECT product_id, sku, price FROM oc_product WHERE product_id = ? LIMIT 1', [u.id]);
    if (!rows.length) {
      console.warn(`MISSING product_id=${u.id} sku=${u.sku}`);
      backup.push({ id: u.id, sku: u.sku, status: 'missing' });
      skipped++; continue;
    }
    const cur = Number(rows[0].price);
    if (Math.abs(cur - u.old) > 0.02) {
      console.warn(`SKIP product_id=${u.id} sku=${u.sku}: DB price ${cur} != audited ${u.old} (changed since audit)`);
      backup.push({ id: u.id, sku: u.sku, old_price: cur, intended_new: u.new, status: 'skipped_mismatch' });
      skipped++; continue;
    }
    backup.push({ id: u.id, sku: u.sku, old_price: cur, new_price: u.new, status: dry ? 'dry' : 'applied' });
    if (!dry) {
      await db.query('UPDATE oc_product SET price = ?, date_modified = NOW() WHERE product_id = ?', [u.new, u.id]);
    }
    applied++;
  }

  const stamp = process.env.GITHUB_RUN_ID || 'manual';
  const outPath = path.resolve(__dirname, 'reports', `price_backup_${dry ? 'dry_' : ''}${stamp}.json`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify({ run: stamp, dry, applied, skipped, items: backup }, null, 2));

  console.log(`\n${dry ? '[DRY RUN] ' : ''}Done. ${dry ? 'would apply' : 'applied'}=${applied}  skipped=${skipped}`);
  console.log(`Backup written: ${outPath}`);
  await db.end();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
