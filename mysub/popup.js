const DEFAULT_THRESHOLD_HOURS = 24;

let statusMap = {};

const DL_LABELS = { in_queue: 'in queue', downloading: 'downloading', downloaded: 'downloaded' };
const UP_LABELS = { in_queue: 'in queue', uploading: 'uploading', uploaded: 'uploaded' };

async function init() {
  const { channels = {}, lastUpdated, lastScrapeStats, newThresholdHours = DEFAULT_THRESHOLD_HOURS, downloadBatch = {} } =
    await chrome.storage.local.get(['channels', 'lastUpdated', 'lastScrapeStats', 'newThresholdHours', 'downloadBatch']);

  setLastUpdated(lastUpdated);
  renderList(channels, newThresholdHours);
  renderDownloads(downloadBatch, {});   // placeholder chips; fetchStatus will refresh them
  setStatusFromStats(lastScrapeStats, Object.keys(channels).length);
  initSettings(newThresholdHours);
  fetchStatus();
  setInterval(fetchStatus, 15000);

  document.getElementById('refresh-btn').addEventListener('click', handleRefresh);
  document.getElementById('subs-link').addEventListener('click', () => {
    chrome.tabs.create({ url: 'https://www.youtube.com/feed/subscriptions' });
  });

  // Show extension ID for install.sh setup
  const extIdEl = document.getElementById('ext-id');
  extIdEl.textContent = chrome.runtime.id;
  extIdEl.addEventListener('click', async () => {
    await navigator.clipboard.writeText(chrome.runtime.id);
    extIdEl.textContent = 'copied!';
    setTimeout(() => { extIdEl.textContent = chrome.runtime.id; }, 1500);
  });
}

function initSettings(savedHours) {
  const sel = document.getElementById('threshold-select');
  sel.value = String(savedHours);
  if (!sel.value) sel.value = String(DEFAULT_THRESHOLD_HOURS); // fallback if stored value isn't an option

  sel.addEventListener('change', async () => {
    const hours = Number(sel.value);
    await chrome.storage.local.set({ newThresholdHours: hours });
    const { channels = {} } = await chrome.storage.local.get('channels');
    renderList(channels, hours);
  });

  document.getElementById('clear-btn').addEventListener('click', async () => {
    await chrome.storage.local.remove(['channels', 'lastUpdated', 'lastScrapeStats', 'downloadedIds', 'downloadLock']);
    renderList({}, Number(sel.value));
    setLastUpdated(null);
    setStatus('Data cleared');
  });
}

function setLastUpdated(ts) {
  const el = document.getElementById('last-updated');
  if (!ts) { el.textContent = 'Never synced'; return; }
  const mins = Math.floor((Date.now() - ts) / 60000);
  if (mins < 1)    el.textContent = 'Updated just now';
  else if (mins < 60)   el.textContent = `Updated ${mins}m ago`;
  else if (mins < 1440) el.textContent = `Updated ${Math.floor(mins / 60)}h ago`;
  else              el.textContent = `Updated ${Math.floor(mins / 1440)}d ago`;
}

function setStatus(text, isError = false) {
  const el = document.getElementById('status-line');
  el.textContent = text;
  el.className = isError ? 'error' : '';
}

function setStatusFromStats(stats, storedCount) {
  if (!stats) {
    if (storedCount > 0) setStatus(`${storedCount} channels stored`);
    return;
  }
  if (stats.itemsTotal === 0) {
    setStatus(
      `Last sync: no video items found — selector "${stats.selectorUsed ?? 'none matched'}" returned 0`,
      true
    );
    return;
  }
  const parts = [`scraped ${stats.extracted} · stored ${storedCount}`];
  if (stats.itemsShorts > 0)            parts.push(`${stats.itemsShorts} Shorts skipped`);
  if (stats.itemsMissingSelectors > 0)  parts.push(`${stats.itemsMissingSelectors} missing selectors`);
  if (stats.itemsMissingData > 0)       parts.push(`${stats.itemsMissingData} missing data`);
  const hasStorageMismatch = stats.extracted > 0 && storedCount === 0;
  setStatus(parts.join(' · '), hasStorageMismatch);
}

function renderList(channels, thresholdHours = DEFAULT_THRESHOLD_HOURS) {
  const list = document.getElementById('video-list');
  const empty = document.getElementById('empty-state');
  const entries = Object.values(channels);

  if (entries.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  list.style.display = 'block';
  empty.style.display = 'none';
  list.innerHTML = '';

  entries.sort((a, b) => b.firstSeen - a.firstSeen);

  const thresholdMs = thresholdHours * 60 * 60 * 1000;
  const now = Date.now();
  for (const entry of entries) {
    list.appendChild(buildCard(entry, now - entry.firstSeen < thresholdMs));
  }
  applyStatuses(statusMap);
}

async function fetchStatus() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'GET_STATUS' });
    if (!response?.ok) return;
    statusMap = response.statuses;
    applyStatuses(statusMap);
    await syncDownloadBatch(response.statuses, response.titles ?? {});
  } catch (e) {
    // silent — status chips are best-effort
  }
}

