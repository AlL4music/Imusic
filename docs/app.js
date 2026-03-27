// Feed Import Manager - GitHub Pages App
// Manages supplier feed configs stored in AlL4music/Imusic repo

const REPO_OWNER = 'AlL4music';
const REPO_NAME = 'Imusic';
const FEEDS_PATH = 'feeds';
const API_BASE = 'https://api.github.com';

// State
let token = localStorage.getItem('gh_token') || '';
let feeds = [];
let csvFiles = [];
let currentView = 'list'; // list | edit
let currentFeed = null;
let currentFeedSha = null; // for GitHub API updates
let csvPreviewData = null;

// ============ GitHub API ============

function ghHeaders() {
  const h = { 'Accept': 'application/vnd.github.v3+json' };
  if (token) h['Authorization'] = 'token ' + token;
  return h;
}

async function ghGet(path) {
  const res = await fetch(`${API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
    headers: ghHeaders()
  });
  if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);
  return res.json();
}

async function ghPut(path, content, sha, message) {
  const body = {
    message: message || `Update ${path}`,
    content: btoa(unescape(encodeURIComponent(content)))
  };
  if (sha) body.sha = sha;

  const res = await fetch(`${API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
    method: 'PUT',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.message || `GitHub API error: ${res.status}`);
  }
  return res.json();
}

async function ghDelete(path, sha, message) {
  const res = await fetch(`${API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
    method: 'DELETE',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message || `Delete ${path}`,
      sha: sha
    })
  });
  if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);
  return res.json();
}

// ============ Data Loading ============

async function loadFeeds() {
  try {
    const contents = await ghGet(FEEDS_PATH);
    feeds = [];
    for (const file of contents) {
      if (file.name.endsWith('.json')) {
        const data = await ghGet(`${FEEDS_PATH}/${file.name}`);
        const decoded = JSON.parse(decodeURIComponent(escape(atob(data.content))));
        feeds.push({ ...decoded, _filename: file.name, _sha: data.sha });
      }
    }
    feeds.sort((a, b) => a.name.localeCompare(b.name));
    return feeds;
  } catch (e) {
    if (e.message.includes('404')) {
      feeds = [];
      return feeds;
    }
    throw e;
  }
}

async function loadCsvFiles() {
  try {
    const contents = await ghGet('');
    csvFiles = contents
      .filter(f => f.name.endsWith('_sklad.csv') || f.name.endsWith('.csv'))
      .map(f => ({
        name: f.name,
        url: f.download_url,
        size: f.size
      }));
    return csvFiles;
  } catch (e) {
    csvFiles = [];
    return csvFiles;
  }
}

async function fetchCsvPreview(url, delimiter, maxRows, quoteChar) {
  maxRows = maxRows || 20;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch CSV: ${res.status}`);
  const text = await res.text();

  const parseConfig = {
    header: true,
    preview: maxRows,
    skipEmptyLines: true,
    complete: () => {}
  };

  // Delimiter: auto-detect or explicit
  if (delimiter && delimiter !== 'auto') {
    parseConfig.delimiter = delimiter;
  }
  // else PapaParse auto-detects

  // Quote character
  if (quoteChar === '') {
    parseConfig.quoteChar = '\0'; // effectively no quoting
  } else if (quoteChar) {
    parseConfig.quoteChar = quoteChar;
  }
  // else default double-quote

  return new Promise((resolve) => {
    parseConfig.complete = (results) => {
      resolve({
        headers: results.meta.fields || [],
        rows: results.data,
        totalRows: text.split('\n').length - 1,
        detectedDelimiter: results.meta.delimiter
      });
    };
    Papa.parse(text, parseConfig);
  });
}

// ============ Rendering ============

function $(sel) { return document.querySelector(sel); }

function render() {
  const app = $('#app');
  if (currentView === 'list') {
    renderFeedList(app);
  } else if (currentView === 'edit') {
    renderFeedEdit(app);
  }
}

function renderFeedList(container) {
  container.innerHTML = `
    <div class="loading"><div class="spinner"></div><p>Loading feeds...</p></div>
  `;

  Promise.all([loadFeeds(), loadCsvFiles()]).then(() => {
    let html = '<div class="feed-grid">';

    for (const feed of feeds) {
      const csvName = feed.csv_url ? feed.csv_url.split('/').pop() : 'N/A';
      html += `
        <div class="feed-card" data-feed="${feed._filename}">
          <span class="badge ${feed.enabled ? 'enabled' : 'disabled'}">${feed.enabled ? 'Enabled' : 'Disabled'}</span>
          <h3>${esc(feed.name)}</h3>
          <div class="feed-meta">
            <span>CSV: ${esc(csvName)}</span>
            <span>Match by: <strong>${esc(feed.match_by)}</strong></span>
            <span>Warehouse: #${feed.warehouse_id}</span>
            <span>Delimiter: "${esc(feed.delimiter)}"</span>
          </div>
        </div>
      `;
    }

    html += `
      <div class="add-card" id="btn-add-feed">+ Add New Feed</div>
    </div>`;

    container.innerHTML = html;

    // Events
    container.querySelectorAll('.feed-card').forEach(card => {
      card.addEventListener('click', () => {
        const filename = card.dataset.feed;
        currentFeed = feeds.find(f => f._filename === filename);
        currentFeedSha = currentFeed._sha;
        currentView = 'edit';
        render();
      });
    });

    $('#btn-add-feed').addEventListener('click', () => {
      currentFeed = {
        name: '',
        enabled: true,
        csv_url: '',
        delimiter: ';',
        columns: { sku: 'SKU', quantity: 'Pocet_ks' },
        match_by: 'old_shop_sku',
        warehouse_id: 2
      };
      currentFeedSha = null;
      currentView = 'edit';
      render();
    });
  }).catch(err => {
    container.innerHTML = `<div class="panel"><p style="color:red;">Error loading feeds: ${esc(err.message)}</p><p>Make sure your GitHub token is valid and has repo access.</p></div>`;
  });
}

