/**
 * Sound Service Labs API Scraper
 *
 * Fetches all products from soundservicelabs.com/api/v2/pricing
 * Outputs CSV with B-Stock rows (matching existing feed format)
 *
 * Usage: node sound_service.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// --- Config ---
const API_URL = 'https://soundservicelabs.com/api/v2/pricing';
const AUTH_EMAIL = 'ptr.salik@gmail.com';
const AUTH_PASSWORD = 'Medvedik14811!';
const AUTH_TOKEN = '486|DMlUe1iMG9MRtPzGBu3seff0UZcdphS5BrGLZkE3';
const OUTPUT_FILE = path.join(__dirname, 'sound serivce.csv');

// --- HTTP helpers ---

function httpsRequest(url, options, body) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const reqOptions = {
      hostname: urlObj.hostname,
      port: 443,
      path: urlObj.pathname + urlObj.search,
      method: options.method || 'GET',
      headers: options.headers || {},
      timeout: 120000,
    };

    const req = https.request(reqOptions, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const responseBody = Buffer.concat(chunks).toString('utf-8');
        resolve({ statusCode: res.statusCode, body: responseBody, headers: res.headers });
      });
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out')); });

    if (body) req.write(body);
    req.end();
  });
}

// --- XML Parser (lightweight, no dependencies) ---

function parseProducts(xml) {
  const products = [];

  // Split by <product> tags
  const productBlocks = xml.split(/<product>/i).slice(1);

  for (const block of productBlocks) {
    const endIdx = block.indexOf('</product>');
    const productXml = endIdx >= 0 ? block.substring(0, endIdx) : block;

    const product = {};
    const fields = [
      'item', 'brand', 'description', 'stock', 'dealer', 'ean',
      'eta', 'discontinued', 'bstock', 'btrade'
    ];

    for (const field of fields) {
      const regex = new RegExp(`<${field}[^>]*>([\\s\\S]*?)</${field}>`, 'i');
      const match = productXml.match(regex);
      if (match) {
        let val = match[1].trim();
        // Handle CDATA
        const cdataMatch = val.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
        if (cdataMatch) val = cdataMatch[1];
        // Decode XML entities
        val = val.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
        product[field] = val;
      } else {
        product[field] = '';
      }
    }

    if (product.item) {
      products.push(product);
    }
  }

  return products;
}

// --- CSV Generation (matches existing format) ---

function escapeCsvField(str) {
  if (!str) return '';
  // If contains comma, quote, or newline — wrap in quotes
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

function generateCsv(products) {
  const rows = [];
  rows.push('"Item ID","Značka","Popis","Sklad","Cena (Dealer)","EAN","ETA","Ukončené"');

  let totalRows = 0;

  for (const item of products) {
    const stock = item.stock || '0';
    const description = escapeCsvField(item.description);
    const eta = item.eta || '';
    const discontinued = item.discontinued || '0';
    const dealer = item.dealer ? `"${item.dealer}"` : '';
    const ean = item.ean || '';

    // Main row
    const row = [
      item.item,
      escapeCsvField(item.brand),
      description,
      stock,
      dealer,
      ean,
      eta ? `"${eta}"` : '',
      discontinued
    ].join(',');
    rows.push(row);
    totalRows++;

    // B-Stock row (only if btrade has a value)
    const bstock = item.bstock || '0';
    const btrade = item.btrade || '';
    if (btrade) {
      const bDescription = item.description
        ? escapeCsvField('[B-Stock] ' + item.description)
        : '"[B-Stock]"';
      const bItemId = '2' + item.item.substring(1); // 10000707 → 20000707

      const bRow = [
        bItemId,
        escapeCsvField(item.brand),
        bDescription,
        bstock,
        btrade,
        ean,
        eta ? `"${eta}"` : '',
        discontinued
      ].join(',');
      rows.push(bRow);
      totalRows++;
    }
  }

  return { csv: rows.join('\n') + '\n', totalRows, productCount: products.length };
}

// --- Main ---

async function main() {
  const startTime = Date.now();

  // Try fetching with Bearer token first, fallback to form POST
  console.log('[1/2] Fetching products from Sound Service API...');

  let response;

  // Attempt 1: Bearer token
  try {
    console.log('    Trying Bearer token auth...');
    response = await httpsRequest(API_URL, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${AUTH_TOKEN}`,
        'Accept': 'application/xml',
      },
    });

    if (response.statusCode === 401 || response.statusCode === 403) {
      throw new Error(`Auth failed (${response.statusCode}), trying form POST...`);
    }
  } catch (err) {
    console.log(`    ${err.message}`);
    // Attempt 2: POST with email/password
    console.log('    Trying form POST auth...');
    const formBody = `email=${encodeURIComponent(AUTH_EMAIL)}&password=${encodeURIComponent(AUTH_PASSWORD)}`;
    response = await httpsRequest(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/xml',
      },
    }, formBody);
  }

  if (response.statusCode >= 400) {
    console.error(`API returned HTTP ${response.statusCode}`);
    console.error(response.body.substring(0, 500));
    process.exit(1);
  }

  console.log(`    Response: ${response.statusCode} (${(response.body.length / 1024 / 1024).toFixed(1)} MB)`);

  // Parse XML
  const products = parseProducts(response.body);
  console.log(`    Parsed ${products.length} products.`);

  if (products.length === 0) {
    // Save response for debugging
    const debugFile = path.join(__dirname, 'sound_service_debug.xml');
    fs.writeFileSync(debugFile, response.body.substring(0, 10000));
    console.error(`    No products found. First 10KB saved to ${debugFile}`);
    process.exit(1);
  }

  // Generate CSV
  console.log('[2/2] Generating CSV...');
  const { csv, totalRows, productCount } = generateCsv(products);

  fs.writeFileSync(OUTPUT_FILE, csv, 'utf-8');

  const inStock = products.filter(p => parseInt(p.stock) > 0).length;
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log(`\nDone in ${elapsed}s!`);
  console.log(`  Products: ${productCount}`);
  console.log(`  CSV rows (incl. B-Stock): ${totalRows}`);
  console.log(`  In stock: ${inStock}`);
  console.log(`  Out of stock: ${productCount - inStock}`);
  console.log(`  Output: ${OUTPUT_FILE}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
