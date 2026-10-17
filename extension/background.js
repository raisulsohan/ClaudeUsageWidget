// Claude Usage Widget — Chrome extension (Manifest V3 module service worker).
//
// Runs inside Chrome and uses your live claude.ai login (credentials: "include"),
// so no cookie file is ever read. The actual work lives in usage.js, which the
// popup also imports — so "Refresh now" never depends on this worker being awake.

import { fetchAndPost } from "./usage.js";

chrome.runtime.onInstalled.addListener(fetchAndPost);
chrome.runtime.onStartup.addListener(fetchAndPost);

// every 5 minutes
chrome.alarms.create("fetch-usage", { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "fetch-usage") fetchAndPost(); });
