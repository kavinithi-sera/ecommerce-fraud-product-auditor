// content.js - Comprehensive Review Card & Multi-Selector Harvester

function parseNumber(text) {
  if (!text) return 0;
  const match = text.match(/(?:Rs\.?|INR|[₹$€£])\s*([\d,]+(?:\.\d{1,2})?)/i);
  if (match) {
    const num = parseFloat(match[1].replace(/,/g, ""));
    if (!isNaN(num)) return num;
  }
  const rawMatch = text.match(/([\d,]+(?:\.\d{1,2})?)/);
  if (!rawMatch) return 0;
  const rawNum = parseFloat(rawMatch[1].replace(/,/g, ""));
  return isNaN(rawNum) ? 0 : rawNum;
}

function parseUniversalDate(text) {
  if (!text) return null;
  const datePatterns = [
    /(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})/i,
    /(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})/i,
    /(\d{4})-(\d{1,2})-(\d{1,2})/,
    /(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/
  ];

  for (const pattern of datePatterns) {
    const match = text.match(pattern);
    if (match) {
      const parsed = Date.parse(match[0]);
      if (!isNaN(parsed)) return new Date(parsed).toISOString();
    }
  }
  return null;
}

function extractStructuredProductData() {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const s of scripts) {
    try {
      const data = JSON.parse(s.innerText);
      const items = Array.isArray(data) ? data : [data];
      for (const item of items) {
        if (item["@type"] === "Product" || (Array.isArray(item["@type"]) && item["@type"].includes("Product"))) {
          const offers = item.offers;
          let price = 0;
          let msrp = 0;
          let sellerName = "";
          if (offers) {
            const offer = Array.isArray(offers) ? offers[0] : offers;
            price = parseFloat(offer.price || offer.lowPrice || 0);
            msrp = parseFloat(offer.highPrice || 0);
            if (offer.seller) {
              sellerName = offer.seller.name || (typeof offer.seller === 'string' ? offer.seller : "");
            }
          }
          
          let ratingValue = null;
          let reviewCount = null;
          if (item.aggregateRating) {
            ratingValue = parseFloat(item.aggregateRating.ratingValue || 0);
            reviewCount = parseInt(item.aggregateRating.reviewCount || item.aggregateRating.ratingCount || 0, 10);
          }

          const schemaReviews = [];
          if (item.review) {
            const revList = Array.isArray(item.review) ? item.review : [item.review];
            revList.forEach(r => {
              if (r.reviewBody) schemaReviews.push(r.reviewBody.trim());
            });
          }

          return {
            title: item.name && !item.name.includes("Product summary") ? item.name : "",
            price: price,
            msrp: msrp,
            sellerName: sellerName,
            ratingValue: ratingValue,
            reviewCount: reviewCount,
            releaseDate: item.releaseDate || item.dateCreated || null,
            schemaReviews: schemaReviews
          };
        }
      }
    } catch (e) {}
  }
  return null;
}

function harvestUniversalPricing() {
  const structured = extractStructuredProductData();
  let price = structured?.price || 0;
  let msrp = structured?.msrp || 0;

  const buyBox = document.querySelector(
    '#apex_desktop, #corePriceDisplay_desktop_feature_div, #corePrice_feature_div, form[action*="/cart/add"], [class*="product-form" i], [class*="product__info" i], [class*="product-single" i], [class*="product-detail" i], main'
  ) || document.body;

  if (!msrp || msrp <= price) {
    const candidateNodes = buyBox.querySelectorAll('s, del, strike, [class*="strike" i], [class*="original" i], [class*="compare" i], [class*="mrp" i], [class*="was" i], [style*="line-through"]');
    for (const node of candidateNodes) {
      const val = parseNumber(node.innerText);
      if (val > 0) {
        msrp = val;
        break;
      }
    }

    if (!msrp || msrp <= price) {
      const allTextSpans = buyBox.querySelectorAll('span, p, div');
      for (const el of allTextSpans) {
        if (el.children.length === 0 && el.innerText.trim().length > 0) {
          try {
            const style = window.getComputedStyle(el);
            if (style.textDecorationLine.includes("line-through") || style.textDecoration.includes("line-through")) {
              const val = parseNumber(el.innerText);
              if (val > 0) {
                msrp = val;
                break;
              }
            }
          } catch (e) {}
        }
      }
    }
  }

  if (!price || price <= 0) {
    const priceSelectors = [
      'div._30jeq3._16Jk6d',
      'div._30jeq3',
      '.a-price:not([data-a-strike="true"]) .a-offscreen',
      '[class*="price--current" i]',
      '[class*="price-item--sale" i]',
      '[class*="current-price" i]',
      '[class*="special-price" i]',
      '[class*="product-price" i]',
      'span[itemprop="price"]',
      '.price .amount'
    ];
    for (const sel of priceSelectors) {
      const el = buyBox.querySelector(sel);
      if (el && el.innerText.trim()) {
        const val = parseNumber(el.innerText);
        if (val > 0) { price = val; break; }
      }
    }
  }

  if (!price || price <= 0 || !msrp || msrp <= price) {
    const textSnippet = buyBox.innerText.slice(0, 1500);
    const currencyMatches = textSnippet.match(/(?:Rs\.?|INR|[₹$€£])\s*([\d,]+(?:\.\d{1,2})?)/gi) || [];
    
    if (currencyMatches.length >= 2) {
      const parsedNums = currencyMatches.map(m => parseNumber(m)).filter(n => n > 0);
      if (parsedNums.length >= 2) {
        if (!price || price <= 0) price = Math.min(...parsedNums);
        if (!msrp || msrp <= price) msrp = Math.max(...parsedNums);
      }
    } else {
      const discountBlockMatch = textSnippet.match(/(?:↓|\%|\bdiscount\b|\boff\b)[^\d]*(\d{2,7})[^\d]*(\d{2,7})/i);
      if (discountBlockMatch) {
        const n1 = parseFloat(discountBlockMatch[1]);
        const n2 = parseFloat(discountBlockMatch[2]);
        if (n1 > 0 && n2 > 0 && n1 !== n2) {
          if (!price || price <= 0) price = Math.min(n1, n2);
          if (!msrp || msrp <= price) msrp = Math.max(n1, n2);
        }
      }
    }
  }

  if (!price || price <= 0) {
    price = parseNumber(buyBox.innerText.slice(0, 1000));
  }

  return { price, msrp };
}

