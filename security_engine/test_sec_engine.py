import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sec_engine import run_role2_security_audit, init_db

print("=== TESTING COMPLETE ROLE 2 UNIFIED AUDIT ENGINE ===\n")
    
init_db()
    
# Test Data: A fake store scam product page
test_domain = "cheap-deals-online.top"
test_title = "iPhone 15 128GB"
test_price = 4999.0
test_raw_text = """
    Limited Time Deal! iPhone 15 listed for ~~₹58900~~ now ₹4999.
    Only 2 left in stock! Deal ends in 05:00 min.
    Cash on delivery available. Strictly Non-Returnable and no refunds allowed.
    """
    
print(f"Auditing '{test_title}' on '{test_domain}'...\n")
audit_result = run_role2_security_audit(test_domain, test_title, test_price, test_raw_text)
    
print(f"TOTAL RISK SCORE : {audit_result['risk_score']} / 100")
print("TRIGGERED REASONS:")
for r in audit_result["reasons"]:
    print(f"  • {r}")