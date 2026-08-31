const NATIVE_HOST = 'com.mysub.downloader';

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'DOWNLOAD_VIDEO') {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST,
      { action: 'download', url: message.videoUrl },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({ status: 'error', error: chrome.runtime.lastError.message });
        } else {
          sendResponse(response ?? { status: 'error', error: 'no response from host' });
        }
      }
    );
    return true; // keep channel open for async callback
  }

  if (message.type === 'SCRAPED_VIDEOS') {
    mergeIntoStorage(message.videos, message.stats)
      .then(newCount => sendResponse({ ok: true, newCount }))
      .catch(e => sendResponse({ ok: false, error: e.message }));
    return true;
  }

  if (message.type === 'REFRESH_REQUEST') {
    handleRefreshRequest()
      .then(sendResponse)
      .catch(e => sendResponse({ ok: false, error: e.message }));
    return true;
  }
});

async function mergeIntoStorage(videos, stats) {
  const { channels = {} } = await chrome.storage.local.get('channels');
  const now = Date.now();
  let newCount = 0;

  for (const video of videos) {
    const existing = channels[video.channelUrl];
    if (!existing || existing.videoId !== video.videoId) {
      channels[video.channelUrl] = { ...video, firstSeen: now };
      newCount++;
    }
    // Same videoId: leave firstSeen untouched so "new" badge ages naturally
  }

  const update = { channels, lastUpdated: now };
  if (stats) update.lastScrapeStats = stats;
  await chrome.storage.local.set(update);
  return newCount;
}

async function handleRefreshRequest() {
  const tabs = await chrome.tabs.query({
    url: 'https://www.youtube.com/feed/subscriptions*',
  });

  if (tabs.length === 0) return { ok: false, reason: 'noTab' };

  const tabId = tabs[0].id;

  // First attempt
  let scrapeResult = await trySendMessage(tabId);

  if (!scrapeResult) {
    // Content script not reachable — extension was likely reloaded while the tab stayed open,
    // destroying the old isolated-world context. Re-inject content.js and retry once.
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['content.js'],
        world: 'ISOLATED',
      });
      await new Promise(r => setTimeout(r, 800));
      scrapeResult = await trySendMessage(tabId);
    } catch (injectErr) {
      return { ok: false, reason: 'contentScriptError', error: injectErr.message };
    }
  }

  if (!scrapeResult?.ok) return scrapeResult ?? { ok: false, reason: 'noResponse' };

  // Merge synchronously before responding — popup can read storage immediately after
  const newCount = await mergeIntoStorage(scrapeResult.videos || [], scrapeResult.stats);
  const { channels = {} } = await chrome.storage.local.get('channels');

  return {
    ok: true,
    newCount,
    totalChannels: Object.keys(channels).length,
    stats: scrapeResult.stats,
  };
}

async function trySendMessage(tabId) {
  try {
    return await chrome.tabs.sendMessage(tabId, { type: 'DO_SCRAPE' });
  } catch {
    return null;
  }
}