function harvestAllReviews() {
  const reviews = [];
  const authors = [];
  const seenTexts = new Set();

  // Extract entire review cards (Title + Body + Emojis together)
  const cardSelectors = [
    '.jdgm-rev',
    '.loox-review',
    '.spr-review',
    '.stamped-review',
    '.yotpo-review',
    '[data-hook="review"]',
    'div._16PBlm',
    'div.col._2wzgFH',
    'div._27M-vq',
    '[class*="review-item" i]',
    '[class*="review-card" i]',
    '[class*="review_item" i]',
    '[class*="review_block" i]',
    '[class*="testimonial" i]'
  ];

  const cards = document.querySelectorAll(cardSelectors.join(', '));

  cards.forEach((card) => {
    // Clone node to safely remove rating star boilerplate numbers
    const clone = card.cloneNode(true);
    const starEls = clone.querySelectorAll('.jdgm-rev__rating, .spr-starrating, [class*="rating" i], [class*="star" i], svg, button');
    starEls.forEach(el => el.remove());

    let fullCardText = clone.innerText.trim();
    fullCardText = fullCardText.replace(/\s+/g, ' ');

    if (
      fullCardText.length >= 8 &&
      fullCardText.length <= 1500 &&
      !fullCardText.includes("How are ratings calculated") &&
      !fullCardText.includes("Write a customer review") &&
      !seenTexts.has(fullCardText)
    ) {
      seenTexts.add(fullCardText);
      reviews.push(fullCardText);

      const authorEl = card.querySelector(
        '.jdgm-rev__author, .spr-review-header-byline, [data-hook="review-author"], p._2NsDsF, [class*="author" i], [class*="buyer" i], [class*="user" i]'
      );
      if (authorEl && authorEl.innerText.trim()) {
        authors.push(authorEl.innerText.trim());
      }
    }
  });

  // Fallback: If containers were missed, gather specific paragraph text
  if (reviews.length < 5) {
    const textNodes = document.querySelectorAll('.jdgm-rev__body, .spr-review-content-body, div.ZmyHeo, [data-hook="review-body"], [class*="review-text" i]');
    textNodes.forEach((node) => {
      let t = node.innerText.trim();
      if (t.length > 10 && !seenTexts.has(t)) {
        seenTexts.add(t);
        reviews.push(t);
      }
    });
  }

  return { reviews: reviews.slice(0, 35), authors: authors.slice(0, 35) };
}

