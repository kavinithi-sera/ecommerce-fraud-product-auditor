# ml_nlp_engine/nlp_engine.py - NLP & Bot Review Pattern Engine

import os
import json
import re
from collections import Counter
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def detect_duplicate_reviews(reviews, similarity_threshold=0.85):
    if len(reviews) < 2:
        return {"duplicate_count": 0, "flagged_pairs": []}

    try:
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

        return {"duplicate_count": len(flagged_pairs), "flagged_pairs": flagged_pairs}
    except Exception:
        return {"duplicate_count": 0, "flagged_pairs": []}

def detect_structural_template_clones(reviews, min_phrase_len=3):
    if len(reviews) < 2:
        return {"template_bot_detected": False, "repeated_phrases": []}

    all_ngrams = []
    for r in reviews:
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', r.lower())
        words = [w for w in cleaned.split() if len(w) > 1]
        review_ngrams = set()
        for n in range(min_phrase_len, min(len(words) + 1, 6)):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                review_ngrams.add(phrase)
        all_ngrams.extend(list(review_ngrams))

    phrase_counts = Counter(all_ngrams)
    repeated = [p for p, count in phrase_counts.items() if count >= 2 and len(p.split()) >= 3]

    return {
        "template_bot_detected": len(repeated) >= 2,
        "repeated_phrases": repeated[:5]
    }

def detect_duplicate_authors(authors):
    if not authors or len(authors) < 2:
        return 0
    seen = {}
    dup_count = 0
    for name in authors:
        clean_name = name.lower().strip()
        if not clean_name:
            continue
        seen[clean_name] = seen.get(clean_name, 0) + 1
        if seen[clean_name] > 1:
            dup_count += 1
    return dup_count

def calculate_bot_stylometry(reviews):
    combined_text = " ".join(reviews).lower()
    tokens = re.findall(r'\b\w+\b', combined_text)
    if not tokens:
        return {"ttr_score": 1.0, "is_bot_vocabulary": False}

    unique_types = set(tokens)
    ttr = len(unique_types) / len(tokens)
    return {
        "ttr_score": round(ttr, 3),
        "is_bot_vocabulary": ttr < 0.40
    }