function renderFeedEdit(container) {
  const f = currentFeed;
  const isNew = !currentFeedSha;

  // Build CSV file options
  let csvOptions = '<option value="">-- Enter URL or select --</option>';
  for (const csv of csvFiles) {
    const sel = f.csv_url && f.csv_url.includes(csv.name) ? 'selected' : '';
    csvOptions += `<option value="${esc(csv.url)}" ${sel}>${esc(csv.name)} (${formatSize(csv.size)})</option>`;
  }

  container.innerHTML = `
    <a class="back-link" id="btn-back">&larr; Back to feeds</a>
    <div class="panel">
      <div class="panel-header">
        <h2>${isNew ? 'Add New Feed' : 'Edit: ' + esc(f.name)}</h2>
        ${!isNew ? '<button class="btn btn-danger btn-sm" id="btn-delete">Delete Feed</button>' : ''}
      </div>

      <div class="form-row">
        <label>Feed Name</label>
        <input type="text" id="f-name" value="${esc(f.name)}" placeholder="e.g. 3DMX">
      </div>

      <div class="form-row">
        <label>Enabled</label>
        <div class="toggle-row">
          <label class="toggle">
            <input type="checkbox" id="f-enabled" ${f.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
          <span id="f-enabled-label">${f.enabled ? 'Active' : 'Inactive'}</span>
        </div>
      </div>

      <div class="form-row">
        <label>CSV Source</label>
        <select id="f-csv-select">${csvOptions}</select>
      </div>

      <div class="form-row">
        <label>CSV URL</label>
        <input type="text" id="f-csv-url" value="${esc(f.csv_url || '')}" placeholder="https://raw.githubusercontent.com/...">
      </div>

      <div class="form-row">
        <label>Delimiter</label>
        <select id="f-delimiter">
          <option value=";" ${f.delimiter === ';' ? 'selected' : ''}>Semicolon (;)</option>
          <option value="," ${f.delimiter === ',' ? 'selected' : ''}>Comma (,)</option>
          <option value="\t" ${f.delimiter === '\t' ? 'selected' : ''}>Tab (\\t)</option>
          <option value="|" ${f.delimiter === '|' ? 'selected' : ''}>Pipe (|)</option>
          <option value="auto" ${f.delimiter === 'auto' ? 'selected' : ''}>Auto-detect</option>
        </select>
      </div>

      <div class="form-row">
        <label>Quote Character <span class="label-hint">(how values are wrapped)</span></label>
        <select id="f-quotechar">
          <option value="&quot;" ${(f.quote_char || '"') === '"' ? 'selected' : ''}>Double quote (")</option>
          <option value="'" ${f.quote_char === "'" ? 'selected' : ''}>Single quote (')</option>
          <option value="" ${f.quote_char === '' ? 'selected' : ''}>None</option>
        </select>
      </div>

      <div class="form-row highlight-row">
        <label>Match By <span class="label-hint">(how to find products in new shop)</span></label>
        <select id="f-match">
          <option value="old_shop_sku" ${f.match_by === 'old_shop_sku' ? 'selected' : ''}>🔗 Via Old Shop SKU → Model (recommended for supplier feeds)</option>
          <option value="sku" ${f.match_by === 'sku' ? 'selected' : ''}>SKU — match directly by new shop SKU</option>
          <option value="model" ${f.match_by === 'model' ? 'selected' : ''}>Model — match directly by new shop Model</option>
          <option value="ean" ${f.match_by === 'ean' ? 'selected' : ''}>EAN — match directly by new shop EAN barcode</option>
        </select>
        <p class="field-help" id="match-help"></p>
      </div>

      <div class="form-row">
        <label id="lbl-col-sku">Identifier Column</label>
        <input type="text" id="f-col-sku" value="${esc(f.columns?.sku || 'SKU')}" placeholder="Column name in CSV">
      </div>

      <div class="form-row">
        <label>Quantity Column</label>
        <input type="text" id="f-col-qty" value="${esc(f.columns?.quantity || 'Pocet_ks')}" placeholder="Column name for quantity">
      </div>

      <div class="form-row">
        <label>Product Name Column <span class="label-hint">(optional — for Feed Prep dashboard)</span></label>
        <input type="text" id="f-col-name" value="${esc(f.columns?.name || '')}" placeholder="e.g. Nazov, ProductName, Popis">
      </div>

      <div class="form-row">
        <label>Brand Column <span class="label-hint">(optional — for brand filtering)</span></label>
        <input type="text" id="f-col-brand" value="${esc(f.columns?.brand || '')}" placeholder="e.g. marke, Značka, Brand">
      </div>

      <div class="form-row">
        <label>URL Column <span class="label-hint">(optional — source link)</span></label>
        <input type="text" id="f-col-url" value="${esc(f.columns?.url || '')}" placeholder="e.g. URL, ProductUrl">
      </div>

      <div class="form-row">
        <label>Warehouse ID</label>
        <select id="f-warehouse">
          <option value="1" ${f.warehouse_id == 1 ? 'selected' : ''}>1 - All4music predajňa (Skladom)</option>
          <option value="2" ${f.warehouse_id == 2 ? 'selected' : ''}>2 - Skladom u dodávateľa (4-7 dní)</option>
          <option value="3" ${f.warehouse_id == 3 ? 'selected' : ''}>3 - Pre-Order / Predobjednávka</option>
        </select>
      </div>

      <div class="btn-group">
        <button class="btn btn-primary" id="btn-save">Save Feed</button>
        <button class="btn btn-secondary" id="btn-preview">Preview CSV</button>
      </div>
    </div>

    <div id="csv-preview-container"></div>
  `;

  // Events
  $('#btn-back').addEventListener('click', () => { currentView = 'list'; render(); });

  $('#f-csv-select').addEventListener('change', (e) => {
    if (e.target.value) $('#f-csv-url').value = e.target.value;
  });

  $('#f-enabled').addEventListener('change', (e) => {
    $('#f-enabled-label').textContent = e.target.checked ? 'Active' : 'Inactive';
  });

  $('#btn-preview').addEventListener('click', previewCsv);
  $('#btn-save').addEventListener('click', saveFeed);
  $('#f-delimiter').addEventListener('change', () => { if ($('#f-csv-url').value) previewCsv(); });
  $('#f-quotechar').addEventListener('change', () => { if ($('#f-csv-url').value) previewCsv(); });

  // Match help text + dynamic label
  function updateMatchHelp() {
    const help = $('#match-help');
    const label = $('#lbl-col-sku');
    const val = $('#f-match').value;
    const hints = {
      'old_shop_sku': 'CSV column value → look up in old shop SKU → get model → find in new shop by model. Best for supplier feeds with numeric codes.',
      'sku': 'CSV column value is matched directly against oc_product.sku in the new shop.',
      'model': 'CSV column value is matched directly against oc_product.model in the new shop.',
      'ean': 'CSV column value is matched directly against oc_product.ean in the new shop.'
    };
    const labels = {
      'old_shop_sku': 'SKU Column (old shop code)',
      'sku': 'SKU Column',
      'model': 'Model Column',
      'ean': 'EAN Column'
    };
    help.textContent = hints[val] || '';
    label.textContent = labels[val] || 'Identifier Column';
  }
  $('#f-match').addEventListener('change', updateMatchHelp);
  updateMatchHelp();

  if (!isNew) {
    $('#btn-delete').addEventListener('click', deleteFeed);
  }

  // Auto-preview if we have a URL
  if (f.csv_url) {
    setTimeout(previewCsv, 300);
  }
}

