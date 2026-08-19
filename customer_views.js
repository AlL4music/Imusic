const mysql = require('mysql2/promise');

const dbConfig = {
  host: process.env.DB_HOST || 'db.r6.websupport.sk',
  port: parseInt(process.env.DB_PORT || '3306'),
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
  connectTimeout: 30000,
};

const PRODUCT_ID = parseInt(process.env.PRODUCT_ID || '39052'); // Ibanez ICWH727

async function main() {
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME env vars.');
    process.exit(1);
  }

  const db = await mysql.createConnection(dbConfig);

  const [[product]] = await db.query(
    `SELECT p.product_id, pd.name, p.model
     FROM oc_product p
     LEFT JOIN oc_product_description pd ON p.product_id = pd.product_id AND pd.language_id = 1
     WHERE p.product_id = ?`,
    [PRODUCT_ID]
  );
  if (!product) {
    console.error(`Product ${PRODUCT_ID} not found.`);
    process.exit(1);
  }

  const [seoRows] = await db.query(
    `SELECT keyword FROM oc_seo_url WHERE query = ? AND language_id = 1`,
    [`product_id=${PRODUCT_ID}`]
  );
  const keywords = seoRows.map((r) => r.keyword).filter(Boolean);

  const urlConditions = [`url LIKE ?`];
  const urlParams = [`%product_id=${PRODUCT_ID}%`];
  for (const kw of keywords) {
    urlConditions.push(`url LIKE ?`);
    urlParams.push(`%${kw}%`);
  }
  const urlWhere = `(${urlConditions.join(' OR ')})`;

  const [[totalOnline]] = await db.query(
    `SELECT COUNT(DISTINCT ip) AS visitors FROM oc_customer_online`
  );

  const [[onProductNow]] = await db.query(
    `SELECT COUNT(DISTINCT ip) AS visitors FROM oc_customer_online
     WHERE ${urlWhere} AND date_added >= NOW() - INTERVAL 5 MINUTE`,
    urlParams
  );

  const [[onProductHour]] = await db.query(
    `SELECT COUNT(DISTINCT ip) AS visitors FROM oc_customer_online
     WHERE ${urlWhere}`,
    urlParams
  );

  const [rows] = await db.query(
    `SELECT ip, customer_id, url, date_added FROM oc_customer_online
     WHERE ${urlWhere} ORDER BY date_added DESC`,
    urlParams
  );

  const result = {
    generated_at: new Date().toISOString(),
    product: { id: product.product_id, name: product.name, model: product.model, seo_keywords: keywords },
    viewers_on_product_last_5_min: onProductNow.visitors,
    viewers_on_product_in_table: onProductHour.visitors,
    total_visitors_online: totalOnline.visitors,
    sessions: rows.map((r) => ({
      ip: r.ip,
      customer_id: r.customer_id,
      logged_in: r.customer_id > 0,
      url: r.url,
      last_seen: r.date_added,
    })),
  };

  console.log('=== CUSTOMER VIEWS RESULT ===');
  console.log(JSON.stringify(result, null, 2));
  console.log('=== END RESULT ===');

  await db.end();
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
