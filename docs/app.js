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

async function fetchCsvPreview(url, delimiter, maxRows) {
  maxRows = maxRows || 20;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch CSV: ${res.status}`);
  const text = await res.text();

  return new Promise((resolve) => {
    Papa.parse(text, {
      delimiter: delimiter || ';',
      header: true,
      preview: maxRows,
      skipEmptyLines: true,
      complete: (results) => {
        resolve({
          headers: results.meta.fields || [],
          rows: results.data,
          totalRows: text.split('\n').length - 1
        });
      }
    });
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
          <option value="\t" ${f.delimiter === '\t' ? 'selected' : ''}>Tab</option>
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
  const container = $('#csv-preview-container');

  if (!url) {
    container.innerHTML = '<div class="panel"><p>Enter a CSV URL first.</p></div>';
    return;
  }

  container.innerHTML = '<div class="panel"><div class="loading"><div class="spinner"></div><p>Loading CSV...</p></div></div>';

  try {
    csvPreviewData = await fetchCsvPreview(url, delimiter, 20);
    const skuCol = $('#f-col-sku').value;
    const qtyCol = $('#f-col-qty').value;

    const matchVal = $('#f-match').value;
    const matchLabels = { 'old_shop_sku': 'Identifier', 'sku': 'SKU', 'model': 'Model', 'ean': 'EAN' };
    const idLabel = matchLabels[matchVal] || 'Identifier';

    let html = `<div class="panel">
      <h2>CSV Preview <span style="font-size:14px;color:#999;">(${csvPreviewData.totalRows} rows total, showing first 20)</span></h2>
      <p class="click-hint">💡 Click a column header to assign it as <strong>${esc(idLabel)}</strong> or <strong>Quantity</strong></p>
      <div class="csv-preview"><table><thead><tr><th class="row-num">#</th>`;

    for (const h of csvPreviewData.headers) {
      let mappedAs = '';
      if (h === skuCol) mappedAs = idLabel;
      else if (h === qtyCol) mappedAs = 'Qty';
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

        const choice = prompt(
          'Assign column "' + col + '" as:\\n' +
          '1 = ' + idLabel + ' column\\n' +
          '2 = Quantity column\\n' +
          (current.length ? '(Currently: ' + current.join(', ') + ')' : ''),
          '1'
        );
        if (choice === '1') { $('#f-col-sku').value = col; toast('"' + col + '" → ' + idLabel, 'success'); }
        else if (choice === '2') { $('#f-col-qty').value = col; toast('"' + col + '" → Quantity', 'success'); }
        if (choice) previewCsv(); // refresh to update highlights
      });
    });

    // Auto-fill column names if they're in the CSV
    if (csvPreviewData.headers.length > 0) {
      const headers = csvPreviewData.headers;
      // Suggest column names if current values don't match
      if (!headers.includes($('#f-col-sku').value)) {
        const skuGuess = headers.find(h => h.toLowerCase().includes('sku') || h.toLowerCase().includes('code'));
        if (skuGuess) $('#f-col-sku').value = skuGuess;
      }
      if (!headers.includes($('#f-col-qty').value)) {
        const qtyGuess = headers.find(h => h.toLowerCase().includes('pocet') || h.toLowerCase().includes('qty') || h.toLowerCase().includes('quantity') || h.toLowerCase().includes('stock'));
        if (qtyGuess) $('#f-col-qty').value = qtyGuess;
      }
    }
  } catch (err) {
    container.innerHTML = `<div class="panel"><p style="color:red;">Error loading CSV: ${esc(err.message)}</p></div>`;
  }
}

async function saveFeed() {
  const name = $('#f-name').value.trim();
  if (!name) { toast('Please enter a feed name', 'error'); return; }

  const feedData = {
    name: name,
    enabled: $('#f-enabled').checked,
    csv_url: $('#f-csv-url').value.trim(),
    delimiter: $('#f-delimiter').value,
    columns: {
      sku: $('#f-col-sku').value.trim(),
      quantity: $('#f-col-qty').value.trim()
    },
    match_by: $('#f-match').value,
    warehouse_id: parseInt($('#f-warehouse').value)
  };

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

// ============ Init ============

document.addEventListener('DOMContentLoaded', () => {
  initAuth();
  render();
});
