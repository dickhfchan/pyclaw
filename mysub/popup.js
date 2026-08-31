const NEW_THRESHOLD_MS = 24 * 60 * 60 * 1000;

async function init() {
  const { channels = {}, lastUpdated, lastScrapeStats } =
    await chrome.storage.local.get(['channels', 'lastUpdated', 'lastScrapeStats']);

  setLastUpdated(lastUpdated);
  renderList(channels);
  setStatusFromStats(lastScrapeStats, Object.keys(channels).length);

  document.getElementById('refresh-btn').addEventListener('click', handleRefresh);
  document.getElementById('subs-link').addEventListener('click', () => {
    chrome.tabs.create({ url: 'https://www.youtube.com/feed/subscriptions' });
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
  const parts = [`${stats.extracted} channels extracted from ${stats.itemsTotal} items`];
  if (stats.itemsShorts > 0)            parts.push(`${stats.itemsShorts} Shorts skipped`);
  if (stats.itemsMissingSelectors > 0)  parts.push(`${stats.itemsMissingSelectors} missing selectors`);
  if (stats.itemsMissingData > 0)       parts.push(`${stats.itemsMissingData} missing data`);
  setStatus(parts.join(' · '));
}

function renderList(channels) {
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

  const now = Date.now();
  for (const entry of entries) {
    list.appendChild(buildCard(entry, now - entry.firstSeen < NEW_THRESHOLD_MS));
  }
}

function buildCard(entry, isNew) {
  const card = document.createElement('div');
  card.className = 'video-card';
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.setAttribute('aria-label', `${entry.channelName}: ${entry.videoTitle}`);

  const thumb = document.createElement('img');
  thumb.className = 'thumbnail';
  thumb.src = entry.thumbnailUrl;
  thumb.alt = '';
  thumb.loading = 'lazy';

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

  info.append(channelEl, titleEl, meta);
  card.append(thumb, info);

  function open() { chrome.tabs.create({ url: entry.videoUrl }); }
  card.addEventListener('click', open);
  card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') open(); });

  return card;
}

async function handleRefresh() {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  btn.textContent = 'Refreshing…';
  setStatus('Looking for subscriptions tab…');

  const response = await chrome.runtime.sendMessage({ type: 'REFRESH_REQUEST' });

  if (response?.ok) {
    // Storage is already written by background before it responded — no race condition
    const { channels = {}, lastUpdated } = await chrome.storage.local.get(['channels', 'lastUpdated']);
    renderList(channels);
    setLastUpdated(lastUpdated);
    setStatusFromStats(response.stats, Object.keys(channels).length);
  } else if (response?.reason === 'noTab') {
    setStatus('No subscriptions tab open — visit youtube.com/feed/subscriptions first', true);
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
