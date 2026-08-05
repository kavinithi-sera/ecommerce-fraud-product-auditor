from nlp_engine import detect_duplicate_reviews

# Dummy dataset simulating real vs. bot reviews
dummy_reviews = [
    # Bot Cluster 1: Exact / Near-exact duplicates
    "Amazing product! Highly recommend buying this. Best purchase ever!",
    "Amazing product! Highly recommend buying this. Best purchase ever!",
    "Amazing product!! Highly recommend buying this item. Best purchase ever!",
    
    # Bot Cluster 2: Copy-pasted template
    "Quality is very bad, do not buy. Waste of money.",
    "Quality is very bad, do not buy. Waste of money.",
    
    # Genuine, unique reviews
    "The battery life is decent, but the delivery took around 5 days to reach Bangalore.",
    "Decent build quality for the price point, though the packaging was slightly damaged."
]

if __name__ == "__main__":
    print("--- Running Local Review Fraud Test ---\n")
    
    # Run TF-IDF + Cosine Similarity check (threshold = 0.85)
    results = detect_duplicate_reviews(dummy_reviews, similarity_threshold=0.85)
    
    print(f"Total Duplicate Pairs Detected: {results['duplicate_count']}\n")
    print("Flagged Review Pairs:")
    print("=" * 60)
    
    for idx, pair in enumerate(results['flagged_pairs'], 1):
        print(f"Match #{idx} | Similarity Score: {pair['similarity']:.2%}")
        print(f"  • Review A: \"{pair['review_a']}\"")
        print(f"  • Review B: \"{pair['review_b']}\"")
        print("-" * 60)