document.addEventListener('DOMContentLoaded', () => {
  const loadingState = document.getElementById('loading-state');
  const resultsState = document.getElementById('results-state');
  const riskBadge = document.getElementById('risk-badge');
  const riskScore = document.getElementById('risk-score');
  const reasonsList = document.getElementById('reasons-list');

  // Simulated payload received from Flask API (Role 1 & Role 2 & Role 3 merged output)
  const mockApiResponse = {
    risk_score: 78,
    risk_level: "HIGH RISK", // SAFE, MODERATE, HIGH RISK
    reasons: [
      "2 duplicate review rings flagged locally (scikit-learn TF-IDF)",
      "Sarcastic text found: 5-star rating despite 'dead left earphone' comment",
      "Price Slashed Anomaly: External web median price is ₹1,200 vs listed ₹4,999 MSRP"
    ]
  };

  // Function to render response data onto the UI
  function renderAuditResults(data) {
    loadingState.classList.add('hidden');
    resultsState.classList.remove('hidden');

    riskScore.textContent = data.risk_score;
    riskBadge.textContent = data.risk_level;

    // Apply color badge based on risk level
    riskBadge.className = "risk-badge";
    if (data.risk_score < 30) {
      riskBadge.classList.add('badge-safe');
    } else if (data.risk_score < 70) {
      riskBadge.classList.add('badge-warning');
    } else {
      riskBadge.classList.add('badge-danger');
    }

    // Populate reason list
    reasonsList.innerHTML = '';
    data.reasons.forEach(reason => {
      const li = document.createElement('li');
      li.textContent = reason;
      reasonsList.appendChild(li);
    });
  }

  // Simulate server response delay (1.5 seconds)
  setTimeout(() => {
    renderAuditResults(mockApiResponse);
  }, 1500);
});