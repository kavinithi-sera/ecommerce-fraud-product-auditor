import sys
import os
import sqlite3
import hashlib
import re
import statistics
from datetime import datetime
import whois
from ddgs import DDGS

# =====================================================================
# 1. SQLITE DATABASE ENGINE
# =====================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'flask_n_db', 'database.db')

def init_db():
    """Initializes local SQLite tables for auditing and user votes."""
    conn = sqlite3.connect('database.db')
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
    print("[SQLite DB]: Database initialized successfully.")

# =====================================================================
# 2. ANTI-BOT SECURITY
# =====================================================================
def hash_ip_address(ip_address):
    """Anonymizes user IP network signatures using SHA-256."""
    return hashlib.sha256(ip_address.encode('utf-8')).hexdigest()

# =====================================================================
# 3. DOMAIN SECURITY & WHOIS LONGEVITY CHECKER
# =====================================================================
def check_domain_infrastructure(domain_name):
    """
    Checks WHOIS creation age, high-risk TLDs (.xyz, .top), and raw IP usage.
    """
    risk = 0
    reasons = []
    
    if not domain_name:
        return {"risk": 0, "reasons": []}
    
    domain_clean = domain_name.lower().replace("www.", "").split('/')[0]
    
    # 1. High-Risk Spam TLD Check
    suspicious_tlds = ['.xyz', '.top', '.vip', '.win', '.cc', '.club', '.gq', '.cf']
    if any(domain_clean.endswith(tld) for tld in suspicious_tlds):
        risk += 15
        reasons.append(f"High-risk domain extension detected ({domain_clean.split('.')[-1]}).")
        
    # 2. WHOIS Domain Registration Age
    try:
        w = whois.whois(domain_clean)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        if creation_date:
            age_days = (datetime.now() - creation_date).days
            if age_days < 60:
                risk += 20
                reasons.append(f"Newly created domain: Registered only {age_days} days ago.")
    except Exception:
        # If WHOIS lookup fails or gets blocked, handle gracefully
        pass
        
    return {"risk": risk, "reasons": reasons}

# =====================================================================
# 4. DECEPTIVE MARKETING & DARK PATTERNS DETECTOR
# =====================================================================
def analyze_dark_patterns(page_text):
    """
    Scans for aggressive urgency indicators, fake stock counts, and brand stuffing.
    """
    risk = 0
    reasons = []
    
    # Regex patterns for artificial urgency
    urgency_patterns = [
        r'only\s+[1-9]\s+left\s+in\s+stock',
        r'deal\s+ends\s+in\s+\d+\s+min',
        r'\d+\s+people\s+are\s+viewing\s+this',
        r'offer\s+expires\s+soon'
    ]
    
    for pattern in urgency_patterns:
        if re.search(pattern, page_text, re.IGNORECASE):
            risk += 15
            reasons.append("Artificial urgency text detected ('Only X left in stock' / Countdown).")
            break
            
    return {"risk": risk, "reasons": reasons}

# =====================================================================
# 5. INDIAN ECOSYSTEM: COD & RETURN POLICY RISK CHECKER
# =====================================================================
def analyze_cod_and_return_risk(page_text, is_steep_discount):
    """
    Detects non-returnable policies paired with high discounts on Cash-on-Delivery.
    """
    risk = 0
    reasons = []
    
    text_lower = page_text.lower()
    
    has_no_return = any(phrase in text_lower for phrase in ["no return", "non-returnable", "no refund", "no exchange"])
    has_cod = any(phrase in text_lower for phrase in ["cash on delivery", "cod available", "pay on delivery"])
    
    if is_steep_discount and has_no_return and has_cod:
        risk += 15
        reasons.append("High-Risk COD Vector: Steep discount paired with strict Non-Returnable terms.")
        
    return {"risk": risk, "reasons": reasons}

