import os
import json
from nlp_engine import analyze_reviews_with_gemini
from dotenv import load_dotenv
load_dotenv()

# Sample Hinglish / sarcastic reviews to test Gemini's analysis
sample_reviews = """
1. "Bhai bohot badhiya product hai, earphone left side worked for 2 days then died completely. Superb delivery!"
2. "Quality looks okay, value for money lag raha hai. Packaging was a bit torn though."
3. "5 star rating! Extremely worst battery life ever seen, stops working in 10 minutes. Love it."
"""

if __name__ == "__main__":
    print("--- Running Gemini API Test ---")
    
    # 1. Check if GEMINI_API_KEY is loaded in env
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n❌ ERROR: GEMINI_API_KEY environment variable is not set.")
        print("Please set it in your terminal using: export GEMINI_API_KEY='your_key'")
        exit(1)
        
    print("✓ API Key detected in environment.")
    print("Sending reviews payload to Gemini API...\n")

    try:
        # 2. Call your Gemini function
        result = analyze_reviews_with_gemini(sample_reviews)
        
        # 3. Print formatted JSON output
        print("✓ Response received successfully!")
        print("=" * 50)
        print(json.dumps(result, indent=4))
        print("=" * 50)
        
        # 4. Verify expected JSON structure fields
        print("\nStructure Validation:")
        print(f" • Sarcasm Detected : {result.get('sarcasm_detected')}")
        print(f" • Sentiment Score  : {result.get('hinglish_sentiment_score')}")
        print(f" • Reasons Flagged  : {result.get('suspicious_review_reasons')}")
        
    except Exception as e:
        print(f"\n❌ API Test Failed: {e}")