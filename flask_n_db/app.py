import sys
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from security_engine.sec_engine import (
    run_role2_security_audit, hash_ip_address, init_db,
    check_domain_infrastructure, analyze_internal_price_anomaly,
    check_external_market_price, analyze_dark_patterns
)
from ml_nlp_engine.nlp_engine import run_nlp_pipeline

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'database.db'))

def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            risk_score INTEGER,
            timestamp TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            user_vote TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_local_db()

@app.route('/api/analyze', methods=['POST'])
def analyze_listing():
    """
    Unified API Endpoint: Receives DOM payload from extension, runs
    both Security & NLP engines, and returns an aggregate 100-pt Risk Score.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid or missing JSON payload"}), 400

        # Extract fields from payload
        domain = data.get('domain', '')
        title = data.get('title', '')
        price = float(data.get('price', 0))
        page_text = data.get('textContent', '')
        reviews = data.get('reviews', [])  # Array of review strings

        # 1. Anonymize Client IP
        client_ip = request.remote_addr or '127.0.0.1'
        ip_hash = hash_ip_address(client_ip)

        # 2. Run Security Audit Engine (Domain, Price Math, Dark Patterns, COD)
        sec_result = run_role2_security_audit(domain, title, price, page_text)
        security_score = sec_result['risk_score']
        all_reasons = list(sec_result['reasons'])

        # 3. Run NLP Engine (Local TF-IDF + Gemini AI)
        nlp_score = 0
        if reviews:
            nlp_result = run_nlp_pipeline(reviews)
            
            # Local Duplicate Review Penalty
            dup_count = nlp_result['local_fraud_metrics']['duplicate_count']
            if dup_count > 0:
                nlp_score += min(dup_count * 5, 15)  # Cap at 15 pts
                all_reasons.append(f"Detected {dup_count} duplicate/copy-pasted review cluster(s).")

            # AI Sentiment & Sarcasm Logic Fix
            ai_data = nlp_result['ai_metrics']
            sentiment_score = ai_data.get('hinglish_sentiment_score', 0.0)
            has_sarcasm = ai_data.get('sarcasm_detected', False)

            # Flag ONLY if sarcasm is paired with a negative/mismatched sentiment
            if has_sarcasm and sentiment_score < 0:
                nlp_score += 10
                all_reasons.append("Review Integrity Flag: Sarcastic negative reviews detected behind positive ratings.")
            elif sentiment_score < -0.5:
                nlp_score += 5
                all_reasons.append("Review Integrity Flag: Customer reviews are overwhelmingly negative.")

            # Append specific AI warning reasons
            for reason in ai_data.get('suspicious_review_reasons', []):
                if "Fallback" not in reason and reason not in all_reasons:
                    all_reasons.append(f"Review Flag: {reason}")
        
        # Vector-level breakdown for the detailed report UI
        domain_vec = check_domain_infrastructure(domain)
        internal_price_vec = analyze_internal_price_anomaly(page_text)
        external_price_vec = check_external_market_price(title, price)
        dark_vec = analyze_dark_patterns(page_text)

        vector_scores = {
            "price_variance": round(min(internal_price_vec['risk'] + external_price_vec['risk'], 45) / 45 * 20),
            "domain_infrastructure": round(min(domain_vec['risk'], 35) / 35 * 20),
            "review_authenticity": round(min(nlp_score, 20)) if reviews else None,
            "dark_patterns": round(min(dark_vec['risk'], 15) / 15 * 20),
            "platform_verification": None  # not implemented yet
        }

        # 4. Calculate Aggregate Score (Capped at 100)
        final_risk_score = min(security_score + nlp_score, 100)

        if final_risk_score >= 70:
            risk_tier = "HIGH RISK"
        elif final_risk_score >= 40:
            risk_tier = "MEDIUM RISK"
        else:
            risk_tier = "LOW RISK"

        # 5. Log Audit Event to SQLite
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (domain, risk_score, timestamp) VALUES (?, ?, ?)",
                (domain, final_risk_score, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"[Database Warning]: {db_err}")

        # Return JSON payload to Extension Popup
        return jsonify({
            "status": "success",
            "domain": domain,
            "risk_score": final_risk_score,
            "risk_level": risk_tier,
            "reasons": all_reasons,
            "breakdown": {
                "security_score": security_score,
                "nlp_score": nlp_score
            },
            "vector_scores": vector_scores
       
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    """Feedback Endpoint: Logs user accuracy votes."""
    try:
        data = request.get_json()
        domain = data.get('domain', '')
        vote = data.get('vote', '')  # 'Accurate' or 'False Positive'

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_feedback (domain, user_vote, timestamp) VALUES (?, ?, ?)",
            (domain, vote, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Feedback recorded"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("=== Starting E-Commerce Fraud Audit Server ===")
    app.run(host='0.0.0.0', port=5001, debug=True)