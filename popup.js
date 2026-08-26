const BACKEND_URL = "https://ecommerce-fraud-detection-ext.onrender.com";
const FEEDBACK_URL = "https://ecommerce-fraud-detection-ext.onrender.com";

let lastResult = null;
let selectedVote = null;

function riskColor(value, max) {
  const pct = value / max;
  if (pct >= 0.7) return "#c0392b"; // red — high risk
  if (pct >= 0.4) return "#d98c1f"; // amber — medium risk
  return "#1a9d5c"; // green — low risk
}

const views = {
  loading: document.getElementById("loading-state"),
  main: document.getElementById("main-view"),
  report: document.getElementById("report-view"),
  feedback: document.getElementById("feedback-view"),
};

function showView(name) {
  Object.values(views).forEach((v) => v.classList.add("hidden"));
  views[name].classList.remove("hidden");
}

function circumference(r) { return 2 * Math.PI * r; }

function renderMain(data) {
  document.getElementById("domain-text").textContent = data.domain;
  document.getElementById("score-num").textContent = data.risk_score;
  document.getElementById("risk-label").textContent = data.risk_level;

  const c = circumference(70);
  const filled = (data.risk_score / 100) * c;
  const gauge = document.getElementById("gauge-fg");
  gauge.style.strokeDasharray = `${filled} ${c}`;
  const color = riskColor(data.risk_score, 100);
  gauge.style.stroke = color;
  document.getElementById("risk-label").style.color = color;

  const list = document.getElementById("reasons-preview");
  list.innerHTML = "";
  data.reasons.slice(0, 3).forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r;
    list.appendChild(li);
  });

  showView("main");
}

function vectorRow(label, value) {
  const wrap = document.createElement("div");
  wrap.className = "vector-row";
  if (value === null || value === undefined) {
    wrap.innerHTML = `<div class="vector-top"><span>${label}</span><span class="vector-na">Coming soon</span></div>`;
    return wrap;
  }
  const pct = Math.min((value / 20) * 100, 100);
  const color = riskColor(value, 20);
  wrap.innerHTML = `
    <div class="vector-top"><span>${label}</span><span>${value} / 20</span></div>
    <div class="vector-track"><div class="vector-fill" style="width:${pct}%; background:${color}"></div></div>
  `;
  return wrap;
}

function renderReport(data) {
  document.getElementById("report-domain").textContent = data.domain;
  document.getElementById("report-timestamp").textContent = new Date().toLocaleString();
  document.getElementById("report-verdict").textContent = data.risk_level;

  const bars = document.getElementById("vector-bars");
  bars.innerHTML = "";
  const vs = data.vector_scores || {};
  bars.appendChild(vectorRow("Price variance", vs.price_variance));
  bars.appendChild(vectorRow("Domain infrastructure", vs.domain_infrastructure));
  bars.appendChild(vectorRow("Review authenticity", vs.review_authenticity));
  bars.appendChild(vectorRow("Dark patterns", vs.dark_patterns));
  
}

function showError(message) {
  showView("main");
  document.getElementById("risk-label").textContent = "ERROR";
  document.getElementById("reasons-preview").innerHTML = `<li>${message}</li>`;
}

function runAudit() {
  showView("loading");
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, { action: "getPageData" }, async (pageData) => {
      if (!pageData) return showError("Could not read this page. Try refreshing it.");
      try {
        const res = await fetch(BACKEND_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(pageData),
        });
        const data = await res.json();
        if (data.status === "error") return showError(data.message);
        lastResult = data;
        renderMain(data);
      } catch (err) {
        showError("Could not reach server: " + err.message);
      }
    });
  });
}

document.getElementById("view-report-btn").addEventListener("click", () => {
  if (!lastResult) return;
  renderReport(lastResult);
  showView("report");
});
document.getElementById("close-report").addEventListener("click", () => showView("main"));

