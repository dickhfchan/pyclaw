const NATIVE_HOST = 'com.mysub.downloader';
const AUTO_REFRESH_ALARM = 'mysub-auto-refresh';
const AUTO_REFRESH_MINUTES = 60;

// Open the side panel when the extension icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

// Schedule periodic auto-refresh on install and browser startup
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(AUTO_REFRESH_ALARM, {
    delayInMinutes: AUTO_REFRESH_MINUTES,
    periodInMinutes: AUTO_REFRESH_MINUTES,
  });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.get(AUTO_REFRESH_ALARM, alarm => {
    if (!alarm) {
      chrome.alarms.create(AUTO_REFRESH_ALARM, {
        delayInMinutes: AUTO_REFRESH_MINUTES,
        periodInMinutes: AUTO_REFRESH_MINUTES,
      });
    }
  });
});

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === AUTO_REFRESH_ALARM) {
    handleRefreshRequest().catch(() => {});
  }
});

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

  if (message.type === 'GET_STATUS') {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST,
      { action: 'get_status' },
      (response) => {
        if (chrome.runtime.lastError || !response || response.status === 'error' || !response.statuses) {
          sendResponse({ ok: false, error: chrome.runtime.lastError?.message ?? response?.error ?? 'no statuses' });
        } else {
          sendResponse({ ok: true, statuses: response.statuses, titles: response.titles ?? {} });
        }
      }
    );
    return true;
  }

  if (message.type === 'DOWNLOAD_TRANSCRIPT') {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST,
      { action: 'download_transcript', url: message.videoUrl },
      (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({ status: 'error', error: chrome.runtime.lastError.message });
        } else {
          sendResponse(response ?? { status: 'error', error: 'no response from host' });
        }
      }
    );
    return true;
  }

  if (message.type === 'SCRAPED_VIDEOS') {
    mergeIntoStorage(message.videos, message.stats)
      .then(newCount => {
        autoDownloadVideos(); // fire and forget
        sendResponse({ ok: true, newCount });
      })
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

let _downloadRunning = false;

async function autoDownloadVideos() {
  // In-memory guard for same service-worker-session concurrency
  if (_downloadRunning) return;

  // Storage-based debounce: survives service worker restarts (10s window)
  const { downloadLock = 0 } = await chrome.storage.local.get('downloadLock');
  if (Date.now() - downloadLock < 10000) return;
  await chrome.storage.local.set({ downloadLock: Date.now() });

  _downloadRunning = true;
  try {
    await _doAutoDownload();
  } finally {
    _downloadRunning = false;
    await chrome.storage.local.remove('downloadLock');
  }
}

// Returns { queued: N, status: 'started'|'already_running'|'nothing'|'error' }
async function _doAutoDownload() {
  const { channels = {}, downloadedIds = {} } = await chrome.storage.local.get(['channels', 'downloadedIds']);
  const allVideos = Object.values(channels).filter(v => v.videoId);
  const toDownload = allVideos.filter(v => !downloadedIds[v.videoId]);
  console.log('[mysub] _doAutoDownload: channels=%d allWithId=%d toDownload=%d downloadedIds=%d',
    Object.keys(channels).length, allVideos.length, toDownload.length, Object.keys(downloadedIds).length);
  console.log('[mysub] toDownload videoIds:', toDownload.map(v => v.videoId));
  if (toDownload.length === 0) return { queued: 0, status: 'nothing' };

  const response = await new Promise(resolve => {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST,
      {
        action: 'download_batch',
        urls: toDownload.map(v => v.videoUrl),
        videos: toDownload.map(v => ({
          url: v.videoUrl,
          channelName: v.channelName ?? '',
          channelUrl: v.channelUrl ?? '',
        })),
      },
      r => resolve(r ?? null)
    );
  });

  console.log('[mysub] download_batch response:', response);
  if (response?.status === 'started') {
    for (const video of toDownload) downloadedIds[video.videoId] = true;
    // Persist video entries so popup can show status chips even after a refresh replaces
    // these videos with newer ones in the channel list.
    const { downloadBatch = {} } = await chrome.storage.local.get('downloadBatch');
    for (const video of toDownload) downloadBatch[video.videoId] = video;
    await chrome.storage.local.set({ downloadedIds, downloadBatch });
    return { queued: toDownload.length, status: 'started' };
  }
  // 'already_running': leave downloadedIds untouched — retried next scrape
  return { queued: 0, status: response?.status ?? 'error' };
}


async function handleRefreshRequest() {
  const tabs = await chrome.tabs.query({
    url: 'https://www.youtube.com/feed/subscriptions*',
  });

  let tabId;
  if (tabs.length === 0) {
    const tab = await chrome.tabs.create({ url: 'https://www.youtube.com/feed/subscriptions' });
    tabId = tab.id;
    await waitForTabLoad(tabId);
    // Give YouTube's JS feed renderer time to populate the DOM
    await new Promise(r => setTimeout(r, 2500));
  } else {
    tabId = tabs[0].id;
  }

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
  // Await directly (not fire-and-forget): keeps the service worker alive and bypasses
  // the _downloadRunning guard that would block if SCRAPED_VIDEOS fired on the same session.
  // The native host's batch_running() check prevents duplicate yt-dlp spawning.
  const dlResult = await _doAutoDownload();
  const { channels = {} } = await chrome.storage.local.get('channels');

  return {
    ok: true,
    newCount,
    totalChannels: Object.keys(channels).length,
    stats: scrapeResult.stats,
    downloadQueued: dlResult.queued,
    downloadStatus: dlResult.status,
  };
}

async function trySendMessage(tabId) {
  try {
    return await chrome.tabs.sendMessage(tabId, { type: 'DO_SCRAPE' });
  } catch {
    return null;
  }
}

function waitForTabLoad(tabId) {
  return new Promise(resolve => {
    function listener(id, changeInfo) {
      if (id === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    // Resolve immediately if the tab is already complete
    chrome.tabs.get(tabId).then(tab => {
      if (tab.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }).catch(() => {});
  });
}