function extractProductData() {
  const structured = extractStructuredProductData();
  const pageText = document.body.innerText;
  const pageTextLower = pageText.toLowerCase();
  const hostname = window.location.hostname.replace("www.", "").toLowerCase();

  let title = structured?.title || "";
  if (!title || title.length < 3 || title.includes("Product summary")) {
    const titleEl = document.querySelector(
      "#productTitle, h1.product-title, h1[class*='title' i], h1, span.B_NuCI, .B_NuCI, ._35KyD6"
    );
    if (titleEl && titleEl.innerText.trim()) {
      title = titleEl.innerText.trim();
    } else {
      title = document.title.split(/[-|:–]/)[0].trim();
    }
  }

  const { price, msrp } = harvestUniversalPricing();

  let overallRating = structured?.ratingValue || 0;
  if (!overallRating || overallRating <= 0) {
    const ratingMatch = pageText.match(/(\d(?:\.\d)?)\s*(?:out of 5|\/5|\s*stars)/i);
    if (ratingMatch) {
      overallRating = parseFloat(ratingMatch[1]);
    }
  }

  let listingDate = structured?.releaseDate ? parseUniversalDate(structured.releaseDate) : null;
  if (!listingDate) {
    const allDetailContainers = document.querySelectorAll('table, ul, dl, div[class*="detail" i], div[class*="spec" i]');
    for (const container of allDetailContainers) {
      const text = container.innerText;
      if (/date first available|release date|date created|published on|listed on/i.test(text)) {
        const parsed = parseUniversalDate(text);
        if (parsed) {
          listingDate = parsed;
          break;
        }
      }
    }
  }

  let isMultiSellerPlatform = false;
  let sellerName = structured?.sellerName || "";
  let isFulfilled = false;
  let isBrandStore = false;
  let sellerIsJustLaunched = false;
  let sellerPositiveRatingPct = 100;

  const knownMarketplaceKeywords = ["flipkart.com", "amazon.", "myntra.com", "ajio.com", "tatacliq.com", "nykaa.com", "meesho.com", "ebay."];
  if (knownMarketplaceKeywords.some(k => hostname.includes(k))) {
    isMultiSellerPlatform = true;
  }

  const sellerCues = [
    '#sellerProfileTriggerId', '#merchant-info', 'div#sellerName',
    'div._1RLviY', 'div._2k6Cbx', 'div.fM06G9', '[class*="seller-name" i]',
    '[class*="merchant-name" i]', '[id*="seller-info" i]', '[class*="sold-by" i]'
  ];

  for (const sel of sellerCues) {
    const el = document.querySelector(sel);
    if (el && el.innerText.trim()) {
      sellerName = el.innerText.trim();
      isMultiSellerPlatform = true;
      break;
    }
  }

  if (/sold by|seller:|ships from and sold by|merchant info/i.test(pageText)) {
    isMultiSellerPlatform = true;
  }

  if (/just launched|no ratings yet|new seller/i.test(pageTextLower)) {
    sellerIsJustLaunched = true;
  }

  const ratingMatch = pageText.match(/(\d{1,3})%\s*positive/i);
  if (ratingMatch) {
    sellerPositiveRatingPct = parseInt(ratingMatch[1], 10);
  }

  if (document.querySelector("[aria-label*='Prime'], .a-icon-prime, [id*='prime'], img[src*='fa_'], ._32UQ-w, [class*='verified-badge' i], [class*='assured' i]")) {
    isFulfilled = true;
  }
  if (document.querySelector("#bylineInfo[href*='/stores/'], #brand, [class*='official-store' i], [class*='brand-store' i]")) {
    isBrandStore = true;
  }

  const isExplicitZeroReviews = (structured?.reviewCount === 0) ||
                                /there are 0 customer reviews|0 customer reviews and 0 customer ratings|be the first to review|no customer reviews yet|0 ratings/i.test(pageTextLower);

  let { reviews, authors } = isExplicitZeroReviews ? { reviews: [], authors: [] } : harvestAllReviews();

  if (structured?.schemaReviews && structured.schemaReviews.length > 0) {
    structured.schemaReviews.forEach(r => {
      if (!reviews.includes(r)) reviews.push(r);
    });
  }

  const domainParts = hostname.split('.');
  const isSubdomain = domainParts.length > 2 && !hostname.endsWith("co.in") && !hostname.endsWith("co.uk") && !hostname.endsWith("gov.in");

  return {
    url: window.location.href,
    domain: hostname,
    title: title,
    price: price,
    msrp: msrp,
    overallRating: overallRating,
    listingDate: listingDate,
    sellerInfo: {
      sellerName: sellerName,
      isMultiSellerPlatform: isMultiSellerPlatform,
      isFulfilled: isFulfilled,
      isBrandStore: isBrandStore,
      isJustLaunched: sellerIsJustLaunched,
      positiveRatingPct: sellerPositiveRatingPct,
      isSubdomain: isSubdomain
    },
    textContent: pageText.slice(0, 6000),
    reviews: reviews.slice(0, 35),
    authors: authors.slice(0, 35)
  };
}

let lastSentPayloadTime = 0;
function harvestAndSend() {
  const now = Date.now();
  if (now - lastSentPayloadTime < 2500) return;
  lastSentPayloadTime = now;

  const payload = extractProductData();
  chrome.runtime.sendMessage({ action: "TRIGGER_AUDIT", payload }).catch(() => {});
}

if (document.readyState === "complete" || document.readyState === "interactive") {
  harvestAndSend();
  setTimeout(harvestAndSend, 1200);
} else {
  window.addEventListener("DOMContentLoaded", () => {
    harvestAndSend();
    setTimeout(harvestAndSend, 1200);
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getPageData") {
    harvestAndSend();
    sendResponse({ status: "TRIGGERED" });
  }
  return true;
});