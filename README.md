# E-Commerce Deceptive Product Auditor - Web Extension

Real-time client-side browser extension and Python Flask backend that audits e-commerce storefronts for malicious domain infrastructure, dark patterns, pricing anomalies, and fake review spam.

## Project Structure
- `extension/` – Chrome extension (Manifest V3): content script, popup UI
- `flask_n_db/` – Flask backend, SQLite database, main API entry point
- `security_engine/` – Price anomaly, domain trust, dark-pattern checks
- `ml_nlp_engine/` – Review fraud detection using TF-IDF and Gemini API

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Create a `.env` file inside `flask_n_db/` with your Gemini API key
3. Run the backend: `python flask_n_db/app.py`
4. Load the `extension/` folder as an unpacked extension in Chrome