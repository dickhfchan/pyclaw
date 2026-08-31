# MySub — YouTube Subscriptions Tracker

A Chrome extension (Manifest V3) that shows you the **latest video from each of your subscribed channels** in one clean popup — no Shorts, no recommendations, no noise.

## What it does

- Scrapes `youtube.com/feed/subscriptions` while you're logged in
- Stores one "latest video" record per channel locally
- Popup shows all channels sorted newest-first, with a **NEW** badge for recent videos
- Clicking any entry opens the video in a new tab (normal YouTube playback, ads included)

## Install (load unpacked)

1. Clone or download this repo
2. Open Chrome → `chrome://extensions`
3. Enable **Developer mode** (toggle, top-right)
4. Click **Load unpacked** → select the `mysub/` folder
5. The MySub icon appears in your toolbar

## Usage

1. Log into YouTube as normal
2. Navigate to `youtube.com/feed/subscriptions` — the extension scrapes automatically
3. Click the MySub toolbar icon to open the popup
4. Use **Refresh** to re-scrape the currently open subscriptions tab
5. Adjust the **NEW badge** threshold (12h / 24h / 48h / 7 days) at the bottom
6. **Clear data** removes all stored channel records

## Notes

- **Data is stored locally only** — no servers, no external requests, metadata only (titles, URLs, thumbnails)
- **Only refreshes when you visit the subscriptions page** — Chrome extensions can't silently scrape an authenticated session in the background
- **DOM selectors may break** when YouTube updates its frontend. If the status bar shows `0 channels extracted`, open the `SELECTORS` object at the top of `content.js` and update the selectors to match the current markup

## Permissions

| Permission | Why |
|---|---|
| `storage` | Store channel/video data locally |
| `tabs` | Find the open subscriptions tab to refresh it |
| `scripting` | Re-inject the content script if the extension is reloaded while the tab stays open |
| `https://www.youtube.com/*` | Read the subscriptions feed DOM |