// Seed downloadBatch from titles returned by get_status, prune uploaded entries, re-render section.
async function syncDownloadBatch(statuses, titles) {
  const { downloadBatch = {} } = await chrome.storage.local.get('downloadBatch');
  let changed = false;

  // Seed entries for any active video we have a filename-derived title for.
  for (const [videoId, title] of Object.entries(titles)) {
    if (!downloadBatch[videoId]) {
      downloadBatch[videoId] = {
        videoId,
        videoTitle: title,
        channelName: '',
        thumbnailUrl: `https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`,
        videoUrl: `https://www.youtube.com/watch?v=${videoId}`,
        channelUrl: '',
        firstSeen: 0,
        publishedTime: '',
      };
      changed = true;
    }
  }

  // Remove entries that have finished uploading.
  for (const [videoId, state] of Object.entries(statuses)) {
    if (state.up === 'uploaded' && downloadBatch[videoId]) {
      delete downloadBatch[videoId];
      changed = true;
    }
  }

  if (changed) await chrome.storage.local.set({ downloadBatch });
  renderDownloads(downloadBatch, statuses);
}

function renderDownloads(batch, statuses) {
  const section = document.getElementById('downloads-section');
  // Only show videos that have an active status (not in the main channel list)
  const channelCards = new Set(
    Array.from(document.querySelectorAll('.status-row[data-video-id]')).map(r => r.dataset.videoId)
  );
  const active = Object.entries(batch).filter(([id]) => {
    const s = statuses[id];
    return s && s.up !== 'uploaded' && !channelCards.has(id);
  });

  if (active.length === 0) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  const list = document.getElementById('downloads-list');
  list.innerHTML = '';
  for (const [videoId, entry] of active) {
    const state = statuses[videoId];
    list.appendChild(buildDownloadCard(entry, state));
  }
}

function buildDownloadCard(entry, state) {
  const card = document.createElement('div');
  card.className = 'video-card dl-card';

  const thumb = document.createElement('img');
  thumb.className = 'thumbnail';
  thumb.alt = '';
  thumb.src = entry.thumbnailUrl ?? '';
  thumb.onerror = () => { thumb.style.opacity = '0.3'; };

  const info = document.createElement('div');
  info.className = 'info';

  const channelEl = document.createElement('div');
  channelEl.className = 'channel-name';
  channelEl.textContent = entry.channelName ?? '';

  const titleEl = document.createElement('div');
  titleEl.className = 'video-title';
  titleEl.textContent = entry.videoTitle ?? '';

  const chipRow = document.createElement('div');
  chipRow.className = 'status-row';
  chipRow.dataset.videoId = entry.videoId;

  const showDl = state.dl && state.up !== 'uploaded';
  if (showDl) chipRow.appendChild(makeStatusChip(DL_LABELS[state.dl] ?? state.dl, `chip-dl-${state.dl}`));
  if (state.up) chipRow.appendChild(makeStatusChip(UP_LABELS[state.up] ?? state.up, `chip-up-${state.up}`));

  info.append(channelEl, titleEl, chipRow);
  card.append(thumb, info);
  card.addEventListener('click', () => chrome.tabs.create({ url: entry.videoUrl }));
  return card;
}

function applyStatuses(map) {
  for (const [videoId, state] of Object.entries(map)) {
    const row = document.querySelector(`.status-row[data-video-id="${CSS.escape(videoId)}"]`);
    if (!row) continue;
    row.innerHTML = '';

    const showDl = state.dl && state.up !== 'uploaded';
    if (showDl) {
      row.appendChild(makeStatusChip(DL_LABELS[state.dl] ?? state.dl, `chip-dl-${state.dl}`));
    }
    if (state.up) {
      row.appendChild(makeStatusChip(UP_LABELS[state.up] ?? state.up, `chip-up-${state.up}`));
    }
  }
}

function makeStatusChip(text, cls) {
  const chip = document.createElement('span');
  chip.className = `status-chip ${cls}`;
  chip.textContent = text;
  return chip;
}

