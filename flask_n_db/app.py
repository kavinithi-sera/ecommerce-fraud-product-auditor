# flask_n_db/app.py - Master Risk Engine

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
    hash_ip_address, check_domain_infrastructure, check_external_market_price
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

    cursor.execute("PRAGMA table_info(audit_logs)")
    audit_cols = [col[1] for col in cursor.fetchall()]
    if 'url' not in audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN url TEXT")

    cursor.execute("PRAGMA table_info(user_feedback)")
    feedback_cols = [col[1] for col in cursor.fetchall()]
    if 'comments' not in feedback_cols:
        cursor.execute("ALTER TABLE user_feedback ADD COLUMN comments TEXT")

    conn.commit()
    conn.close()

init_local_db()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "online", "message": "Scamouflage Engine Live"}), 200

@app.route('/api/analyze', methods=['POST'])
def analyze_listing():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON"}), 400

        url = data.get('url', '')
        domain = data.get('domain', '')
        title = data.get('title', '')
        price = float(data.get('price', 0))
        msrp = float(data.get('msrp', 0))
        overall_rating = float(data.get('overallRating', 0))
        listing_date = data.get('listingDate', None)
        seller_info = data.get('sellerInfo', {})
        page_text = data.get('textContent', '')
        reviews = data.get('reviews', [])
        authors = data.get('authors', [])

        all_reasons = []
        detailed_audit = {}
        evidence_data = {
            "price_details": {},
            "domain_age": "",
            "seller_profile": {},
            "dark_pattern_quotes": [],
            "flagged_reviews": []
        }

        # -------------------------------------------------------------
        # 1. VECTOR 1: Price Check (0-20 pts)
        # -------------------------------------------------------------
        part_a_score = 0
        part_b_score = 0

        external_price_vec = check_external_market_price(title, price)
        part_a_score = external_price_vec.get('risk', 0)
        all_reasons.extend(external_price_vec.get('reasons', []))

        internal_audit = ""
        discount_pct = 0
        if price > 0 and msrp > price:
            discount_pct = ((msrp - price) / msrp) * 100
            internal_audit = f"Price: Rs. {price} (Original MRP shown as Rs. {msrp}, a {round(discount_pct)}% markdown)."
            if discount_pct >= 85:
                part_b_score = 10
                all_reasons.append(f"Suspicious On-Page Discount: {round(discount_pct)}% off from Rs. {msrp} down to Rs. {price}.")
            elif discount_pct >= 70:
                part_b_score = 5
                all_reasons.append(f"Heavy Promotional Discount: {round(discount_pct)}% off from original price.")
        elif price > 0:
            internal_audit = f"Selling price: Rs. {price} (Standard listing without discount slash)."
        else:
            internal_audit = "Normal price range."

        price_variance_score = min(part_a_score + part_b_score, 20)
        detailed_audit["price_variance"] = f"{internal_audit} {external_price_vec.get('audit_details', '')}".strip()

        evidence_data["price_details"] = {
            "listed_price": price,
            "stated_mrp": msrp,
            "discount_pct": round(discount_pct) if discount_pct > 0 else 0,
            "market_median": external_price_vec.get('median_price', 0),
            "samples_found": external_price_vec.get('samples_found', 0)
        }

        # -------------------------------------------------------------
        # 2. VECTOR 2: Store & Listing Longevity (0-20 pts)
        # -------------------------------------------------------------
        is_subdomain = seller_info.get('isSubdomain', False)
        is_multi_seller = seller_info.get('isMultiSellerPlatform', False)

        if is_subdomain and not is_multi_seller:
            domain_score = 10
            all_reasons.append("Generic Storefront: Hosted on a generic multi-tenant platform.")
            detailed_audit["domain_infrastructure"] = f"Hosted on a generic web platform ('{domain}')."
            evidence_data["domain_age"] = "Generic Subdomain"
        else:
            domain_vec = check_domain_infrastructure(domain, listing_date, is_multi_seller)
            domain_score = domain_vec.get('risk', 0)
            all_reasons.extend(domain_vec.get('reasons', []))
            detailed_audit["domain_infrastructure"] = domain_vec.get('audit_detail', "Verified record.")
            evidence_data["domain_age"] = domain_vec.get('age_str', domain_vec.get('audit_detail', 'Established'))

        evidence_data["sample_reviews"] = reviews[:6]
        # -------------------------------------------------------------
        # NLP & AI Execution (Customer Reviews & Page Text)
        # -------------------------------------------------------------
        nlp_result = run_nlp_pipeline(title, page_text, reviews, authors)
        ai_data = nlp_result.get('ai_metrics', {})

        # -------------------------------------------------------------
        # 3. VECTOR 3: Customer Reviews Authenticity (0-20 pts)
        # -------------------------------------------------------------
        review_score = 0
        if not nlp_result.get('has_reviews', True):
            review_score = 20  # Full precautionary penalty for unreviewed listings
            all_reasons.append("Unverified Listing: No buyers have reviewed this product yet (High Precaution).")
            detailed_audit["review_authenticity"] = "No customer reviews found. Assigned full precaution score."
        else:
            local_m = nlp_result['local_fraud_metrics']
            review_audit_notes = [f"Checked {len(reviews)} reviews."]

            if 0 < overall_rating < 3.0:
                review_score += 15
                all_reasons.append(f"Poor Product Rating: Overall customer score is low ({overall_rating} / 5 stars).")
                review_audit_notes.append(f"Low rating: {overall_rating}/5.")
            elif 3.0 <= overall_rating < 3.6:
                review_score += 8
                all_reasons.append(f"Below Average Rating: Customer score is mediocre ({overall_rating} / 5 stars).")
                review_audit_notes.append(f"Below average rating: {overall_rating}/5.")

            # Template Bot Praise Detection
            if local_m.get('template_bot_detected', False) or ai_data.get('template_formula_detected', False):
                review_score += 15
                all_reasons.append("Fake/Bot Reviews: Multiple reviews follow the exact same template pattern from different accounts.")
                review_audit_notes.append("Formulaic bot review structure detected.")

            # Unrelated Product Catalog Hijacking
            if ai_data.get('unrelated_product_hijacking_detected', False):
                review_score += 15
                all_reasons.append("Mismatched Reviews: Reviews describe completely different, unrelated items.")
                review_audit_notes.append("Unrelated product reviews detected.")

            # Duplicate Reviews
            if local_m['duplicate_count'] > 0:
                review_score += min(local_m['duplicate_count'] * 10, 15)
                all_reasons.append(f"Copy-Pasted Reviews: Found {local_m['duplicate_count']} reviews with identical wording.")
                review_audit_notes.append(f"Found {local_m['duplicate_count']} duplicate review(s).")

            # Duplicate Authors
            if local_m.get('author_duplicate_count', 0) > 0:
                review_score += min(local_m['author_duplicate_count'] * 10, 15)
                all_reasons.append("Fake Review Warning: The same user account wrote multiple reviews on this item.")
                review_audit_notes.append("Repeated reviewer usernames found.")

            # Bot Stylometry
            if local_m.get('is_bot_vocabulary', False):
                review_score += 10
                all_reasons.append("Robotic Reviews: Reviews sound repetitive and computer-generated.")
                review_audit_notes.append("Robotic phrasing detected.")

            if ai_data.get('counterfeit_complaint_detected', False):
                review_score += 20
                all_reasons.append("Fake Product Warning: Past buyers reported receiving broken items, empty boxes, or fakes.")

            if ai_data.get('negative_feedback_detected', False):
                review_score += 12
                all_reasons.append("Negative Customer Reviews: Buyers reported poor quality, defects, performance issues, or dissatisfaction.")
                review_audit_notes.append("Buyer dissatisfaction/defects reported in reviews.")

            if ai_data.get('astroturf_bot_praise_detected', False):
                review_score += 10
                all_reasons.append("Artificial Praise: Customer reviews appear fake or paid-for.")

            if ai_data.get('sarcasm_detected', False):
                review_score += 10
                all_reasons.append("Sarcastic Review Alert: Buyers used sarcastic praise to conceal reports of defective items.")
                review_audit_notes.append("Sarcastic complaints detected.")

            if ai_data.get('multilingual_negative_detected', False):
                review_score += 15
                all_reasons.append("Buyer Warning: Negative product warnings or defect reports detected in regional language reviews.")
                review_audit_notes.append("Negative regional language reviews detected.")

            detailed_audit["review_authenticity"] = " ".join(review_audit_notes)
            evidence_data["flagged_reviews"] = ai_data.get("flagged_reviews", [])

        review_score = min(review_score, 20)

        # -------------------------------------------------------------
        # 4. VECTOR 4: Hidden Traps & Pressure Tactics (0-20 pts)
        # -------------------------------------------------------------
        dark_score = 0
        dark_audit_notes = []

        if ai_data.get('has_pressure_timers', False):
            dark_score += 10
            all_reasons.append("Fake Urgency: Uses pressure countdowns or fake stock limits.")
            dark_audit_notes.append("Pressure countdown detected.")

        if ai_data.get('has_replica_keywords', False):
            dark_score += 15
            all_reasons.append("Replica / Clone Warning: The product description uses terms indicating a copy or clone.")
            dark_audit_notes.append("Replica language detected.")

        if ai_data.get('has_hidden_return_traps', False):
            dark_score += 10
            all_reasons.append("Hidden Return Trap: Restrictive return conditions found in fine print.")
            dark_audit_notes.append("Restrictive return terms found.")

        dark_score = min(dark_score, 20)
        detailed_audit["dark_patterns"] = " ".join(dark_audit_notes) if dark_audit_notes else "No hidden return traps or pressure timers found."
        evidence_data["dark_pattern_quotes"] = ai_data.get("evidence_snippets", [])

        # -------------------------------------------------------------
        # 5. VECTOR 5: Seller Verification & Buyer Protection (0-20 pts)
        # -------------------------------------------------------------
        is_fulfilled = seller_info.get('isFulfilled', False)
        is_brand = seller_info.get('isBrandStore', False)
        seller_name = seller_info.get('sellerName', '')
        is_just_launched = seller_info.get('isJustLaunched', False)
        pos_pct = seller_info.get('positiveRatingPct', 100)

        platform_score = 0
        seller_notes = []

        if is_multi_seller:
            if is_just_launched:
                platform_score += 15
                all_reasons.append(f"New Seller: Merchant '{seller_name or 'Unknown'}' just joined and has no sales track record.")
                seller_notes.append("Brand new seller account with no prior ratings.")
            elif pos_pct < 80:
                platform_score += 10
                all_reasons.append(f"Low Seller Rating: Seller has a low positive feedback score ({pos_pct}%).")
                seller_notes.append(f"Low seller rating: {pos_pct}%.")

            if not is_fulfilled and not is_brand:
                platform_score = max(platform_score, 15)
                all_reasons.append(f"Self-Shipped by Third-Party: Sold by '{seller_name or 'Unverified'}' without warehouse inspection or platform fulfillment guarantee.")
                seller_notes.append("Ships directly from third-party seller (no warehouse inspection).")
            elif not is_fulfilled:
                platform_score = max(platform_score, 5)
                all_reasons.append("Self-Shipped: Shipped directly by merchant rather than the platform warehouse.")
                seller_notes.append("Merchant-fulfilled delivery.")
            else:
                seller_notes.append("Verified fulfillment (Prime / Assured / Official Brand).")

            detailed_audit["platform_verification"] = " ".join(seller_notes)
        else:
            platform_score = 15  # Independent shop without escrow
            all_reasons.append("Independent Store: Standalone shop without built-in marketplace buyer protection.")
            detailed_audit["platform_verification"] = "Independent store (no platform guarantee like Amazon/Flipkart)."

        platform_score = min(platform_score, 20)

        # -------------------------------------------------------------
        # Universal Scam Multiplier: Prevent Scam Sites (DeoDap) from Hiding Behind Domain Age
        # -------------------------------------------------------------
        if not is_multi_seller and (review_score >= 15 and (price_variance_score >= 10 or dark_score >= 5)):
            if domain_score == 0:
                domain_score = 15
                all_reasons.append("Deceptive Storefront Pattern: Suspicious pricing and bot reviews detected on standalone domain.")
                detailed_audit["domain_infrastructure"] = "Domain age trust discounted due to concurrent bot reviews and pricing anomalies."

        evidence_data["seller_profile"] = {
            "seller_name": seller_name or "Independent Merchant",
            "is_multi_seller": is_multi_seller,
            "is_fulfilled": is_fulfilled,
            "is_brand": is_brand,
            "rating_pct": pos_pct
        }

        # -------------------------------------------------------------
        # Exact Aggregate Total
        # -------------------------------------------------------------
        final_risk_score = min(price_variance_score + domain_score + review_score + dark_score + platform_score, 100)

        vector_scores = {
            "price_variance": price_variance_score,
            "domain_infrastructure": domain_score,
            "review_authenticity": review_score,
            "dark_patterns": dark_score,
            "platform_verification": platform_score
        }

        risk_tier = "HIGH RISK" if final_risk_score >= 70 else "MEDIUM RISK" if final_risk_score >= 40 else "LOW RISK"

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (url, domain, risk_score, timestamp) VALUES (?, ?, ?, ?)",
                (url, domain, final_risk_score, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"[Database Warning]: {db_err}")

        return jsonify({
            "status": "success",
            "domain": domain,
            "title": title,
            "risk_score": final_risk_score,
            "risk_level": risk_tier,
            "reasons": all_reasons,
            "vector_scores": vector_scores,
            "detailed_audit": detailed_audit,
            "evidence": evidence_data
        })

    except Exception as e:
        print(f"[Backend Error]: {e}")
        return jsonify({
            "status": "error",
            "message": "Audit service encountered an internal processing error.",
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "reasons": ["Audit could not be completed due to a temporary service error."],
            "vector_scores": {
                "price_variance": 0,
                "domain_infrastructure": 0,
                "review_authenticity": 0,
                "dark_patterns": 0,
                "platform_verification": 0
            },
            "detailed_audit": {},
            "evidence": {}
        }), 500

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    try:
        data = request.get_json() or {}
        domain = data.get('domain', '')
        vote = data.get('vote', '')
        comments = data.get('comments', '')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_feedback (domain, user_vote, comments, timestamp) VALUES (?, ?, ?, ?)",
            (domain, vote, comments, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Feedback recorded"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)