async function previewCsv() {
  const url = $('#f-csv-url').value.trim();
  const delimiter = $('#f-delimiter').value;
  const quoteChar = $('#f-quotechar').value;
  const container = $('#csv-preview-container');

  if (!url) {
    container.innerHTML = '<div class="panel"><p>Enter a CSV URL first.</p></div>';
    return;
  }

  container.innerHTML = '<div class="panel"><div class="loading"><div class="spinner"></div><p>Loading CSV...</p></div></div>';

  try {
    csvPreviewData = await fetchCsvPreview(url, delimiter, 20, quoteChar);
    const skuCol = $('#f-col-sku').value;
    const qtyCol = $('#f-col-qty').value;
    const nameCol = $('#f-col-name').value;
    const brandCol = $('#f-col-brand').value;
    const urlCol = $('#f-col-url').value;

    const matchVal = $('#f-match').value;
    const matchLabels = { 'old_shop_sku': 'Identifier', 'sku': 'SKU', 'model': 'Model', 'ean': 'EAN' };
    const idLabel = matchLabels[matchVal] || 'Identifier';

    // Show detected delimiter if auto
    const delimNote = delimiter === 'auto' && csvPreviewData.detectedDelimiter
      ? ` — detected delimiter: "${esc(csvPreviewData.detectedDelimiter)}"`
      : '';

    let html = `<div class="panel">
      <h2>CSV Preview <span style="font-size:14px;color:#999;">(${csvPreviewData.totalRows} rows total, showing first 20${delimNote})</span></h2>
      <p class="click-hint">💡 Click a column header to assign it as <strong>${esc(idLabel)}</strong>, <strong>Quantity</strong>, <strong>Name</strong>, <strong>Brand</strong>, or <strong>URL</strong></p>
      <div class="csv-preview"><table><thead><tr><th class="row-num">#</th>`;

    for (const h of csvPreviewData.headers) {
      let mappedAs = '';
      if (h === skuCol) mappedAs = idLabel;
      else if (h === qtyCol) mappedAs = 'Qty';
      else if (h === nameCol) mappedAs = 'Name';
      else if (h === brandCol) mappedAs = 'Brand';
      else if (h === urlCol) mappedAs = 'URL';
      const isMapped = mappedAs !== '';
      html += `<th class="${isMapped ? 'mapped' : 'clickable-col'}" data-col="${esc(h)}">${esc(h)}${isMapped ? ' ✓ ' + mappedAs : ''}</th>`;
    }
    html += '</tr></thead><tbody>';

    csvPreviewData.rows.forEach((row, i) => {
      html += `<tr><td class="row-num">${i + 1}</td>`;
      for (const h of csvPreviewData.headers) {
        html += `<td>${esc(row[h] || '')}</td>`;
      }
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';
    container.innerHTML = html;

    // Click column headers to assign
    container.querySelectorAll('th[data-col]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        const current = [];
        if ($('#f-col-sku').value === col) current.push(idLabel);
        if ($('#f-col-qty').value === col) current.push('Qty');
        if ($('#f-col-name').value === col) current.push('Name');
        if ($('#f-col-brand').value === col) current.push('Brand');
        if ($('#f-col-url').value === col) current.push('URL');

        const choice = prompt(
          'Assign column "' + col + '" as:\n' +
          '1 = ' + idLabel + ' column\n' +
          '2 = Quantity column\n' +
          '3 = Product Name column\n' +
          '4 = Brand column\n' +
          '5 = URL column\n' +
          '0 = Clear assignment\n' +
          (current.length ? '(Currently: ' + current.join(', ') + ')' : ''),
          current.length ? '' : '1'
        );
        if (choice === '1') { $('#f-col-sku').value = col; toast('"' + col + '" → ' + idLabel, 'success'); }
        else if (choice === '2') { $('#f-col-qty').value = col; toast('"' + col + '" → Quantity', 'success'); }
        else if (choice === '3') { $('#f-col-name').value = col; toast('"' + col + '" → Name', 'success'); }
        else if (choice === '4') { $('#f-col-brand').value = col; toast('"' + col + '" → Brand', 'success'); }
        else if (choice === '5') { $('#f-col-url').value = col; toast('"' + col + '" → URL', 'success'); }
        else if (choice === '0') {
          // Clear any assignment matching this column
          if ($('#f-col-sku').value === col) $('#f-col-sku').value = '';
          if ($('#f-col-qty').value === col) $('#f-col-qty').value = '';
          if ($('#f-col-name').value === col) $('#f-col-name').value = '';
          if ($('#f-col-brand').value === col) $('#f-col-brand').value = '';
          if ($('#f-col-url').value === col) $('#f-col-url').value = '';
          toast('"' + col + '" cleared', 'success');
        }
        if (choice) previewCsv(); // refresh to update highlights
      });
    });

    // Auto-fill column names if they're in the CSV
    if (csvPreviewData.headers.length > 0) {
      const headers = csvPreviewData.headers;
      // Suggest column names if current values don't match
      if (!headers.includes($('#f-col-sku').value)) {
        const skuGuess = headers.find(h => h.toLowerCase().includes('sku') || h.toLowerCase().includes('code') || h.toLowerCase() === 'id');
        if (skuGuess) $('#f-col-sku').value = skuGuess;
      }
      if (!headers.includes($('#f-col-qty').value)) {
        const qtyGuess = headers.find(h => h.toLowerCase().includes('pocet') || h.toLowerCase().includes('qty') || h.toLowerCase().includes('quantity') || h.toLowerCase().includes('stock') || h.toLowerCase().includes('available'));
        if (qtyGuess) $('#f-col-qty').value = qtyGuess;
      }
      if (!$('#f-col-name').value && !headers.includes($('#f-col-name').value)) {
        const nameGuess = headers.find(h => h.toLowerCase().includes('nazov') || h.toLowerCase().includes('productname') || h.toLowerCase().includes('name') || h.toLowerCase().includes('popis'));
        if (nameGuess) $('#f-col-name').value = nameGuess;
      }
      if (!$('#f-col-brand').value && !headers.includes($('#f-col-brand').value)) {
        const brandGuess = headers.find(h => h.toLowerCase().includes('brand') || h.toLowerCase().includes('marke') || h.toLowerCase().includes('značka') || h.toLowerCase().includes('manufacturer'));
        if (brandGuess) $('#f-col-brand').value = brandGuess;
      }
      if (!$('#f-col-url').value && !headers.includes($('#f-col-url').value)) {
        const urlGuess = headers.find(h => h.toLowerCase().includes('url') || h.toLowerCase().includes('link'));
        if (urlGuess) $('#f-col-url').value = urlGuess;
      }
    }
  } catch (err) {
    container.innerHTML = `<div class="panel"><p style="color:red;">Error loading CSV: ${esc(err.message)}</p></div>`;
  }
}