function buildCard(entry, isNew) {
  const card = document.createElement('div');
  card.className = 'video-card';
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.setAttribute('aria-label', `${entry.channelName}: ${entry.videoTitle}`);

  const thumb = document.createElement('img');
  thumb.className = 'thumbnail';
  thumb.alt = '';
  // lazy loading doesn't fire in extension popups — use eager
  thumb.src = entry.thumbnailUrl;
  thumb.onerror = () => { thumb.style.opacity = '0.3'; };

  const info = document.createElement('div');
  info.className = 'info';

  const channelEl = document.createElement('div');
  channelEl.className = 'channel-name';
  channelEl.textContent = entry.channelName;

  const titleEl = document.createElement('div');
  titleEl.className = 'video-title';
  titleEl.textContent = entry.videoTitle;

  const meta = document.createElement('div');
  meta.className = 'meta';
  if (entry.publishedTime) {
    const time = document.createElement('span');
    time.className = 'time';
    time.textContent = entry.publishedTime;
    meta.appendChild(time);
  }
  if (isNew) {
    const badge = document.createElement('span');
    badge.className = 'badge-new';
    badge.textContent = 'NEW';
    meta.appendChild(badge);
  }

  const dlBtn = document.createElement('button');
  dlBtn.className = 'dl-btn';
  dlBtn.textContent = '↓';
  dlBtn.title = 'Download with yt-dlp';
  dlBtn.addEventListener('click', e => {
    e.stopPropagation();
    handleDownload(entry, dlBtn);
  });

  const txBtn = document.createElement('button');
  txBtn.className = 'tx-btn';
  txBtn.textContent = 'T';
  txBtn.title = 'Download transcript';
  txBtn.addEventListener('click', e => {
    e.stopPropagation();
    handleTranscript(entry, txBtn);
  });

  const statusRow = document.createElement('div');
  statusRow.className = 'status-row';
  if (entry.videoId) statusRow.dataset.videoId = entry.videoId;

  info.append(channelEl, titleEl, statusRow, meta);
  card.append(thumb, info, txBtn, dlBtn);

  function open() { chrome.tabs.create({ url: entry.videoUrl }); }
  card.addEventListener('click', open);
  card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') open(); });

  return card;
}

async function handleDownload(entry, btn) {
  btn.disabled = true;
  btn.textContent = '…';

  const response = await chrome.runtime.sendMessage({
    type: 'DOWNLOAD_VIDEO',
    videoUrl: entry.videoUrl,
  });

  if (response?.status === 'started') {
    btn.textContent = '✓';
    btn.title = `Downloading to ~/Downloads/MySub`;
    btn.classList.add('dl-done');
  } else {
    btn.textContent = '✗';
    btn.disabled = false;
    const err = response?.error ?? 'unknown error';
    const notInstalled = err.toLowerCase().includes('not found') || err.toLowerCase().includes('cannot find');
    btn.title = notInstalled
      ? `Native host not installed. Run: ./native/install.sh ${chrome.runtime.id}`
      : `Error: ${err}`;
    btn.classList.add('dl-error');
  }
}

async function handleTranscript(entry, btn) {
  btn.disabled = true;
  btn.textContent = '…';

  const response = await chrome.runtime.sendMessage({
    type: 'DOWNLOAD_TRANSCRIPT',
    videoUrl: entry.videoUrl,
  });

  if (response?.status === 'started') {
    btn.textContent = '✓';
    btn.title = 'Transcript queued — will upload to R2 automatically';
    btn.classList.add('tx-done');
  } else {
    btn.textContent = '✗';
    btn.disabled = false;
    btn.title = `Error: ${response?.error ?? 'unknown error'}`;
    btn.classList.add('tx-error');
  }
}

async function handleRefresh() {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  btn.textContent = 'Refreshing…';
  setStatus('Refreshing…');

  const response = await chrome.runtime.sendMessage({ type: 'REFRESH_REQUEST' });

  if (response?.ok) {
    // Storage is already written by background before it responded — no race condition
    const { channels = {}, lastUpdated, newThresholdHours = DEFAULT_THRESHOLD_HOURS } =
      await chrome.storage.local.get(['channels', 'lastUpdated', 'newThresholdHours']);
    renderList(channels, newThresholdHours);
    setLastUpdated(lastUpdated);
    // response.totalChannels = what background read back from storage after writing
    // Object.keys(channels).length  = what popup reads from storage now
    // If these differ there is a storage sync issue
    setStatusFromStats(response.stats, response.totalChannels ?? Object.keys(channels).length);
    if (response.downloadStatus === 'started') {
      showToast(`Queued ${response.downloadQueued} video${response.downloadQueued === 1 ? '' : 's'} for download`);
    } else if (response.downloadStatus === 'nothing') {
      showToast('No new videos to download');
    } else if (response.downloadStatus === 'already_running') {
      showToast('Download already running');
    }
  } else if (response?.reason === 'contentScriptError') {
    setStatus(`Content script error: ${response.error ?? 'unknown'}`, true);
  } else {
    setStatus(`Refresh failed: ${response?.error ?? response?.reason ?? 'unknown error'}`, true);
  }

  btn.disabled = false;
  btn.textContent = 'Refresh';
}

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), 3200);
}

document.addEventListener('DOMContentLoaded', init);
