// background.js

const API_ENDPOINT = "http://127.0.0.1:5001/api/analyze";
const pendingRequests = new Set();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "TRIGGER_AUDIT") {
    const payload = message.payload;
    const cacheKey = `audit_${payload.domain}_${payload.title.slice(0, 30)}`;

    // Avoid duplicate simultaneous requests
    if (pendingRequests.has(cacheKey)) {
      return true;
    }

    pendingRequests.add(cacheKey);

    fetch(API_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
        return res.json();
      })
      .then((data) => {
        pendingRequests.delete(cacheKey);
        chrome.storage.local.set({
          [`audit_${payload.domain}`]: { status: "COMPLETED", data: data, timestamp: Date.now() }
        });

        if (sender.tab && sender.tab.id) {
          const score = data.risk_score;
          const color = score >= 70 ? "#c0392b" : score >= 40 ? "#d98c1f" : "#1a9d5c";
          chrome.action.setBadgeText({ tabId: sender.tab.id, text: String(score) });
          chrome.action.setBadgeBackgroundColor({ tabId: sender.tab.id, color: color });
        }
      })
      .catch((err) => {
        pendingRequests.delete(cacheKey);
        chrome.storage.local.set({
          [`audit_${payload.domain}`]: { status: "FAILED", error: err.message }
        });
      });
  }
  return true;
});