async function saveFeed() {
  const name = $('#f-name').value.trim();
  if (!name) { toast('Please enter a feed name', 'error'); return; }

  const columns = {
    sku: $('#f-col-sku').value.trim(),
    quantity: $('#f-col-qty').value.trim()
  };
  // Only include optional columns if they have a value
  const nameCol = $('#f-col-name').value.trim();
  const brandCol = $('#f-col-brand').value.trim();
  const urlCol = $('#f-col-url').value.trim();
  if (nameCol) columns.name = nameCol;
  if (brandCol) columns.brand = brandCol;
  if (urlCol) columns.url = urlCol;

  const feedData = {
    name: name,
    enabled: $('#f-enabled').checked,
    csv_url: $('#f-csv-url').value.trim(),
    delimiter: $('#f-delimiter').value,
    columns: columns,
    match_by: $('#f-match').value,
    warehouse_id: parseInt($('#f-warehouse').value)
  };

  // Only include quote_char if not default (double quote)
  const quoteChar = $('#f-quotechar').value;
  if (quoteChar !== '"') {
    feedData.quote_char = quoteChar;
  }

  const filename = name.toLowerCase().replace(/[^a-z0-9]/g, '_') + '.json';
  const path = `${FEEDS_PATH}/${filename}`;
  const content = JSON.stringify(feedData, null, 2) + '\n';

  try {
    // If renaming (new filename different from old), delete old file
    if (currentFeedSha && currentFeed._filename && currentFeed._filename !== filename) {
      await ghDelete(`${FEEDS_PATH}/${currentFeed._filename}`, currentFeedSha, `Rename feed: ${currentFeed._filename} -> ${filename}`);
      currentFeedSha = null;
    }

    const result = await ghPut(path, content, currentFeedSha, `${currentFeedSha ? 'Update' : 'Add'} feed: ${name}`);
    currentFeedSha = result.content.sha;
    currentFeed = { ...feedData, _filename: filename, _sha: currentFeedSha };
    toast('Feed saved successfully!', 'success');
  } catch (err) {
    toast('Error saving: ' + err.message, 'error');
  }
}

async function deleteFeed() {
  if (!confirm(`Delete feed "${currentFeed.name}"? This cannot be undone.`)) return;

  try {
    await ghDelete(`${FEEDS_PATH}/${currentFeed._filename}`, currentFeedSha, `Delete feed: ${currentFeed.name}`);
    toast('Feed deleted', 'success');
    currentView = 'list';
    render();
  } catch (err) {
    toast('Error deleting: ' + err.message, 'error');
  }
}

// ============ Auth ============

