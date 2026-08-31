// SELECTORS — edit only this object when YouTube changes its markup.
// New layout (2025): ytd-rich-item-renderer now wraps yt-lockup-view-model instead of ytd-video-renderer.
const SELECTORS = {
  // Tried in order; first selector that returns results wins
  videoItemCandidates: [
    'ytd-rich-item-renderer',
    'ytd-grid-video-renderer',
    'ytd-video-renderer',
  ],

  shortsItem: 'ytd-reel-item-renderer',

  channelLink: [
    // yt-lockup-view-model layout (2025+)
    'a.ytAttributedStringLink[href^="/@"]',
    'a.ytAttributedStringLink[href^="/channel/"]',
    'a.ytAttributedStringLink',
    // Legacy ytd-video-renderer layout
    'ytd-channel-name yt-formatted-string a',
    'ytd-channel-name a',
    '#channel-info a[href]',
    '#channel-name a',
    'a[href*="/@"]',
  ],

  videoLink: [
    // yt-lockup-view-model layout (2025+)
    'a.ytLockupMetadataViewModelTitle',
    // Legacy ytd-video-renderer layout
    'a#video-title-link',
    'a#video-title',
    'h3 a[href*="watch?v="]',
    'a[href*="/watch?v="]',
  ],

  thumbnail: [
    // yt-lockup-view-model layout (2025+) — src is always empty (lazy), so this is just a fallback
    'yt-thumbnail-view-model img',
    // Legacy
    'ytd-thumbnail a#thumbnail img',
    'ytd-thumbnail img',
    'img[src*="ytimg.com"]',
  ],
};

function query(el, selectorList) {
  for (const sel of selectorList) {
    const found = el.querySelector(sel);
    if (found) return found;
  }
  return null;
}

function extractVideoId(url) {
  try {
    return new URL(url, 'https://www.youtube.com').searchParams.get('v') || null;
  } catch {
    return null;
  }
}

function extractPublishedTime(item) {
  // yt-lockup-view-model layout (2025+)
  const meta = item.querySelector('yt-content-metadata-view-model');
  if (meta) {
    const texts = Array.from(meta.querySelectorAll('span'))
      .map(s => s.textContent.trim())
      .filter(Boolean);
    // texts looks like ["Channel", "Channel", "46K views", "•", "6 days ago"]
    // Prefer a span that looks like a relative time
    const timeSpan = texts.find(t => /\d+\s*(second|minute|hour|day|week|month|year|sec|min|hr)s?\s+ago/i.test(t));
    if (timeSpan) return timeSpan;
    // Fallback: item right after the bullet separator
    const dotIdx = texts.findIndex(t => t === '•' || t === '·');
    if (dotIdx >= 0 && dotIdx < texts.length - 1) return texts[dotIdx + 1];
    // Last resort: last non-bullet text
    const last = [...texts].reverse().find(t => t !== '•' && t !== '·');
    if (last) return last;
  }

  // Legacy ytd-video-renderer layout
  const spans = item.querySelectorAll('#metadata-line span.inline-metadata-item');
  const candidates = spans.length > 0
    ? Array.from(spans)
    : Array.from(item.querySelectorAll('#metadata-line span'));
  for (let i = candidates.length - 1; i >= 0; i--) {
    const text = candidates[i].textContent.trim();
    if (text && text !== '·') return text;
  }
  return '';
}

function getVideoItems() {
  for (const sel of SELECTORS.videoItemCandidates) {
    const items = document.querySelectorAll(sel);
    if (items.length > 0) return { items, selector: sel };
  }
  return { items: [], selector: null };
}

