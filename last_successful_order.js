const mysql = require('mysql2/promise');

const dbConfig = {
  host: process.env.DB_HOST || 'db.r6.websupport.sk',
  port: parseInt(process.env.DB_PORT || '3306'),
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
  connectTimeout: 30000,
};

async function main() {
  if (!dbConfig.user || !dbConfig.password || !dbConfig.database) {
    console.error('Missing DB credentials. Set DB_USER, DB_PASS, DB_NAME env vars.');
    process.exit(1);
  }

  const db = await mysql.createConnection(dbConfig);

  // OpenCart successful order statuses:
  // 2 = Processing, 3 = Shipped, 5 = Complete, 15 = Processed
  const [rows] = await db.execute(`
    SELECT
      o.order_id,
      o.firstname,
      o.lastname,
      o.email,
      o.telephone,
      o.total,
      o.currency_code,
      o.date_added,
      o.date_modified,
      o.payment_method,
      o.shipping_method,
      os.name AS order_status
    FROM oc_order o
    LEFT JOIN oc_order_status os
      ON o.order_status_id = os.order_status_id AND os.language_id = 1
    WHERE o.order_status_id IN (2, 3, 5, 15)
    ORDER BY o.date_added DESC
    LIMIT 1
  `);

  if (rows.length === 0) {
    console.log('No successful orders found.');
    await db.end();
    return;
  }

  const order = rows[0];
  console.log('=== Last Successful Order ===');
  console.log(`Order ID:        #${order.order_id}`);
  console.log(`Date:            ${order.date_added}`);
  console.log(`Customer:        ${order.firstname} ${order.lastname}`);
  console.log(`Email:           ${order.email}`);
  console.log(`Phone:           ${order.telephone}`);
  console.log(`Total:           ${order.total} ${order.currency_code}`);
  console.log(`Payment:         ${order.payment_method}`);
  console.log(`Shipping:        ${order.shipping_method}`);
  console.log(`Status:          ${order.order_status}`);

  // Fetch order products
  const [products] = await db.execute(`
    SELECT
      op.name,
      op.model,
      op.quantity,
      op.price,
      op.total
    FROM oc_order_product op
    WHERE op.order_id = ?
  `, [order.order_id]);

  if (products.length > 0) {
    console.log('\n--- Products ---');
    products.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.name} (${p.model}) x${p.quantity} — ${p.price} each, total: ${p.total}`);
    });
  }

  await db.end();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
