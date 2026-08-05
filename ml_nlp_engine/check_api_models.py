# To get a list of available models for the GEMINI API key, run this script.

import os
from dotenv import load_dotenv
from google import genai

# 1. Load the API key from your .env file
load_dotenv()

# 2. Pass the key explicitly (or let Client pick up GEMINI_API_KEY from env)
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("❌ API key not found in .env file!")
else:
    client = genai.Client(api_key=api_key)
    
    print("Available models for your key:")
    print("-" * 40)
    for model in client.models.list():
        if "generateContent" in model.supported_actions:
            print(model.name)