function scrapeWithStats() {
  const { items, selector: selectorUsed } = getVideoItems();

  // Snapshot of every candidate selector count — useful for diagnosing layout changes
  const pageItems = {};
  for (const sel of SELECTORS.videoItemCandidates) {
    pageItems[sel] = document.querySelectorAll(sel).length;
  }

  const stats = {
    selectorUsed,
    itemsTotal: items.length,
    itemsShorts: 0,
    itemsMissingSelectors: 0,
    itemsMissingData: 0,
    extracted: 0,
    pageItems,
  };

  if (items.length === 0) {
    console.warn('[mysub] No video items found. Selector counts:', pageItems);
    console.warn('[mysub] URL:', location.href, '| ytd-app:', !!document.querySelector('ytd-app'));
    return { videos: [], stats };
  }

  const seenChannels = new Set();
  const videos = [];

  for (const item of items) {
    try {
      if (item.querySelector(SELECTORS.shortsItem)) {
        stats.itemsShorts++;
        continue;
      }

      const channelEl = query(item, SELECTORS.channelLink);
      const videoLinkEl = query(item, SELECTORS.videoLink);

      if (!channelEl || !videoLinkEl) {
        stats.itemsMissingSelectors++;
        // Log the first few failures so selector issues are easy to spot in DevTools
        if (stats.itemsMissingSelectors <= 2) {
          console.warn(`[mysub] Item #${stats.itemsMissingSelectors}: missing channelEl=${!channelEl} videoLinkEl=${!videoLinkEl}`);
          console.warn('[mysub] innerHTML snippet:', item.innerHTML.substring(0, 600));
        }
        continue;
      }

      const channelUrl = channelEl.href;
      const channelName = channelEl.textContent.trim();
      const videoUrl = videoLinkEl.href;
      const videoId = extractVideoId(videoUrl);
      // New lockup: title is textContent of the link itself; old renderer used a title="" attribute
      const titleEl = videoLinkEl.querySelector('yt-formatted-string') || videoLinkEl;
      const videoTitle = (videoLinkEl.getAttribute('title') || titleEl.textContent || videoLinkEl.textContent || '').trim();

      if (!channelUrl || !videoUrl || !videoId || !videoTitle) {
        stats.itemsMissingData++;
        continue;
      }

      if (seenChannels.has(channelUrl)) continue;
      seenChannels.add(channelUrl);

      const thumbEl = query(item, SELECTORS.thumbnail);
      const rawSrc = thumbEl?.src || '';
      const thumbnailUrl = rawSrc && !rawSrc.startsWith('data:')
        ? rawSrc
        : `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;

      videos.push({
        channelName, channelUrl, videoTitle, videoUrl, videoId,
        thumbnailUrl, publishedTime: extractPublishedTime(item),
      });
      stats.extracted++;
    } catch (e) {
      console.warn('[mysub] Error parsing item:', e);
    }
  }

  console.log(
    `[mysub] Scrape complete | selector: ${selectorUsed} | total: ${stats.itemsTotal}` +
    ` | extracted: ${stats.extracted} | shorts: ${stats.itemsShorts}` +
    ` | missingSel: ${stats.itemsMissingSelectors} | missingData: ${stats.itemsMissingData}`
  );
  return { videos, stats };
}

// Auto-scrape on page load: send to background, which merges into storage
async function runScrapeAndStore() {
  const { videos, stats } = scrapeWithStats();
  if (videos.length === 0) return;
  try {
    await chrome.runtime.sendMessage({ type: 'SCRAPED_VIDEOS', videos, stats });
  } catch (e) {
    console.warn('[mysub] Failed to send to background:', e);
  }
}

function waitForFeed(callback, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  function check() {
    const found = SELECTORS.videoItemCandidates.some(s => document.querySelector(s));
    if (found) {
      callback();
    } else if (Date.now() < deadline) {
      setTimeout(check, 400);
    } else {
      console.warn('[mysub] Timed out waiting for feed. Counts:', {
        richItems: document.querySelectorAll('ytd-rich-item-renderer').length,
        videoRenderers: document.querySelectorAll('ytd-video-renderer').length,
        gridRenderers: document.querySelectorAll('ytd-grid-video-renderer').length,
      });
    }
  }
  setTimeout(check, 800);
}

// Guard against double-registration when background re-injects this file after an extension reload.
// The isolated-world `window` is fresh each injection, so this flag reliably prevents duplicate listeners.
if (!window.__mysub_loaded) {
  window.__mysub_loaded = true;

  // DO_SCRAPE: return videos+stats directly so background can store before responding to popup
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === 'DO_SCRAPE') {
      const { videos, stats } = scrapeWithStats();
      sendResponse({ ok: true, videos, stats });
    }
  });

  waitForFeed(runScrapeAndStore);
}
