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

const REPORT_PATH = path.resolve(__dirname, 'reports', 'product_audit.json');

async function main() {
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME env vars.');
    process.exit(1);
  }

  const db = await mysql.createConnection(dbConfig);
  console.log('Connected to DB. Running product audit...\n');

  // 1. Get all enabled products with descriptions (lang 1)
  const [products] = await db.query(`
    SELECT p.product_id, p.model, p.sku, p.price, p.image, p.manufacturer_id,
           p.status, p.quantity,
           pd.name, pd.description, pd.meta_title, pd.meta_description, pd.tag
    FROM oc_product p
    LEFT JOIN oc_product_description pd ON p.product_id = pd.product_id AND pd.language_id = 1
    WHERE p.status = 1
    ORDER BY p.product_id
  `);
  console.log(`Total enabled products: ${products.length}`);

  // 2. SEO URLs
  const [seoUrls] = await db.query(`
    SELECT query, keyword FROM oc_seo_url
    WHERE query LIKE 'product_id=%' AND store_id = 0 AND language_id = 1
  `);
  const seoMap = new Map();
  for (const s of seoUrls) {
    const pid = parseInt(s.query.replace('product_id=', ''));
    seoMap.set(pid, s.keyword);
  }

  // 3. Product images count
  const [images] = await db.query(`
    SELECT product_id, COUNT(*) as img_count FROM oc_product_image GROUP BY product_id
  `);
  const imgMap = new Map();
  for (const i of images) imgMap.set(i.product_id, i.img_count);

  // 4. Category assignments
  const [categories] = await db.query(`
    SELECT product_id, COUNT(*) as cat_count FROM oc_product_to_category GROUP BY product_id
  `);
  const catMap = new Map();
  for (const c of categories) catMap.set(c.product_id, c.cat_count);

  // 5. Manufacturer names
  const [manufacturers] = await db.query(`SELECT manufacturer_id, name FROM oc_manufacturer`);
  const mfrMap = new Map();
  for (const m of manufacturers) mfrMap.set(m.manufacturer_id, m.name);

  // 6. Audit each product
  const results = { complete: [], incomplete: [] };

  const issueCounters = {
    no_name: 0, no_description: 0, short_description: 0,
    no_meta_title: 0, no_meta_description: 0, no_seo_url: 0,
    no_image: 0, no_extra_images: 0, no_category: 0,
    no_manufacturer: 0, no_price: 0, no_model: 0,
  };

  for (const p of products) {
    const pid = p.product_id;
    const seoUrl = seoMap.get(pid) || '';
    const extraImages = imgMap.get(pid) || 0;
    const catCount = catMap.get(pid) || 0;
    const mfrName = mfrMap.get(p.manufacturer_id) || '';
    const desc = (p.description || '').replace(/<[^>]*>/g, '').trim();

    // Core checks (required for "DONE")
    const coreIssues = [];
    if (!p.name || !p.name.trim()) coreIssues.push('no_name');
    if (!desc) coreIssues.push('no_description');
    else if (desc.length < 50) coreIssues.push('short_description');
    if (!p.meta_title || !p.meta_title.trim()) coreIssues.push('no_meta_title');
    if (!p.meta_description || !p.meta_description.trim()) coreIssues.push('no_meta_description');
    if (!seoUrl) coreIssues.push('no_seo_url');
    if (!p.image || !p.image.trim() || p.image === 'no_image.png' || p.image === 'placeholder.png') coreIssues.push('no_image');
    if (!p.manufacturer_id || p.manufacturer_id === 0) coreIssues.push('no_manufacturer');
    if (!p.price || p.price <= 0) coreIssues.push('no_price');
    if (!p.model || !p.model.trim()) coreIssues.push('no_model');

    // Extra checks (tracked but not required)
    const extraIssues = [];
    if (extraImages === 0) extraIssues.push('no_extra_images');
    if (catCount === 0) extraIssues.push('no_category');

    for (const issue of [...coreIssues, ...extraIssues]) issueCounters[issue]++;

    const CORE_TOTAL = 10;
    const entry = {
      id: pid,
      name: (p.name || '').substring(0, 80),
      model: (p.model || '').substring(0, 40),
      manufacturer: mfrName,
      issues: coreIssues,
      extras: extraIssues,
      score: Math.round(((CORE_TOTAL - coreIssues.length) / CORE_TOTAL) * 100),
    };

    if (coreIssues.length === 0) results.complete.push(entry);
    else results.incomplete.push(entry);
  }

  results.incomplete.sort((a, b) => a.score - b.score);

  // 7. Build report
  const report = {
    timestamp: new Date().toISOString(),
    total_products: products.length,
    complete_count: results.complete.length,
    incomplete_count: results.incomplete.length,
    completeness_pct: Math.round((results.complete.length / products.length) * 100 * 10) / 10,
    issue_summary: {
      no_name: { count: issueCounters.no_name, label: 'Missing product name' },
      no_description: { count: issueCounters.no_description, label: 'Missing description' },
      short_description: { count: issueCounters.short_description, label: 'Description too short (<50 chars)' },
      no_meta_title: { count: issueCounters.no_meta_title, label: 'Missing meta title' },
      no_meta_description: { count: issueCounters.no_meta_description, label: 'Missing meta description' },
      no_seo_url: { count: issueCounters.no_seo_url, label: 'Missing SEO URL' },
      no_image: { count: issueCounters.no_image, label: 'Missing main image' },
      no_extra_images: { count: issueCounters.no_extra_images, label: 'No additional images' },
      no_category: { count: issueCounters.no_category, label: 'Not in any category' },
      no_manufacturer: { count: issueCounters.no_manufacturer, label: 'No manufacturer set' },
      no_price: { count: issueCounters.no_price, label: 'No price or price is 0' },
      no_model: { count: issueCounters.no_model, label: 'Missing model/SKU' },
    },
    by_manufacturer: {},
    products: [...results.incomplete, ...results.complete].map(p => ({
      id: p.id, n: p.name, m: p.model, b: p.manufacturer,
      i: p.issues, x: p.extras, s: p.score,
    })),
  };

  // Manufacturer breakdown
  const mfrStats = {};
  for (const p of [...results.complete, ...results.incomplete]) {
    const mfr = p.manufacturer || 'No Manufacturer';
    if (!mfrStats[mfr]) mfrStats[mfr] = { total: 0, complete: 0, incomplete: 0 };
    mfrStats[mfr].total++;
    if (p.issues.length === 0) mfrStats[mfr].complete++;
    else mfrStats[mfr].incomplete++;
  }
  report.by_manufacturer = Object.entries(mfrStats)
    .sort((a, b) => b[1].total - a[1].total)
    .map(([name, stats]) => ({
      name, total: stats.total, complete: stats.complete,
      incomplete: stats.incomplete,
      pct: Math.round((stats.complete / stats.total) * 100),
    }));

  // Save
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  const { products: prodList, ...summary } = report;
  let json = JSON.stringify(summary, null, 2);
  json = json.slice(0, -2) + ',\n  "products": ' + JSON.stringify(prodList) + '\n}';
  fs.writeFileSync(REPORT_PATH, json);
  console.log(`\nReport saved to: ${REPORT_PATH}`);

  // Print summary
  console.log('\n=== PRODUCT AUDIT SUMMARY ===');
  console.log(`Total products:  ${report.total_products}`);
  console.log(`Complete:        ${report.complete_count} (${report.completeness_pct}%)`);
  console.log(`Needs work:      ${report.incomplete_count}`);
  console.log('\nIssue breakdown:');
  for (const [key, val] of Object.entries(report.issue_summary)) {
    if (val.count > 0) {
      const bar = '█'.repeat(Math.round(val.count / report.total_products * 40));
      console.log(`  ${val.label.padEnd(35)} ${String(val.count).padStart(6)} (${Math.round(val.count / report.total_products * 100)}%) ${bar}`);
    }
  }

  await db.end();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