function downloadJSON() {
  if (!lastResult) return;
  const blob = new Blob([JSON.stringify(lastResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `fraud-audit-${lastResult.domain}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const VECTOR_EXPLANATIONS = {
  price_variance: "Compares the listed price against internal slashed-price patterns and live market medians pulled from web search, to catch fake or exaggerated discounts.",
  domain_infrastructure: "Checks how recently the domain was registered and whether it uses a high-risk extension (like .xyz or .top) — newer, throwaway-style domains score higher risk.",
  review_authenticity: "Runs review text through local duplicate detection (TF-IDF + cosine similarity) and Gemini AI sentiment analysis to catch copy-pasted or sarcastic/mismatched reviews.",
  dark_patterns: "Scans page text for manipulative tactics — fake urgency countdowns, artificial stock counters, and non-refundable Cash-on-Delivery restrictions.",
  platform_verification: "Platform verification is on our roadmap — we're building automated checks for marketplace trust badges like Flipkart Assured and Amazon Prime to add an extra layer of confidence in an upcoming release.",
};

const VECTOR_LABELS = {
  price_variance: "Price Variance",
  domain_infrastructure: "Domain Infrastructure",
  review_authenticity: "Review Authenticity",
  dark_patterns: "Dark Patterns",
  platform_verification: "Platform Verification",
};

function generatePDFReport() {
  if (!lastResult) return;
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const marginX = 15;
  let y = 20;

  doc.setFontSize(16);
  doc.setFont(undefined, "bold");
  doc.text("Shopping Fraud Audit Report", marginX, y);
  y += 10;

  doc.setFontSize(10);
  doc.setFont(undefined, "normal");
  doc.text(`Target URL: ${lastResult.domain}`, marginX, y); y += 6;
  doc.text(`Audit timestamp: ${new Date().toLocaleString()}`, marginX, y); y += 6;

  doc.setFont(undefined, "bold");
  doc.setFontSize(13);
  doc.setTextColor(lastResult.risk_score >= 70 ? 192 : lastResult.risk_score >= 40 ? 180 : 26,
                    lastResult.risk_score >= 70 ? 57  : lastResult.risk_score >= 40 ? 140 : 157,
                    lastResult.risk_score >= 70 ? 43  : lastResult.risk_score >= 40 ? 31  : 92);
  doc.text(`Final verdict: ${lastResult.risk_level} (${lastResult.risk_score} / 100)`, marginX, y);
  doc.setTextColor(0, 0, 0);
  y += 10;

  doc.setFontSize(12);
  doc.setFont(undefined, "bold");
  doc.text("Scores by risk vector", marginX, y);
  y += 7;

  doc.setFontSize(10);
  doc.setFont(undefined, "normal");
  const vs = lastResult.vector_scores || {};
  Object.keys(VECTOR_LABELS).forEach((key) => {
    const val = vs[key];
    const scoreText = val === null || val === undefined ? "Coming soon" : `${val} / 20`;
    doc.setFont(undefined, "bold");
    doc.text(`${VECTOR_LABELS[key]}: `, marginX, y);
    doc.setFont(undefined, "normal");
    doc.text(scoreText, marginX + 55, y);
    y += 5;
    const explanation = doc.splitTextToSize(VECTOR_EXPLANATIONS[key], 175);
    doc.setFontSize(9);
    doc.setTextColor(90, 90, 90);
    doc.text(explanation, marginX + 3, y);
    doc.setTextColor(0, 0, 0);
    doc.setFontSize(10);
    y += explanation.length * 4 + 5;
  });

  y += 3;
  doc.setFontSize(12);
  doc.setFont(undefined, "bold");
  doc.text("Triggered risk reasons", marginX, y);
  y += 7;

  doc.setFontSize(10);
  doc.setFont(undefined, "normal");
  if (lastResult.reasons && lastResult.reasons.length > 0) {
    lastResult.reasons.forEach((reason, i) => {
      if (y > 275) { doc.addPage(); y = 20; }
      const lines = doc.splitTextToSize(`${i + 1}. ${reason}`, 180);
      doc.text(lines, marginX, y);
      y += lines.length * 5 + 2;
    });
  } else {
    doc.text("No specific risk reasons were triggered.", marginX, y);
    y += 6;
  }

  y += 5;
  if (y > 270) { doc.addPage(); y = 20; }
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  doc.text("Generated client-side by the Shopping Fraud Auditor extension. Scores reflect only the analysis vectors currently implemented in this build.", marginX, y);

  doc.save(`fraud-audit-${lastResult.domain}.pdf`);
}

document.getElementById("download-btn").addEventListener("click", generatePDFReport);
document.getElementById("export-json-btn").addEventListener("click", downloadJSON);
document.getElementById("report-domain-btn").addEventListener("click", () => {
  alert("Reporting is not wired up yet — placeholder for a future version.");
});

document.getElementById("open-feedback-link").addEventListener("click", (e) => {
  e.preventDefault();
  showView("feedback");
});
document.getElementById("close-feedback").addEventListener("click", () => showView("main"));

document.querySelectorAll(".vote-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    selectedVote = btn.dataset.vote;
    document.querySelectorAll(".vote-btn").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
  });
});

document.getElementById("send-feedback-btn").addEventListener("click", async () => {
  if (!lastResult || !selectedVote) {
    alert("Pick Accurate or False Positive first.");
    return;
  }
  const notes = document.getElementById("feedback-notes").value;
  try {
    await fetch(FEEDBACK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: lastResult.domain, vote: selectedVote, comments: notes }),
    });
    alert("Feedback sent, thank you!");
    showView("main");
  } catch (err) {
    alert("Could not send feedback: " + err.message);
  }
});

runAudit();