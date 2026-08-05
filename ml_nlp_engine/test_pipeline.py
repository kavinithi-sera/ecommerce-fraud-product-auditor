from nlp_engine import run_nlp_pipeline

reviews = [
    "Amazing product! Highly recommend buying this. Best purchase ever!",
    "Amazing product! Highly recommend buying this. Best purchase ever!",
    "Bhai 5 star rating, but earphone left side stopped working in 2 minutes."
]

if __name__ == "__main__":
    # Test full pipeline with safety fallback
    result = run_nlp_pipeline(reviews)
    print("Pipeline Execution Result:")
    print(result)