function initAuth() {
  const input = $('#token-input');
  const status = $('#auth-status');

  input.value = token ? '••••••••' + token.slice(-4) : '';

  input.addEventListener('change', async () => {
    const val = input.value.trim();
    if (val.startsWith('••••')) return; // masked, ignore

    token = val;
    localStorage.setItem('gh_token', token);

    try {
      const res = await fetch(`${API_BASE}/user`, { headers: ghHeaders() });
      if (res.ok) {
        const user = await res.json();
        status.className = 'status ok';
        status.textContent = user.login;
        render();
      } else {
        status.className = 'status err';
        status.textContent = 'Invalid token';
      }
    } catch (e) {
      status.className = 'status err';
      status.textContent = 'Error';
    }
  });

  // Check existing token
  if (token) {
    status.textContent = 'Checking...';
    fetch(`${API_BASE}/user`, { headers: ghHeaders() }).then(async res => {
      if (res.ok) {
        const user = await res.json();
        status.className = 'status ok';
        status.textContent = user.login;
      } else {
        status.className = 'status err';
        status.textContent = 'Token expired';
      }
    }).catch(() => {
      status.className = 'status err';
      status.textContent = 'Error';
    });
  }
}

// ============ Helpers ============

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function toast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast ${type || 'success'}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ============ SEO Dashboard ============

let seoReport = null;

async function loadSeoReport() {
  try {
    const data = await ghGet('reports/seo_report.json');
    seoReport = JSON.parse(decodeURIComponent(escape(atob(data.content))));
    return seoReport;
  } catch (e) {
    seoReport = null;
    return null;
  }
}

function renderSeo(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading SEO report...</p></div>';

  loadSeoReport().then(report => {
    if (!report) {
      container.innerHTML = `<div class="panel">
        <h2>SEO Health Dashboard</h2>
        <p>No SEO report found yet. Run the SEO Health Check workflow from GitHub Actions, or wait for it to run automatically.</p>
      </div>`;
      return;
    }

    const s = report.summary;
    let html = `
      <div class="panel">
        <h2>SEO Health Dashboard</h2>
        <p class="seo-timestamp">Last check: ${new Date(report.timestamp).toLocaleString()} | Site: ${esc(report.site_url)}</p>

        <div class="seo-summary">
          <div class="seo-stat errors"><div class="num">${s.errors}</div><div class="label">Errors</div></div>
          <div class="seo-stat warnings"><div class="num">${s.warnings}</div><div class="label">Warnings</div></div>
          <div class="seo-stat info"><div class="num">${s.info}</div><div class="label">Info</div></div>
        </div>
      </div>`;

    // Global checks
    for (const [name, section] of Object.entries(report.global_checks || {})) {
      if (section.issues && section.issues.length > 0) {
        html += `<div class="panel"><div class="seo-section">
          <div class="seo-section-title">${esc(name.replace(/_/g, ' ').toUpperCase())}</div>`;

        // Show relevant info
        if (section.info) {
          html += '<dl class="seo-meta-grid">';
          for (const [k, v] of Object.entries(section.info)) {
            if (v !== null && v !== undefined && k !== 'content') {
              const display = typeof v === 'object' ? JSON.stringify(v) : String(v);
              html += `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd>${esc(display.slice(0, 200))}</dd>`;
            }
          }
          html += '</dl>';
        }

        for (const issue of section.issues) {
          const icon = {error: 'X', warning: '!', info: 'i'}[issue.severity];
          html += `<div class="seo-issue ${issue.severity}">
            <span class="icon">${icon}</span>
            <span>${esc(issue.msg)}</span>
          </div>`;
        }
        html += '</div></div>';
      }
    }

    // Per-page checks
    for (const page of report.pages || []) {
      html += `<div class="panel"><div class="seo-section">
        <div class="seo-section-title">PAGE: ${esc(page.url)}</div>`;

      if (page.checks) {
        // Show key meta info
        const meta = page.checks.meta_tags;
        if (meta) {
          html += '<dl class="seo-meta-grid">';
          if (meta.title) html += `<dt>Title</dt><dd>${esc(meta.title)}</dd>`;
          if (meta.meta_description) html += `<dt>Description</dt><dd>${esc(meta.meta_description)}</dd>`;
          if (meta.html_lang) html += `<dt>Language</dt><dd>${esc(meta.html_lang)}</dd>`;
          if (meta.canonical) html += `<dt>Canonical</dt><dd>${esc(meta.canonical)}</dd>`;
          html += '</dl>';
        }

        const hreflang = page.checks.hreflang;
        if (hreflang && hreflang.hreflang_tags && hreflang.hreflang_tags.length > 0) {
          html += '<dl class="seo-meta-grid">';
          for (const tag of hreflang.hreflang_tags) {
            html += `<dt>hreflang="${esc(tag.lang)}"</dt><dd>${esc(tag.href)}</dd>`;
          }
          html += '</dl>';
        }
      }

      if (page.issues && page.issues.length > 0) {
        for (const issue of page.issues) {
          const icon = {error: 'X', warning: '!', info: 'i'}[issue.severity];
          html += `<div class="seo-issue ${issue.severity}">
            <span class="icon">${icon}</span>
            <span>${esc(issue.msg)}</span>
          </div>`;
        }
      } else {
        html += '<p style="color:#2abb67;font-weight:600;">All checks passed!</p>';
      }

      html += '</div></div>';
    }

    container.innerHTML = html;
  });
}

// ============ Product Audit Dashboard ============

let productAudit = null;
let auditFilters = { search: '', manufacturer: '', issue: '', status: 'all', sort: 'score_asc' };
let auditPage = 0;
const AUDIT_PAGE_SIZE = 50;

async function loadProductAudit() {
  if (productAudit) return productAudit;
  try {
    // Try direct GitHub Pages URL first (faster, no base64)
    const directUrl = `https://all4music.github.io/Imusic/reports/product_audit.json?_=${Date.now()}`;
    const res = await fetch(directUrl);
    if (res.ok) {
      productAudit = await res.json();
      return productAudit;
    }
  } catch (e) { /* fallback */ }
  try {
    const data = await ghGet('reports/product_audit.json');
    productAudit = JSON.parse(decodeURIComponent(escape(atob(data.content))));
    return productAudit;
  } catch (e) {
    productAudit = null;
    return null;
  }
}

