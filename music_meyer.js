/**
 * Music Meyer SOAP API Scraper
 *
 * 1. Calls getItemList to fetch ALL product article numbers from Brand Unit 9
 * 2. Calls getAvailabilityList (in batches) to get stock availability
 * 3. Outputs MM.csv in the format: "Kod";"Stav" (article number; 1/0)
 *
 * Usage: node music_meyer.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// --- Config ---
const CUSTOMER_NR = '1004769';
const PASSWORD_MD5 = 'cb41e5098579086e4a9d30c6cddc220e';
const BRAND_UNIT = '9'; // MUSIK MEYER Central Europe
const ENDPOINT = 'https://extra.musik-meyer.net/ws/services/MMGCustomizedItems';
const AVAILABILITY_BATCH_SIZE = 200; // how many articles per availability request
const OUTPUT_FILE = path.join(__dirname, 'MM.csv');

// --- SOAP Templates ---

function buildGetItemListSOAP() {
  return `<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="urn:MMGCustomizedItems"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
  <soapenv:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>${CUSTOMER_NR}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">${PASSWORD_MD5}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <urn:getItemList soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
      <kdnr xsi:type="xsd:string">${CUSTOMER_NR}</kdnr>
      <finr xsi:type="xsd:string">${BRAND_UNIT}</finr>
      <brand xsi:type="xsd:string"></brand>
      <filterdatum xsi:type="xsd:string">01.01.2000</filterdatum>
      <showmodified xsi:type="xsd:string">true</showmodified>
      <shownew xsi:type="xsd:string">true</shownew>
    </urn:getItemList>
  </soapenv:Body>
</soapenv:Envelope>`;
}

function buildGetAvailabilitySOAP(articleNumbers) {
  const items = articleNumbers
    .map(nr => `            <item xsi:type="xsd:string">${escapeXml(nr)}</item>`)
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="urn:MMGCustomizedItems"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
  <soapenv:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>${CUSTOMER_NR}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">${PASSWORD_MD5}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <urn:getAvailabilityList soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
      <kdnr xsi:type="xsd:string">${CUSTOMER_NR}</kdnr>
      <finr xsi:type="xsd:string">${BRAND_UNIT}</finr>
      <artnrs xsi:type="soapenc:Array" soapenc:arrayType="xsd:string[]">
${items}
      </artnrs>
      <useMultiRefs xsi:type="xsd:string">false</useMultiRefs>
    </urn:getAvailabilityList>
  </soapenv:Body>
</soapenv:Envelope>`;
}

// --- Helpers ---

function escapeXml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function soapRequest(body) {
  return new Promise((resolve, reject) => {
    const url = new URL(ENDPOINT);
    const options = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '',
      },
      timeout: 120000, // 2 min timeout for large responses
    };

    const req = https.request(options, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const responseBody = Buffer.concat(chunks).toString('utf-8');
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${responseBody.substring(0, 500)}`));
        } else {
          resolve(responseBody);
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timed out'));
    });

    req.write(body);
    req.end();
  });
}

/**
 * Extract all article numbers (ccgart) from getItemList response.
 * The response XML contains <ccgart> elements with article numbers.
 */
function extractArticleNumbers(xml) {
  const articles = [];
  // Match ccgart values - they appear as <ccgart xsi:type="...">VALUE</ccgart>
  const regex = /<ccgart[^>]*>([^<]+)<\/ccgart>/gi;
  let match;
  while ((match = regex.exec(xml)) !== null) {
    const artNr = match[1].trim();
    if (artNr && artNr !== '' && artNr !== 'null') {
      articles.push(artNr);
    }
  }
  return articles;
}

/**
 * Extract availability from getAvailabilityList response.
 * Returns Map of articleNumber -> boolean (available or not)
 */
function extractAvailability(xml) {
  const availability = new Map();

  // The response contains items with <artnr> and <availability> fields
  // Match pairs of artnr + availability
  const artnrRegex = /<artnr[^>]*>([^<]+)<\/artnr>/gi;
  const availRegex = /<availability[^>]*>([^<]+)<\/availability>/gi;

  const artNumbers = [];
  const availValues = [];

  let match;
  while ((match = artnrRegex.exec(xml)) !== null) {
    artNumbers.push(match[1].trim());
  }
  while ((match = availRegex.exec(xml)) !== null) {
    availValues.push(match[1].trim().toLowerCase());
  }

  for (let i = 0; i < artNumbers.length; i++) {
    const avail = availValues[i] || 'false';
    availability.set(artNumbers[i], avail === 'true' || avail === 'y');
  }

  return availability;
}

