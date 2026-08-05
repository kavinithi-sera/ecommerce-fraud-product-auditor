import requests

url = "http://127.0.0.1:5001/api/analyze"

payload = {
    "domain": "cheap-deals-online.top",
    "title": "iPhone 15 Pro",
    "price": 4999,
    "textContent": "Limited Time Deal! Only 2 left in stock! Non-refundable COD.",
    "reviews": [
        "Amazing phone, delivered on time!",
        "Amazing phone, delivered on time!",
        "Great battery life, died in 5 mins 🙄"
    ]
}

try:
    response = requests.post(url, json=payload)
    print("\n--- FLASK API RESPONSE ---")
    print(response.json())
except Exception as e:
    print(f"Server not responding. Make sure app.py is running first! Error: {e}")