function getFilteredProducts(report) {
  let products = report.products || [];

  // Status filter
  if (auditFilters.status === 'done') {
    products = products.filter(p => (p.i || []).length === 0);
  } else if (auditFilters.status === 'todo') {
    products = products.filter(p => (p.i || []).length > 0);
  }

  // Manufacturer filter
  if (auditFilters.manufacturer) {
    products = products.filter(p => p.b === auditFilters.manufacturer);
  }

  // Issue filter
  if (auditFilters.issue) {
    products = products.filter(p => (p.i || []).includes(auditFilters.issue));
  }

  // Text search
  if (auditFilters.search) {
    const q = auditFilters.search.toLowerCase();
    products = products.filter(p =>
      (p.n || '').toLowerCase().includes(q) ||
      (p.m || '').toLowerCase().includes(q) ||
      String(p.id).includes(q)
    );
  }

  // Sort
  const [sortKey, sortDir] = auditFilters.sort.split('_');
  const dir = sortDir === 'desc' ? -1 : 1;
  products.sort((a, b) => {
    if (sortKey === 'score') return (a.s - b.s) * dir;
    if (sortKey === 'name') return (a.n || '').localeCompare(b.n || '') * dir;
    if (sortKey === 'brand') return (a.b || '').localeCompare(b.b || '') * dir;
    if (sortKey === 'id') return (a.id - b.id) * dir;
    return 0;
  });

  return products;
}

function renderProducts(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading product audit...</p></div>';

  loadProductAudit().then(report => {
    if (!report) {
      container.innerHTML = `<div class="panel">
        <h2>Product Completeness</h2>
        <p>No product audit found yet. Run the product-audit script locally.</p>
      </div>`;
      return;
    }
    renderProductsDashboard(container, report);
  });
}