/**
 * Split array into chunks
 */
function chunk(arr, size) {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

// --- Main ---

async function main() {
  const startTime = Date.now();

  // Step 1: Get all products
  console.log(`[1/3] Fetching all products from Brand Unit ${BRAND_UNIT}...`);
  const itemListSoap = buildGetItemListSOAP();
  let itemListResponse;
  try {
    itemListResponse = await soapRequest(itemListSoap);
  } catch (err) {
    console.error('Failed to fetch item list:', err.message);
    process.exit(1);
  }

  const articleNumbers = extractArticleNumbers(itemListResponse);
  console.log(`    Found ${articleNumbers.length} article numbers.`);

  if (articleNumbers.length === 0) {
    // Maybe ccgart is empty but there's another field - try to extract from response
    console.log('    No ccgart found. Checking for alternative field names...');
    // Try artnr or ordernr
    const altRegex = /<(?:artnr|ordernr)[^>]*>([^<]+)<\/(?:artnr|ordernr)>/gi;
    let altMatch;
    while ((altMatch = altRegex.exec(itemListResponse)) !== null) {
      const nr = altMatch[1].trim();
      if (nr && nr !== 'null') articleNumbers.push(nr);
    }
    console.log(`    Found ${articleNumbers.length} articles via alternate fields.`);

    if (articleNumbers.length === 0) {
      // Save raw response for debugging
      const debugFile = path.join(__dirname, 'MM_debug_response.xml');
      fs.writeFileSync(debugFile, itemListResponse);
      console.error(`    No articles found. Raw response saved to ${debugFile}`);
      process.exit(1);
    }
  }

  // Deduplicate
  const uniqueArticles = [...new Set(articleNumbers)];
  console.log(`    Unique articles: ${uniqueArticles.length}`);

  // Step 2: Get availability in batches
  console.log(`[2/3] Fetching availability (${Math.ceil(uniqueArticles.length / AVAILABILITY_BATCH_SIZE)} batches of ${AVAILABILITY_BATCH_SIZE})...`);
  const batches = chunk(uniqueArticles, AVAILABILITY_BATCH_SIZE);
  const allAvailability = new Map();

  for (let i = 0; i < batches.length; i++) {
    const batch = batches[i];
    console.log(`    Batch ${i + 1}/${batches.length} (${batch.length} articles)...`);

    try {
      const availSoap = buildGetAvailabilitySOAP(batch);
      const availResponse = await soapRequest(availSoap);
      const batchAvailability = extractAvailability(availResponse);

      for (const [artNr, avail] of batchAvailability) {
        allAvailability.set(artNr, avail);
      }
      console.log(`      -> Got ${batchAvailability.size} results`);
    } catch (err) {
      console.error(`      -> Batch ${i + 1} failed: ${err.message}`);
      // Mark failed batch articles as unknown (0)
      for (const artNr of batch) {
        if (!allAvailability.has(artNr)) {
          allAvailability.set(artNr, false);
        }
      }
    }

    // Small delay between batches to be polite
    if (i < batches.length - 1) {
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  // Step 3: Write CSV
  console.log(`[3/3] Writing ${OUTPUT_FILE}...`);

  const lines = ['"Kod";"Stav"'];
  // Sort alphabetically for consistency
  const sortedArticles = uniqueArticles.sort();

  let availableCount = 0;
  for (const artNr of sortedArticles) {
    const isAvailable = allAvailability.get(artNr) ? 1 : 0;
    if (isAvailable) availableCount++;
    lines.push(`"${artNr}";${isAvailable}`);
  }

  fs.writeFileSync(OUTPUT_FILE, lines.join('\n') + '\n', 'utf-8');

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`\nDone in ${elapsed}s!`);
  console.log(`  Total products: ${sortedArticles.length}`);
  console.log(`  Available: ${availableCount}`);
  console.log(`  Unavailable: ${sortedArticles.length - availableCount}`);
  console.log(`  Output: ${OUTPUT_FILE}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