def analyze_page_semantics_with_gemini(title, page_text, reviews_text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "is_fraud_suspected": False,
            "negative_feedback_detected": False,
            "counterfeit_complaint_detected": False,
            "astroturf_bot_praise_detected": False,
            "template_formula_detected": False,
            "unrelated_product_hijacking_detected": False,
            "sarcasm_detected": False,
            "multilingual_negative_detected": False,
            "has_pressure_timers": False,
            "has_hidden_return_traps": False,
            "has_replica_keywords": False,
            "evidence_snippets": [],
            "flagged_reviews": [],
            "fraud_indicators": [],
            "confidence_score": 0.0
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are an e-commerce assistant protecting everyday shoppers. Audit this listing for FRAUD, FAKES, DEFECTIVE ITEMS, TEMPLATE BOT REVIEWS, POLICY TRAPS, or MANIPULATED FEEDBACK.
    Analyze across all languages, scripts, Romanized regional languages (Hinglish), and transliterated expressions without bias or hallucination.

    Product Title: "{title}"
    
    Page Text / Return Fine Print:
    {page_text[:3000]}

    Customer Reviews:
    {reviews_text[:7000] if reviews_text else "No customer reviews on page."}

    Evaluation Instructions:
    1. Template / Formulaic Bot Praise: Flag if reviews follow structured marketing formats, repetitive headline formulas, paired emojis with taglines (e.g., "[Heading] 🎁🏠 - [Tagline] / [Adjective]"), or Mad-Libs praise across multiple accounts.
    2. Unrelated Product Hijacking: Flag ONLY if reviews explicitly review a completely different physical item category (e.g., reviewing dinner plates, lunch boxes, or car parts on a clothing listing). DO NOT flag genuine reviews that describe product features, sizing, or synonyms.
    3. Negative Customer Feedback: Real buyers expressing dissatisfaction, reporting poor build quality, product defects, bad material, missing pieces, poor performance, or failure to work.
    4. Counterfeit Warnings: Real buyers reporting fakes, clones, knockoffs, or empty packages.
    5. Sarcasm / Irony: Sarcastic praise disguising product defects.
    6. Multi-language Negative Warnings: Critical warnings, complaints, or clone alerts in Romanized regional text or mixed languages.
    7. Pressure Tactics: Fake urgency countdown timers or artificial scarcity in page text.
    8. Hidden Traps: Restrictive return terms in fine print (e.g., mandatory unboxing video, non-refundable).
    9. Replica Language: Explicit clone or replica claims (e.g., first copy, 1:1 replica, OEM grade).

    Return your audit strictly in JSON format including exact quoted evidence snippets.
    """

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "is_fraud_suspected": {"type": "BOOLEAN"},
                "fraud_indicators": {"type": "ARRAY", "items": {"type": "STRING"}},
                "template_formula_detected": {"type": "BOOLEAN"},
                "unrelated_product_hijacking_detected": {"type": "BOOLEAN"},
                "negative_feedback_detected": {"type": "BOOLEAN"},
                "counterfeit_complaint_detected": {"type": "BOOLEAN"},
                "astroturf_bot_praise_detected": {"type": "BOOLEAN"},
                "sarcasm_detected": {"type": "BOOLEAN"},
                "multilingual_negative_detected": {"type": "BOOLEAN"},
                "has_pressure_timers": {"type": "BOOLEAN"},
                "has_hidden_return_traps": {"type": "BOOLEAN"},
                "has_replica_keywords": {"type": "BOOLEAN"},
                "evidence_snippets": {"type": "ARRAY", "items": {"type": "STRING"}},
                "flagged_reviews": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "review_snippet": {"type": "STRING"},
                            "flag_reason": {"type": "STRING"}
                        },
                        "required": ["review_snippet", "flag_reason"]
                    }
                },
                "confidence_score": {"type": "NUMBER"}
            },
            "required": [
                "is_fraud_suspected",
                "fraud_indicators",
                "template_formula_detected",
                "unrelated_product_hijacking_detected",
                "negative_feedback_detected",
                "counterfeit_complaint_detected",
                "astroturf_bot_praise_detected",
                "sarcasm_detected",
                "multilingual_negative_detected",
                "has_pressure_timers",
                "has_hidden_return_traps",
                "has_replica_keywords"
            ]
        }
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[Gemini Log]: Fallback mode engaged - {e}")
        return {
            "is_fraud_suspected": False,
            "template_formula_detected": False,
            "unrelated_product_hijacking_detected": False,
            "negative_feedback_detected": False,
            "counterfeit_complaint_detected": False,
            "astroturf_bot_praise_detected": False,
            "sarcasm_detected": False,
            "multilingual_negative_detected": False,
            "has_pressure_timers": False,
            "has_hidden_return_traps": False,
            "has_replica_keywords": False,
            "evidence_snippets": [],
            "flagged_reviews": [],
            "fraud_indicators": [],
            "confidence_score": 0.5
        }

def run_nlp_pipeline(title, page_text, reviews_list, authors_list=None):
    if not reviews_list or len(reviews_list) == 0:
        ai_data = analyze_page_semantics_with_gemini(title, page_text, "")
        return {
            "has_reviews": False,
            "unverified_penalty": 20,
            "local_fraud_metrics": {
                "duplicate_count": 0,
                "author_duplicate_count": 0,
                "template_bot_detected": False,
                "is_bot_vocabulary": False
            },
            "ai_metrics": ai_data
        }

    local_metrics = detect_duplicate_reviews(reviews_list)
    local_metrics["author_duplicate_count"] = detect_duplicate_authors(authors_list or [])
    
    template_check = detect_structural_template_clones(reviews_list)
    local_metrics["template_bot_detected"] = template_check["template_bot_detected"]
    local_metrics["repeated_template_phrases"] = template_check["repeated_phrases"]

    stylometry = calculate_bot_stylometry(reviews_list)
    local_metrics["is_bot_vocabulary"] = stylometry["is_bot_vocabulary"]

    reviews_combined = "\n".join(reviews_list)
    ai_metrics = analyze_page_semantics_with_gemini(title, page_text, reviews_combined)

    return {
        "has_reviews": True,
        "unverified_penalty": 0,
        "local_fraud_metrics": local_metrics,
        "ai_metrics": ai_metrics
    }