function renderProductsDashboard(container, report) {
  const total = report.total_products;
  const done = report.complete_count;
  const todo = report.incomplete_count;
  const pct = report.completeness_pct;

  // Get filtered products
  const filtered = getFilteredProducts(report);
  const pageCount = Math.ceil(filtered.length / AUDIT_PAGE_SIZE);
  if (auditPage >= pageCount) auditPage = Math.max(0, pageCount - 1);
  const pageProducts = filtered.slice(auditPage * AUDIT_PAGE_SIZE, (auditPage + 1) * AUDIT_PAGE_SIZE);

  // Filtered stats
  const filteredDone = filtered.filter(p => (p.i || []).length === 0).length;
  const filteredTodo = filtered.length - filteredDone;
  const filteredPct = filtered.length > 0 ? Math.round(filteredDone / filtered.length * 1000) / 10 : 0;
  const isFiltered = auditFilters.search || auditFilters.manufacturer || auditFilters.issue || auditFilters.status !== 'all';

  // Build manufacturers list for dropdown
  const manufacturers = (report.by_manufacturer || []).map(m => m.name).sort();

  // Issue labels
  const issueLabels = {
    no_name: 'Missing name', no_description: 'Missing description', short_description: 'Short description',
    no_meta_title: 'Missing meta title', no_meta_description: 'Missing meta desc',
    no_seo_url: 'Missing SEO URL', no_image: 'Missing image', no_manufacturer: 'No brand',
    no_price: 'No price', no_model: 'Missing model',
    brand_all_caps: 'Brand ALL CAPS in name', model_not_in_name: 'Model code missing from name'
  };
  const issueShort = {
    no_name: 'Name', no_description: 'Desc', short_description: 'Short desc',
    no_meta_title: 'Meta title', no_meta_description: 'Meta desc',
    no_seo_url: 'SEO URL', no_image: 'Image', no_manufacturer: 'Brand',
    no_price: 'Price', no_model: 'Model',
    brand_all_caps: 'ALL CAPS', model_not_in_name: 'Model missing'
  };

  let html = `
    <div class="panel">
      <h2>Product Completeness</h2>
      <p class="seo-timestamp">Last audit: ${new Date(report.timestamp).toLocaleString()} | ${total.toLocaleString()} enabled products</p>

      <div class="seo-summary">
        <div class="seo-stat" style="border-color:#2abb67"><div class="num" style="color:#2abb67">${done.toLocaleString()}</div><div class="label">Done</div></div>
        <div class="seo-stat" style="border-color:#e67e22"><div class="num" style="color:#e67e22">${todo.toLocaleString()}</div><div class="label">Needs Work</div></div>
        <div class="seo-stat" style="border-color:#3498db"><div class="num" style="color:#3498db">${pct}%</div><div class="label">Complete</div></div>
      </div>

      <div style="background:#eee;border-radius:8px;height:24px;margin:16px 0;overflow:hidden">
        <div style="background:linear-gradient(90deg,#2abb67,#27ae60);height:100%;width:${pct}%;transition:width .5s;border-radius:8px"></div>
      </div>
    </div>`;

  // Issue breakdown (clickable)
  html += `<div class="panel"><h3>Issue Breakdown <span style="font-weight:400;font-size:13px;color:#888">— click to filter</span></h3><table class="audit-table"><thead><tr><th>Issue</th><th>Count</th><th>% of Products</th><th></th></tr></thead><tbody>`;
  const issueOrder = ['no_description','short_description','no_image','no_seo_url','no_meta_title','no_meta_description','no_manufacturer','no_price','no_model','no_name','brand_all_caps','model_not_in_name','no_category','no_extra_images'];
  for (const key of issueOrder) {
    const issue = (report.issue_summary || {})[key];
    if (!issue || issue.count === 0) continue;
    const ipct = Math.round(issue.count / total * 100);
    const isExtra = key === 'no_category' || key === 'no_extra_images' || key === 'brand_all_caps' || key === 'model_not_in_name';
    const isActive = auditFilters.issue === key;
    html += `<tr class="issue-row${isActive ? ' active-filter' : ''}${isExtra ? '' : ' clickable-issue'}" data-issue="${key}"${isExtra ? ' style="opacity:.5"' : ''}>
      <td>${esc(issue.label)}${isActive ? ' <span class="filter-badge">filtered</span>' : ''}</td>
      <td style="text-align:right;font-weight:600">${issue.count.toLocaleString()}</td>
      <td style="text-align:right">${ipct}%</td>
      <td style="width:200px"><div style="background:#eee;border-radius:4px;height:12px;overflow:hidden"><div style="background:${isExtra ? '#bbb' : '#e74c3c'};height:100%;width:${ipct}%"></div></div></td>
    </tr>`;
  }
  html += '</tbody></table></div>';

  // By manufacturer (clickable)
  if (report.by_manufacturer && report.by_manufacturer.length > 0) {
    html += `<div class="panel"><h3>By Manufacturer <span style="font-weight:400;font-size:13px;color:#888">— click to filter</span></h3><table class="audit-table"><thead><tr><th>Brand</th><th>Total</th><th>Done</th><th>Needs Work</th><th>%</th><th></th></tr></thead><tbody>`;
    for (const m of report.by_manufacturer) {
      const barColor = m.pct >= 80 ? '#2abb67' : m.pct >= 50 ? '#e67e22' : '#e74c3c';
      const isActive = auditFilters.manufacturer === m.name;
      html += `<tr class="mfr-row${isActive ? ' active-filter' : ''}" data-mfr="${esc(m.name)}">
        <td style="font-weight:600">${esc(m.name)}${isActive ? ' <span class="filter-badge">filtered</span>' : ''}</td>
        <td style="text-align:right">${m.total}</td>
        <td style="text-align:right;color:#2abb67">${m.complete}</td>
        <td style="text-align:right;color:#e74c3c">${m.incomplete}</td>
        <td style="text-align:right;font-weight:600">${m.pct}%</td>
        <td style="width:150px"><div style="background:#eee;border-radius:4px;height:12px;overflow:hidden"><div style="background:${barColor};height:100%;width:${m.pct}%"></div></div></td>
      </tr>`;
    }
    html += '</tbody></table></div>';
  }

  // Filter toolbar + product list
  html += `<div class="panel" id="product-list-panel">
    <h3>Products ${isFiltered ? '<span style="color:#e67e22;font-weight:400;font-size:14px">— filtered</span>' : ''}</h3>

    <div class="filter-toolbar">
      <div class="filter-group">
        <input type="text" id="audit-search" class="filter-input" placeholder="Search name, model or ID..." value="${esc(auditFilters.search)}">
      </div>
      <div class="filter-group">
        <select id="audit-mfr" class="filter-select">
          <option value="">All brands</option>
          ${manufacturers.map(m => `<option value="${esc(m)}"${auditFilters.manufacturer === m ? ' selected' : ''}>${esc(m)}</option>`).join('')}
        </select>
      </div>
      <div class="filter-group">
        <select id="audit-issue" class="filter-select">
          <option value="">All issues</option>
          ${Object.entries(issueLabels).map(([k, v]) => `<option value="${k}"${auditFilters.issue === k ? ' selected' : ''}>${v}</option>`).join('')}
        </select>
      </div>
      <div class="filter-group">
        <select id="audit-status" class="filter-select">
          <option value="all"${auditFilters.status === 'all' ? ' selected' : ''}>All status</option>
          <option value="todo"${auditFilters.status === 'todo' ? ' selected' : ''}>Needs Work</option>
          <option value="done"${auditFilters.status === 'done' ? ' selected' : ''}>Done</option>
        </select>
      </div>
      <div class="filter-group">
        <select id="audit-sort" class="filter-select">
          <option value="score_asc"${auditFilters.sort === 'score_asc' ? ' selected' : ''}>Score: Low first</option>
          <option value="score_desc"${auditFilters.sort === 'score_desc' ? ' selected' : ''}>Score: High first</option>
          <option value="name_asc"${auditFilters.sort === 'name_asc' ? ' selected' : ''}>Name: A-Z</option>
          <option value="name_desc"${auditFilters.sort === 'name_desc' ? ' selected' : ''}>Name: Z-A</option>
          <option value="brand_asc"${auditFilters.sort === 'brand_asc' ? ' selected' : ''}>Brand: A-Z</option>
          <option value="id_asc"${auditFilters.sort === 'id_asc' ? ' selected' : ''}>ID: Low first</option>
          <option value="id_desc"${auditFilters.sort === 'id_desc' ? ' selected' : ''}>ID: High first</option>
        </select>
      </div>
      ${isFiltered ? '<button class="btn btn-sm btn-clear-filters" id="audit-clear">Clear filters</button>' : ''}
    </div>

    <div class="filter-stats">
      Showing <strong>${filtered.length.toLocaleString()}</strong> products
      ${isFiltered ? ` (of ${total.toLocaleString()})` : ''}
      — <span style="color:#2abb67">${filteredDone.toLocaleString()} done</span>,
      <span style="color:#e74c3c">${filteredTodo.toLocaleString()} needs work</span>
      (${filteredPct}% complete)
    </div>`;

  // Products table
  html += `<table class="audit-table product-table"><thead><tr>
    <th style="width:60px">ID</th>
    <th>Name</th>
    <th style="width:100px">Model</th>
    <th style="width:120px">Brand</th>
    <th style="width:60px">Score</th>
    <th>Missing</th>
    <th style="width:60px">Status</th>
  </tr></thead><tbody>`;

  if (pageProducts.length === 0) {
    html += '<tr><td colspan="7" style="text-align:center;padding:24px;color:#999">No products match your filters</td></tr>';
  }

  for (const p of pageProducts) {
    const issues = p.i || [];
    const isDone = issues.length === 0;
    const scoreColor = p.s >= 100 ? '#2abb67' : p.s >= 80 ? '#2abb67' : p.s >= 50 ? '#e67e22' : '#e74c3c';
    const missing = issues.map(i => issueShort[i] || i);
    const extras = p.x || [];
    const nameCell = p.sug
      ? `<div title="${esc(p.n)}">${esc(p.n)}</div><div class="suggested-name" title="Suggested: ${esc(p.sug)}">→ ${esc(p.sug)}</div>`
      : `<div title="${esc(p.n)}">${esc(p.n)}</div>`;
    html += `<tr class="${isDone ? 'row-done' : 'row-todo'}">
      <td><a href="https://all4.rentit.sk/admin/index.php?route=catalog/product/edit&product_id=${p.id}" target="_blank" class="product-link">${p.id}</a></td>
      <td class="cell-name">${nameCell}</td>
      <td class="cell-model" title="${esc(p.m)}">${esc(p.m)}</td>
      <td>${esc(p.b)}</td>
      <td style="font-weight:700;color:${scoreColor}">${p.s}%</td>
      <td>${isDone ? '' : missing.map(m => `<span class="issue-tag">${esc(m)}</span>`).join(' ')}${extras.length ? extras.map(e => `<span class="issue-tag extra-tag">${esc(issueShort[e] || e)}</span>`).join(' ') : ''}</td>
      <td>${isDone ? '<span class="status-done">Done</span>' : '<span class="status-todo">Todo</span>'}</td>
    </tr>`;
  }

  html += '</tbody></table>';

  // Pagination
  if (pageCount > 1) {
    html += '<div class="pagination">';
    if (auditPage > 0) {
      html += `<button class="btn btn-sm btn-secondary page-btn" data-page="0">First</button>`;
      html += `<button class="btn btn-sm btn-secondary page-btn" data-page="${auditPage - 1}">&laquo; Prev</button>`;
    }
    // Show page numbers around current
    const startPage = Math.max(0, auditPage - 3);
    const endPage = Math.min(pageCount - 1, auditPage + 3);
    for (let i = startPage; i <= endPage; i++) {
      html += `<button class="btn btn-sm ${i === auditPage ? 'btn-primary' : 'btn-secondary'} page-btn" data-page="${i}">${i + 1}</button>`;
    }
    if (auditPage < pageCount - 1) {
      html += `<button class="btn btn-sm btn-secondary page-btn" data-page="${auditPage + 1}">Next &raquo;</button>`;
      html += `<button class="btn btn-sm btn-secondary page-btn" data-page="${pageCount - 1}">Last</button>`;
    }
    html += `<span class="page-info">Page ${auditPage + 1} of ${pageCount}</span>`;
    html += '</div>';
  }

  html += '</div>'; // close panel

  container.innerHTML = html;

  // ---- Event bindings ----

  // Search (debounced)
  let searchTimer;
  const searchInput = document.getElementById('audit-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        auditFilters.search = searchInput.value.trim();
        auditPage = 0;
        renderProductsDashboard(container, report);
      }, 300);
    });
    // Keep focus on search after re-render
    if (auditFilters.search) {
      searchInput.focus();
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }
  }

  // Dropdowns
  const bindSelect = (id, key) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => {
      auditFilters[key] = el.value;
      auditPage = 0;
      renderProductsDashboard(container, report);
    });
  };
  bindSelect('audit-mfr', 'manufacturer');
  bindSelect('audit-issue', 'issue');
  bindSelect('audit-status', 'status');
  bindSelect('audit-sort', 'sort');

  // Clear filters
  const clearBtn = document.getElementById('audit-clear');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      auditFilters = { search: '', manufacturer: '', issue: '', status: 'all', sort: 'score_asc' };
      auditPage = 0;
      renderProductsDashboard(container, report);
    });
  }

  // Clickable manufacturer rows
  container.querySelectorAll('.mfr-row').forEach(row => {
    row.addEventListener('click', () => {
      const mfr = row.dataset.mfr;
      if (auditFilters.manufacturer === mfr) {
        auditFilters.manufacturer = '';
      } else {
        auditFilters.manufacturer = mfr;
      }
      auditPage = 0;
      renderProductsDashboard(container, report);
      // Scroll to product list
      setTimeout(() => {
        const panel = document.getElementById('product-list-panel');
        if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    });
  });

  // Clickable issue rows
  container.querySelectorAll('.clickable-issue').forEach(row => {
    row.addEventListener('click', () => {
      const issue = row.dataset.issue;
      if (auditFilters.issue === issue) {
        auditFilters.issue = '';
      } else {
        auditFilters.issue = issue;
        auditFilters.status = 'todo'; // issues only apply to incomplete products
      }
      auditPage = 0;
      renderProductsDashboard(container, report);
      setTimeout(() => {
        const panel = document.getElementById('product-list-panel');
        if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    });
  });

  // Pagination
  container.querySelectorAll('.page-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      auditPage = parseInt(btn.dataset.page);
      renderProductsDashboard(container, report);
      // Scroll to top of product table
      setTimeout(() => {
        const panel = document.getElementById('product-list-panel');
        if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    });
  });
}

// ============ Init ============

let activeTab = 'feeds'; // feeds | seo | products

document.addEventListener('DOMContentLoaded', () => {
  initAuth();
  render();

  // Tab navigation
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeTab = btn.dataset.view;
      if (activeTab === 'seo') {
        renderSeo($('#app'));
      } else if (activeTab === 'products') {
        renderProducts($('#app'));
      } else {
        currentView = 'list';
        render();
      }
    });
  });
});
