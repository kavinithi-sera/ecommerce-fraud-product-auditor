import os
import json
from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()  # This automatically loads GEMINI_API_KEY from .env

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

#Local Review Fraud Detection
def detect_duplicate_reviews(reviews, similarity_threshold=0.85):
    """
    Identifies duplicate or copy-pasted review rings using TF-IDF and Cosine Similarity.
    """
    if len(reviews) < 2:
        return {"duplicate_count": 0, "flagged_pairs": []}

    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(reviews)
    sim_matrix = cosine_similarity(tfidf_matrix)

    flagged_pairs = []
    n = len(reviews)
    
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= similarity_threshold:
                flagged_pairs.append({
                    "review_a": reviews[i],
                    "review_b": reviews[j],
                    "similarity": float(sim_matrix[i][j])
                })

    return {
        "duplicate_count": len(flagged_pairs),
        "flagged_pairs": flagged_pairs
    }

#Gemini API Integration for Sentiment & Sarcasm
def analyze_reviews_with_gemini(reviews_text):
    """
    Uses Gemini API (JSON mode) to evaluate regional slang, sarcasm, and sentiment anomalies.
    """
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    prompt = f"""
    Analyze these e-commerce product reviews for fake sentiment, regional slang/multilingual content, sarcasm, or rating mismatches.
    Reviews:
    {reviews_text}

    Provide a breakdown in JSON format.
    """

    # Enforce JSON Schema response
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "sarcasm_detected": {"type": "BOOLEAN"},
                "regional_slang_score": {"type": "NUMBER"}, # -1.0 to 1.0
                "suspicious_review_reasons": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                },
                "confidence_score": {"type": "NUMBER"}
            },
            "required": ["sarcasm_detected", "regional_slang_score", "suspicious_review_reasons"]
        }
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=config
    )

    return json.loads(response.text)

#Fallback Logic
def run_nlp_pipeline(reviews_list):
    # Guard clause: Handle empty review lists gracefully
    if not reviews_list or len(reviews_list) == 0:
        return {
            "local_fraud_metrics": {
                "duplicate_count": 0,
                "flagged_pairs": []
            },
            "ai_metrics": {
                "sarcasm_detected": False,
                "hinglish_sentiment_score": 0.0,
                "suspicious_review_reasons": ["No customer reviews found for this listing."],
                "confidence_score": 1.0
            },
            "fallback_active": False,
            "overall_risk_score": 5  # Returns your baseline score of 5
        }
    
    # 1. Always run local TF-IDF check
    local_metrics = detect_duplicate_reviews(reviews_list)
    
    # 2. Attempt Gemini analysis with graceful fallback
    try:
        reviews_combined = "\n".join(reviews_list)
        ai_metrics = analyze_reviews_with_gemini(reviews_combined)
        used_fallback = False
    except Exception as e:
        print(f"[Warning] Gemini API unavailable or rate-limited: {e}")
        ai_metrics = {
            "sarcasm_detected": False,
            "regional_slang_score": 0.0,
            "suspicious_review_reasons": ["AI analysis bypassed (Fallback Mode Active)"],
            "confidence_score": 0.5
        }
        used_fallback = True

    return {
        "local_fraud_metrics": local_metrics,
        "ai_metrics": ai_metrics,
        "fallback_active": used_fallback
    }

def calculate_risk_score(local_metrics, ai_metrics):
    raw_score = 0
    
    # Add points based on detected anomalies...
    if local_metrics.get("duplicate_count", 0) > 0:
        raw_score += 30
        
    if ai_metrics.get("sarcasm_detected"):
        raw_score += 25

    # Enforce a minimum score of 5 when no risk factors are triggered
    final_score = max(5, raw_score)
    
    return final_score