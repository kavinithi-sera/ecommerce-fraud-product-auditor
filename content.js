function extractPrice(text) {
  const match = text.match(/[₹$]\s?([\d,]+(?:\.\d{1,2})?)/);
  if (!match) return 0;
  return parseFloat(match[1].replace(/,/g, ""));
}

function extractTitle() {
  const h1 = document.querySelector("h1");
  if (h1 && h1.innerText.trim().length > 5) return h1.innerText.trim();
  return document.title;
}

function extractReviews() {
  const nodes = document.querySelectorAll('[class*="review" i], [id*="review" i]');
  const seen = new Set();
  const reviews = [];
  nodes.forEach((el) => {
    const text = el.innerText.trim();
    if (text.length > 20 && text.length < 500 && !seen.has(text)) {
      seen.add(text);
      reviews.push(text);
    }
  });
  return reviews.slice(0, 15);
}

function harvestPageData() {
  const bodyText = document.body.innerText.slice(0, 6000);
  return {
    domain: window.location.hostname,
    title: extractTitle(),
    price: extractPrice(bodyText),
    textContent: bodyText,
    reviews: extractReviews(),
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getPageData") {
    sendResponse(harvestPageData());
  }
});