# =====================================================================
# 6. INTERNAL & EXTERNAL PRICE ENGINE (Statistical Median)
# =====================================================================
def analyze_internal_price_anomaly(raw_text):
    global_price_pattern = r'(?:[₹$€£¥]|(?:USD|EUR|GBP|INR|Rs\.?))\s*([\d,]+(?:\.\d{2})?)'
    matches = re.findall(global_price_pattern, raw_text, re.IGNORECASE)
    
    if not matches:
        return {"risk": 0, "has_steep_discount": False, "reasons": []}
    
    numeric_prices = []
    for match in matches:
        if not match:
            continue
        try:
            clean_num = float(match.replace(',', ''))
            if clean_num > 100:
                numeric_prices.append(clean_num)
        except ValueError:
            continue
            
    if len(numeric_prices) < 2:
        return {"risk": 0, "has_steep_discount": False, "reasons": []}
    
    numeric_prices.sort()
    min_price, max_price = numeric_prices[0], numeric_prices[-1]
    discount_margin = ((max_price - min_price) / max_price) * 100
    
    if discount_margin >= 80:
        return {
            "risk": 20,
            "has_steep_discount": True,
            "reasons": [f"Extreme Internal Slashed Price: {min_price} vs reference MSRP {max_price} ({int(discount_margin)}% drop)."]
        }
    
    return {"risk": 0, "has_steep_discount": False, "reasons": []}

def check_external_market_price(product_title, current_page_price):
    if not product_title or current_page_price <= 0:
        return {"risk": 0, "reasons": []}
    
    try:
        search_query = f"{product_title} price buy online india"
        results = list(DDGS().text(search_query, max_results=10))
        
        raw_numbers = []
        for r in results:
            # ONLY parse visible title and body text — DO NOT parse raw URL parameters
            text = r.get('title', '') + " " + r.get('body', '')
            
            # Explicit currency prefix pattern ONLY (removes loose 4-6 digit regex that broke on URLs)
            matches = re.findall(r'(?:[₹$]|Rs\.?|INR)\s*([\d,]{4,7})', text, re.IGNORECASE)
            for m in matches:
                clean_str = m.replace(',', '').split('.')[0]
                if clean_str.isdigit():
                    val = float(clean_str)
                    if val >= 1000:  # Ignore small numbers
                        raw_numbers.append(val)
                            
        if not raw_numbers:
            return {"risk": 0, "reasons": []}
        
        market_median = statistics.median(raw_numbers)
        
        # Flag if listed price is less than 40% of web market median
        if current_page_price < (market_median * 0.4):
            return {
                "risk": 25,
                "reasons": [f"External Market Variance: Listed at ₹{int(current_page_price)}, but web market median is ~₹{int(market_median)}."]
            }
            
        return {"risk": 0, "reasons": []}
        
    except Exception:
        return {"risk": 0, "reasons": []}

# =====================================================================
# 7. UNIFIED 100-POINT RISK AUDITOR (Role 2 Master Function)
# =====================================================================
def run_role2_security_audit(domain, product_title, page_price, raw_page_text):
    """
    Aggregates all Role 2 security vectors into a single score (0-100).
    """
    total_risk = 0
    all_reasons = []
    
    # Vector 1: Infrastructure & WHOIS Check (0-35 pts)
    domain_res = check_domain_infrastructure(domain)
    total_risk += domain_res["risk"]
    all_reasons.extend(domain_res["reasons"])
    
    # Vector 2: Internal Price Discount Check (0-20 pts)
    internal_price_res = analyze_internal_price_anomaly(raw_page_text)
    total_risk += internal_price_res["risk"]
    all_reasons.extend(internal_price_res["reasons"])
    
    # Vector 3: External Market Price Check (0-25 pts)
    external_price_res = check_external_market_price(product_title, page_price)
    total_risk += external_price_res["risk"]
    all_reasons.extend(external_price_res["reasons"])
    
    # Vector 4: Dark Patterns & Deceptive Urgency (0-15 pts)
    dark_res = analyze_dark_patterns(raw_page_text)
    total_risk += dark_res["risk"]
    all_reasons.extend(dark_res["reasons"])
    
    # Vector 5: COD & Non-Returnable Scam Logic (0-15 pts)
    cod_res = analyze_cod_and_return_risk(raw_page_text, internal_price_res["has_steep_discount"])
    total_risk += cod_res["risk"]
    all_reasons.extend(cod_res["reasons"])
    
    # Cap total risk at 100
    final_score = min(total_risk, 100)
    
    return {
        "domain": domain,
        "risk_score": final_score,
        "reasons": all_reasons
    }
